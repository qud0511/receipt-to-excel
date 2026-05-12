"""우리카드 매출전표 룰 기반 파서.

ADR-004 §"우리카드 N-up layout 분석" 의 결정 사항:
- 라벨 없는 위치 기반 layout — `국내전용카드` 마커 이후 12~16 line block.
- 4-line 금액 순서 추정: ① 거래금액 ② 봉사료 ③ 부가세 ④ 자원순환보증금.
- 거래일+시각 붙음 (yyyy/MM/ddHH:mm:ss) — 우리카드 특이.
- Confidence: 거래금액=high, 부가세=medium, 봉사료/자원순환=low.

ADR-005 §"Parser returns list":
- N-up (2-column) 페이지 → ``page.crop()`` 으로 컬럼별 분리 후 splitter 적용.
- 단일 거래도 길이 1 list 반환 (일관 계약).
"""

from __future__ import annotations

import asyncio
import io
import re
from datetime import date, time

import pdfplumber
import structlog

from app.domain.confidence import ConfidenceLabel
from app.domain.parsed_transaction import ParsedTransaction
from app.services.parsers.base import (
    BaseParser,
    FormatMismatchError,
    ParserTier,
    ProviderNotDetectedError,
    RequiredFieldMissingError,
)
from app.services.parsers.preprocessor.nup_splitter import split_by_marker

_log = structlog.get_logger(__name__)

# 페이지 발행 timestamp — 거래일과 별개. 추출 시 skip (splitter 가 처리).
_PAGE_HEADER_TIMESTAMP = re.compile(r"^\d{4}\.\d{2}\.\d{2}\s*\d{2}:\d{2}:\d{2}$")
# 블록 마커.
_BLOCK_MARKER = "국내전용카드"
# 거래일+시각 — 공백이 있거나 없거나 모두 허용.
_DATETIME = re.compile(r"^(\d{4})/(\d{2})/(\d{2})\s*(\d{2}):(\d{2}):(\d{2})$")
# 카드번호 — raw "NNNN-NN**-****-NNNN" 또는 이미 canonical.
_CARD = re.compile(r"^(\d{4})-(?:\d{2}\*\*|\*{4})-\*{4}-(\d{4})$")
# 광역시/도 prefix — 가맹점명 휴리스틱 (주소 line 시작 검출용).
_ADDRESS_PREFIX = re.compile(
    r"^(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)"
)
# 금액 — "12,345원" (콤마 옵션, "원" 필수).
_AMOUNT = re.compile(r"^([\d,]+)원$")
# 가맹점번호 — 정확히 9 자리 숫자 단독.
_MERCHANT_NUMBER = re.compile(r"^\d{9}$")
# 승인번호 — 정확히 8 자리.
_APPROVAL_NUMBER = re.compile(r"^\d{8}$")


class WooriRuleBasedParser(BaseParser):
    """우리카드 매출전표 — 라벨 없는 위치 기반 layout + N-up 분할 (ADR-004/005)."""

    @property
    def tier(self) -> ParserTier:
        return "rule_based"

    async def parse(self, content: bytes, *, filename: str) -> list[ParsedTransaction]:
        column_texts = await asyncio.to_thread(self._extract_per_column_texts, content)
        results: list[ParsedTransaction] = []
        for column_text in column_texts:
            try:
                block_texts = split_by_marker(column_text, _BLOCK_MARKER)
            except ProviderNotDetectedError:
                # 컬럼에 마커 없음 (예: 마지막 페이지 홀수번째 거래만 있는 column 2).
                continue
            for block_text in block_texts:
                lines = [ln for ln in block_text.splitlines() if ln.strip()]
                results.append(self._parse_single_block(lines, filename=filename))

        if not results:
            raise RequiredFieldMissingError(
                "국내전용카드 블록 마커 미발견",
                field="가맹점명",
                reason="no '국내전용카드' marker found in any column",
                tier_attempted="rule_based",
            )
        return results

    @staticmethod
    def _extract_per_column_texts(content: bytes) -> list[str]:
        """페이지마다 N-up 컬럼 개수 감지 후 컬럼별 텍스트 반환.

        - 1-col page → 한 element (page 전체 text)
        - 2-col N-up page → 두 element (좌 컬럼 text, 우 컬럼 text)
        - pdfplumber crop 으로 좌·우 절반 분리 후 각각 ``extract_text()``
        """
        texts: list[str] = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                full_text = page.extract_text() or ""
                col_count = _detect_column_count(full_text)
                if col_count <= 1:
                    texts.append(full_text)
                    continue
                page_width = page.width
                col_width = page_width / col_count
                for ci in range(col_count):
                    bbox = (
                        ci * col_width,
                        0,
                        (ci + 1) * col_width,
                        page.height,
                    )
                    cropped = page.crop(bbox)
                    texts.append(cropped.extract_text() or "")
        return texts

    def _parse_single_block(
        self, block: list[str], *, filename: str
    ) -> ParsedTransaction:
        if len(block) < 12:
            raise RequiredFieldMissingError(
                f"우리카드 블록 line 수 부족 — got {len(block)}, expected >= 12",
                field="가맹점명",
                tier_attempted="rule_based",
            )

        # ── 카드번호 (block[0]) ──
        card_match = _CARD.match(block[0])
        if not card_match:
            raise FormatMismatchError(
                f"우리카드 카드번호 형식 불일치 — got {block[0]!r}",
                field="카드번호_마스킹",
                tier_attempted="rule_based",
            )
        first4, last4 = card_match.groups()
        card_masked = f"{first4}-****-****-{last4}"

        # ── 거래일+시각 (block[1]) ──
        dt_match = _DATETIME.match(block[1])
        if not dt_match:
            raise RequiredFieldMissingError(
                f"우리카드 거래일시 형식 불일치 — got {block[1]!r}",
                field="거래일",
                tier_attempted="rule_based",
            )
        y, mo, d, hh, mm, ss = (int(g) for g in dt_match.groups())
        tx_date = date(y, mo, d)
        tx_time = time(hh, mm, ss)

        # block[2] = 일시불/할부 — ParsedTransaction 미저장. Skip.

        # ── 4-line 금액 (block[3..6]) ──
        amounts = [self._parse_amount(block[3 + i], position=i) for i in range(4)]
        amount_total, service_charge, vat, recycle_deposit = amounts
        if amount_total <= 0:
            raise FormatMismatchError(
                "거래금액이 양수가 아님",
                field="금액",
                tier_attempted="rule_based",
            )

        # 비율 가드 — 부가세 위치 추정 검증. 면세(vat=0) 는 가드 통과.
        vat_layout_ok = vat == 0 or abs(vat - round(amount_total * 10 / 110)) <= 1
        if not vat_layout_ok:
            _log.warning(
                "woori_amount_layout_mismatch",
                filename=filename,
                amount=amount_total,
                vat=vat,
                expected_vat=round(amount_total * 10 / 110),
                reason="line 3 ratio mismatch",
            )

        # ── 승인번호 (block[7]) ──
        approval_no: str | None = block[7] if _APPROVAL_NUMBER.match(block[7]) else None

        # ── 가맹점명 + 주소 + 가맹점번호 ──
        merchant = block[8]
        merchant_number_idx: int | None = None
        for i in range(9, len(block)):
            if _MERCHANT_NUMBER.match(block[i]):
                merchant_number_idx = i
                break
        if merchant_number_idx is None:
            raise RequiredFieldMissingError(
                "가맹점번호 (9 자리) 미발견 — block 구조 변경 의심",
                field="가맹점명",
                tier_attempted="rule_based",
            )
        address_lines = block[9:merchant_number_idx]
        if address_lines and not _ADDRESS_PREFIX.match(address_lines[0]):
            _log.info(
                "woori_address_prefix_unexpected",
                filename=filename,
                first_address_line=address_lines[0],
            )

        supply_amount = amount_total - service_charge - vat - recycle_deposit
        supply_or_none = supply_amount if supply_amount > 0 else None

        vat_confidence: ConfidenceLabel = "low" if not vat_layout_ok else "medium"
        confidence: dict[str, ConfidenceLabel] = {
            "가맹점명": "high",
            "거래일": "high",
            "거래시각": "high",
            "금액": "high",
            "공급가액": "medium" if supply_or_none is not None else "none",
            "부가세": vat_confidence,
            "봉사료": "low",
            "자원순환보증금": "low",
            "승인번호": "high" if approval_no else "none",
            "카드번호_마스킹": "high",
            "업종": "none",
        }

        return ParsedTransaction(
            가맹점명=merchant,
            거래일=tx_date,
            거래시각=tx_time,
            금액=amount_total,
            공급가액=supply_or_none,
            부가세=vat,
            승인번호=approval_no,
            업종=None,
            카드사="woori",
            카드번호_마스킹=card_masked,
            parser_used="rule_based",
            field_confidence=confidence,
        )

    @staticmethod
    def _parse_amount(line: str, *, position: int) -> int:
        m = _AMOUNT.match(line)
        if not m:
            raise FormatMismatchError(
                f"우리카드 금액 line 형식 불일치 — position={position}, line={line!r}",
                field="금액",
                tier_attempted="rule_based",
            )
        return int(m.group(1).replace(",", ""))


def _detect_column_count(text: str) -> int:
    """페이지 텍스트에서 마커 line 의 토큰 수 → N-up 컬럼 개수.

    예: "국내전용카드 국내전용카드" → 2 컬럼. 마커 미발견 시 1 반환 (단일 컬럼).
    """
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if _PAGE_HEADER_TIMESTAMP.match(line):
            continue
        if _BLOCK_MARKER in line:
            return max(line.count(_BLOCK_MARKER), 1)
    return 1
