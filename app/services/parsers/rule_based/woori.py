"""우리카드 매출전표 룰 기반 파서.

ADR-004 §"우리카드 N-up layout 분석" 의 결정 사항:
- 라벨 없는 위치 기반 layout — `국내전용카드` 마커 이후 14~16 line block.
- 4-line 금액 순서 추정: ① 거래금액 ② 봉사료 ③ 부가세 ④ 자원순환보증금.
  근거: 70,000 x 10/110 ≈ 6,364 (line 3 = 부가세) 비율 일치.
- 거래일+시각 붙음 (yyyy/MM/ddHH:mm:ss) — 다른 카드사와 다른 우리카드 특이.
- Confidence: 거래금액=high, 부가세=medium (위치 추정 + 비율 검증), 봉사료/자원순환=low.

Task 2 범위: 단일 transaction 블록 추출 (synthetic + 1-col 실 자료).
Task 3 에서 N-up (2-column) 분할 지원 + 시그니처 list 반환으로 마이그레이션.
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
    RequiredFieldMissingError,
)

_log = structlog.get_logger(__name__)

# 페이지 발행 timestamp — 거래일과 별개. 추출 시 skip.
_PAGE_HEADER_TIMESTAMP = re.compile(r"^\d{4}\.\d{2}\.\d{2}\s*\d{2}:\d{2}:\d{2}$")
# 블록 마커 — N-up 의 좌·우 같은 line 에 반복될 수 있음 ("국내전용카드 국내전용카드").
_BLOCK_MARKER = "국내전용카드"
# 거래일+시각 — 공백이 있거나 없거나 모두 허용 (yyyy/MM/ddHH:mm:ss 또는 yyyy/MM/dd HH:mm:ss).
_DATETIME = re.compile(r"^(\d{4})/(\d{2})/(\d{2})\s*(\d{2}):(\d{2}):(\d{2})$")
# 카드번호 — raw "NNNN-NN**-****-NNNN" 또는 이미 canonical "NNNN-****-****-NNNN".
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
    """우리카드 매출전표 — 라벨 없는 위치 기반 layout (ADR-004)."""

    @property
    def tier(self) -> ParserTier:
        return "rule_based"

    async def parse(self, content: bytes, *, filename: str) -> ParsedTransaction:
        text = await asyncio.to_thread(self._extract_text, content)
        blocks = self._split_into_blocks(text)
        if not blocks:
            raise RequiredFieldMissingError(
                "국내전용카드 블록 마커 미발견",
                field="가맹점명",
                reason="no '국내전용카드' marker found in extracted text",
                tier_attempted="rule_based",
            )
        return self._parse_single_block(blocks[0], filename=filename)

    @staticmethod
    def _extract_text(content: bytes) -> str:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)

    @staticmethod
    def _split_into_blocks(text: str) -> list[list[str]]:
        """`국내전용카드` 마커 단위로 line block 분리.

        Task 2: single-column 가정 — 마커 line 토큰 수와 무관하게 각 line 을 1 token 으로 처리.
        Task 3 에서 2-column N-up 분할 도입 시 별도 splitter 모듈로 분리.
        """
        blocks: list[list[str]] = []
        current: list[str] | None = None
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if _PAGE_HEADER_TIMESTAMP.match(line):
                continue
            # 마커 line — 단독("국내전용카드") 또는 N-up 반복("국내전용카드 국내전용카드").
            if line.replace(_BLOCK_MARKER, "").strip() == "":
                if current is not None:
                    blocks.append(current)
                current = []
                continue
            if current is not None:
                current.append(line)
        if current is not None:
            blocks.append(current)
        return blocks

    def _parse_single_block(self, block: list[str], *, filename: str) -> ParsedTransaction:
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

        # block[2] = 일시불/할부 구분 — 현재 ParsedTransaction 에 저장 필드 없음. Skip.

        # ── 4-line 금액 (block[3..6]) — 거래금액 / 봉사료 / 부가세 / 자원순환보증금 ──
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
                reason="line 3 ratio mismatch — 발행 양식 변경 또는 line 순서 오류 가능",
            )

        # ── 승인번호 (block[7]) ──
        approval_no: str | None = block[7] if _APPROVAL_NUMBER.match(block[7]) else None

        # ── 가맹점명 + 주소 + 가맹점번호 위치 탐색 ──
        # 가맹점명 = block[8], 그 다음 1~2 line 이 주소, 9-자리 line 이 가맹점번호.
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
        # 주소 line 들 (가맹점명 다음 ~ 가맹점번호 직전). 1~2 줄 예상.
        address_lines = block[9:merchant_number_idx]
        if address_lines and not _ADDRESS_PREFIX.match(address_lines[0]):
            # 광역시/도 시작이 아니라면 발행 양식이 바뀐 것 — 경고만 (raise 안 함).
            _log.info(
                "woori_address_prefix_unexpected",
                filename=filename,
                first_address_line=address_lines[0],
            )

        # 공급가액 = 거래금액 - 봉사료 - 부가세 - 자원순환보증금 (가드 식과 동일).
        supply_amount = amount_total - service_charge - vat - recycle_deposit
        # AD-4 gt=0 — None 처리 (음수/0 인 경우 저장하지 않음).
        supply_or_none = supply_amount if supply_amount > 0 else None

        # ── Confidence 정책 (ADR-004) ──
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
