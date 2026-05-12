"""케이뱅크 카드 매출 전표 룰 기반 파서.

사양 (synthesis/05 §Phase 4 KBank):
- 거래금액 `[\\d,]+ 원` (숫자와 "원" 사이 공백 강제)
- 공급가액 / 부가세 필드 부재 → None + confidence "none"
- 업종 값 존재 시 → confidence "medium" (partial_match)
- 거래일시 `YYYY/MM/DD HH:MM:SS` → 거래일 + 거래시각 분리
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

_CARD = re.compile(r"(\d{4})-\d{2}\*\*-\*\*\*\*-(\d{4})")
_DATE_TIME = re.compile(r"(\d{4})/(\d{2})/(\d{2})\s+(\d{2}):(\d{2}):(\d{2})")
_APPROVAL = re.compile(r"승인번호[:\s]*(\d{8})")
# 사양: 숫자와 "원" 사이 공백 1개 이상 (\s+).
_AMOUNT = re.compile(r"거래금액[:\s]*([\d,]+)\s+원")
_MERCHANT = re.compile(r"가맹점명[:\s]*(.+?)\s*$", re.MULTILINE)
_CATEGORY = re.compile(r"업종[:\s]*(.+?)\s*$", re.MULTILINE)


class KBankRuleBasedParser(BaseParser):
    @property
    def tier(self) -> ParserTier:
        return "rule_based"

    async def parse(self, content: bytes, *, filename: str) -> list[ParsedTransaction]:
        text = await asyncio.to_thread(self._extract_text, content)
        # ADR-005: 케이뱅크는 영수증당 1 거래 — 단일 결과 list 1 래핑.
        return [self._parse_from_text(text)]

    @staticmethod
    def _extract_text(content: bytes) -> str:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)

    def _parse_from_text(self, text: str) -> ParsedTransaction:
        dt_match = _DATE_TIME.search(text)
        if not dt_match:
            raise RequiredFieldMissingError(
                "거래일시 미발견",
                field="거래일",
                tier_attempted="rule_based",
            )
        y, mo, d, hh, mm, ss = (int(g) for g in dt_match.groups())
        tx_date = date(y, mo, d)
        tx_time = time(hh, mm, ss)

        m_match = _MERCHANT.search(text)
        if not m_match:
            raise RequiredFieldMissingError(
                "가맹점명 미발견",
                field="가맹점명",
                tier_attempted="rule_based",
            )
        merchant = m_match.group(1)

        amt_match = _AMOUNT.search(text)
        if not amt_match:
            raise RequiredFieldMissingError(
                "거래금액 미발견",
                field="금액",
                tier_attempted="rule_based",
            )
        amount = int(amt_match.group(1).replace(",", ""))
        if amount <= 0:
            raise FormatMismatchError(
                "금액이 양수가 아님",
                field="금액",
                tier_attempted="rule_based",
            )

        card_masked: str | None = None
        card_match = _CARD.search(text)
        if card_match:
            first4, last4 = card_match.groups()
            card_masked = f"{first4}-****-****-{last4}"

        approval_match = _APPROVAL.search(text)
        approval_no = approval_match.group(1) if approval_match else None

        cat_match = _CATEGORY.search(text)
        category = cat_match.group(1) if cat_match else None

        confidence: dict[str, ConfidenceLabel] = {
            "가맹점명": "high",
            "거래일": "high",
            "거래시각": "high",
            "금액": "high",
            "승인번호": label_rule_based("exact_regex_match" if approval_no else "missing"),
            "카드번호_마스킹": label_rule_based("exact_regex_match" if card_masked else "missing"),
            # KBank: 업종 값 존재 시 medium (partial_match) — 사양 명시.
            "업종": label_rule_based("partial_match" if category else "missing"),
            # KBank: 공급가액/부가세 필드 부재 → 항상 none.
            "공급가액": "none",
            "부가세": "none",
        }

        return ParsedTransaction(
            가맹점명=merchant,
            거래일=tx_date,
            거래시각=tx_time,
            금액=amount,
            공급가액=None,
            부가세=None,
            승인번호=approval_no,
            업종=category,
            카드사="kbank",
            카드번호_마스킹=card_masked,
            parser_used="rule_based",
            field_confidence=confidence,
        )
