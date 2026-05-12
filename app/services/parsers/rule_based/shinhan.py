"""신한카드 매출전표 룰 기반 파서 — pdfplumber 텍스트 추출 + 정규식 매핑.

CLAUDE.md §"특이사항":
- AD-1 가맹점명/업종 raw 값 보존 (strip/normalize 안 함은 본 파서 책임 밖)
- AD-2 카드번호 canonical NNNN-****-****-NNNN 강제
- AD-4 금액 int gt 0
- CLAUDE.md §"성능": 블로킹 pdfplumber 호출은 ``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
import io
import re
from datetime import date, time

import pdfplumber

from app.domain.confidence import ConfidenceLabel
from app.domain.parsed_transaction import ParsedTransaction
from app.services.extraction.confidence_labeler import label_rule_based
from app.services.parsers.base import (
    BaseParser,
    FormatMismatchError,
    ParserTier,
    RequiredFieldMissingError,
)

# 정규식 — 신한카드 매출전표 (합성 fixture + 실 PDF 양쪽 layout, ADR-008).
#
# 합성 fixture (`make_shinhan_receipt`):
#   - 거래일시: YYYY-MM-DD HH:MM:SS (대시, 공백, 초 포함, 라벨 "거래일시:")
#   - 거래금액: ₩XXX,XXX  (라벨 + ₩)
#   - 가맹점명: XXXX      (라벨)
#
# 실 PDF (shinhan_01..12, shinhan_taxi_01..06):
#   - 거래일 YYYY.M.D\x01HH:MM (점, \x01, 초 없음, 라벨 "거래일")  ← 페이지 헤더와 구분 필수
#   - 금액은 라벨 없이 별도 라인 (예: '10,300' \n '원')
#   - 가맹점명은 '가맹점\x01정보' 블록 다음 줄 (라벨 없음, raw \x01 보존)

_CARD_PATTERN = re.compile(r"(\d{4})-\d{2}\*\*-\*\*\*\*-(\d{4})")

# 거래일: 라벨 "거래일" 또는 "거래일시" 강제 → 페이지 출력 시각 (2026.1.2 형식) 오인식 차단.
# 구분자: 대시/점/슬래시. 일-시각 사이: 공백 또는 \x01. 초 옵셔널 (실 PDF "HH:MM" 만 있음).
_DATE_TIME = re.compile(
    r"거래일[시]?[:\s]*(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})[\s\x01]+(\d{2}):(\d{2})(?::(\d{2}))?"
)

# 금액: 라벨 형식 (합성) 우선 → 라벨 없는 멀티라인 (실 PDF) fallback.
_AMOUNT_LABELED = re.compile(r"거래금액[:\s]*₩?\s*([\d,]+)")
_AMOUNT_BARE = re.compile(r"^([\d,]+)\s*\n\s*원\s*$", re.MULTILINE)

# 가맹점: 라벨 형식 (합성) 우선 → "가맹점 정보" 블록 다음 줄 (실 PDF) fallback.
# 실 PDF 의 \x01 는 가맹점명 raw 일부 — AD-1 immutable 로 보존.
_MERCHANT_LABELED = re.compile(r"가맹점명[:\s]*(.+?)\s*$", re.MULTILINE)
_MERCHANT_INFO_BLOCK = re.compile(r"가맹점.정보\s*\n([^\n]+)")

_SUPPLY = re.compile(r"공급가액[:\s]*₩?\s*([\d,]+)")
_VAT = re.compile(r"부가세[:\s]*₩?\s*([\d,]+)")
_APPROVAL = re.compile(r"승인번호[:\s]*(\d{8})")
_CATEGORY = re.compile(r"업종[:\s]*(.+?)\s*$", re.MULTILINE)


class ShinhanRuleBasedParser(BaseParser):
    """신한카드 매출전표 — 텍스트 임베디드 PDF 가정. 스캔본은 OCR Hybrid 가 처리."""

    @property
    def tier(self) -> ParserTier:
        return "rule_based"

    async def parse(self, content: bytes, *, filename: str) -> list[ParsedTransaction]:
        # pdfplumber 는 동기 — async 컨텍스트 차단 방지 (CLAUDE.md §"성능").
        text = await asyncio.to_thread(self._extract_text, content)
        # ADR-005: 신한카드는 영수증당 1 거래 — 단일 결과 list 1 래핑.
        return [self._parse_from_text(text)]

    @staticmethod
    def _extract_text(content: bytes) -> str:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)

    def _parse_from_text(self, text: str) -> ParsedTransaction:
        # 영문 로컬 변수 + 한글 도메인 API 분리 — ruff N806 호환.

        # ── 필수: 거래일 (라벨 강제 — 페이지 출력 시각 오인식 차단) ──
        dt_match = _DATE_TIME.search(text)
        if not dt_match:
            raise RequiredFieldMissingError(
                "거래일시 미발견",
                field="거래일",
                tier_attempted="rule_based",
            )
        y_s, mo_s, d_s, hh_s, mm_s, ss_s = dt_match.groups()
        # 초는 실 PDF 에서 부재 가능 (라벨 "거래일 YYYY.M.D\x01HH:MM" — 초 없음).
        tx_date = date(int(y_s), int(mo_s), int(d_s))
        tx_time = time(int(hh_s), int(mm_s), int(ss_s) if ss_s else 0)

        # ── 필수: 가맹점명 — 라벨 → "가맹점 정보" 블록 fallback (AD-1 raw 보존) ──
        m_match = _MERCHANT_LABELED.search(text) or _MERCHANT_INFO_BLOCK.search(text)
        if not m_match:
            raise RequiredFieldMissingError(
                "가맹점명 미발견",
                field="가맹점명",
                tier_attempted="rule_based",
            )
        merchant = m_match.group(1)

        # ── 필수: 금액 — 라벨 → bare line 양식 (실 PDF) fallback ──
        amt_match = _AMOUNT_LABELED.search(text) or _AMOUNT_BARE.search(text)
        if not amt_match:
            raise RequiredFieldMissingError(
                "거래금액 미발견",
                field="금액",
                tier_attempted="rule_based",
            )
        amount = int(amt_match.group(1).replace(",", ""))
        if amount <= 0:
            raise FormatMismatchError(
                "거래금액이 양수가 아님",
                field="금액",
                tier_attempted="rule_based",
            )

        # ── Optional: 카드번호 (AD-2 canonical 변환) ──
        card_masked: str | None = None
        card_match = _CARD_PATTERN.search(text)
        if card_match:
            first4, last4 = card_match.groups()
            card_masked = f"{first4}-****-****-{last4}"

        # ── Optional 금액 ──
        supply_match = _SUPPLY.search(text)
        supply_amount = int(supply_match.group(1).replace(",", "")) if supply_match else None
        vat_match = _VAT.search(text)
        vat_amount = int(vat_match.group(1).replace(",", "")) if vat_match else None

        # ── Optional 텍스트 ──
        approval_match = _APPROVAL.search(text)
        approval_no = approval_match.group(1) if approval_match else None
        cat_match = _CATEGORY.search(text)
        category = cat_match.group(1) if cat_match else None

        # ── Confidence 라벨링 ──
        # 필수 필드: regex exact match → high.
        # Optional 텍스트 (승인번호/카드번호/업종): 있으면 exact_regex_match → high.
        # Optional 금액 (공급가액/부가세): 있으면 partial_match → medium (다른 필드와 종속).
        confidence: dict[str, ConfidenceLabel] = {
            "가맹점명": "high",
            "거래일": "high",
            "거래시각": "high",
            "금액": "high",
            "승인번호": label_rule_based("exact_regex_match" if approval_no else "missing"),
            "카드번호_마스킹": label_rule_based("exact_regex_match" if card_masked else "missing"),
            "업종": label_rule_based("exact_regex_match" if category else "missing"),
            "공급가액": label_rule_based(
                "partial_match" if supply_amount is not None else "missing"
            ),
            "부가세": label_rule_based("partial_match" if vat_amount is not None else "missing"),
        }

        return ParsedTransaction(
            가맹점명=merchant,
            거래일=tx_date,
            거래시각=tx_time,
            금액=amount,
            공급가액=supply_amount,
            부가세=vat_amount,
            승인번호=approval_no,
            업종=category,
            카드사="shinhan",
            카드번호_마스킹=card_masked,
            parser_used="rule_based",
            field_confidence=confidence,
        )
