"""삼성카드 매출전표 룰 기반 파서.

사양 (synthesis/05 §Phase 4 Samsung):
- 이용금액 합계 → 금액 (= 최종 청구액)
- 이용금액 → 공급가액
- 부가세 → 부가세
- 거래일자 `YYYY/MM/DD HH:MM:SS` → 거래일 + 거래시각 분리
- 업종 미기재 → None + confidence "none"
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
# "이용금액 합계" 가 먼저 — "이용금액" 부분 일치를 피하기 위해 명시적 "합계" 라벨.
_AMOUNT_TOTAL = re.compile(r"이용금액\s*합계[:\s]*([\d,]+)\s*원")
_USAGE = re.compile(r"이용금액[:\s]*([\d,]+)\s*원")
_VAT = re.compile(r"부가세[:\s]*([\d,]+)\s*원")
_MERCHANT = re.compile(r"가맹점명[:\s]*(.+?)\s*$", re.MULTILINE)


class SamsungRuleBasedParser(BaseParser):
    @property
    def tier(self) -> ParserTier:
        return "rule_based"

    async def parse(self, content: bytes, *, filename: str) -> ParsedTransaction:
        text = await asyncio.to_thread(self._extract_text, content)
        return self._parse_from_text(text)

    @staticmethod
    def _extract_text(content: bytes) -> str:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)

    def _parse_from_text(self, text: str) -> ParsedTransaction:
        # 거래일자 분리.
        dt_match = _DATE_TIME.search(text)
        if not dt_match:
            raise RequiredFieldMissingError(
                "거래일자 미발견",
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

        # 금액 = 이용금액 합계 (최종 청구액). "이용금액" 단독 매치는 공급가액.
        total_match = _AMOUNT_TOTAL.search(text)
        if not total_match:
            raise RequiredFieldMissingError(
                "이용금액 합계 미발견",
                field="금액",
                tier_attempted="rule_based",
            )
        amount = int(total_match.group(1).replace(",", ""))
        if amount <= 0:
            raise FormatMismatchError(
                "금액이 양수가 아님",
                field="금액",
                tier_attempted="rule_based",
            )

        # 공급가액 = 이용금액. "이용금액 합계" 와 중첩 매치 회피 위해 합계 라인 제거 후 검색.
        text_wo_total = _AMOUNT_TOTAL.sub("", text, count=1)
        usage_match = _USAGE.search(text_wo_total)
        supply_amount = int(usage_match.group(1).replace(",", "")) if usage_match else None

        vat_match = _VAT.search(text)
        vat_amount = int(vat_match.group(1).replace(",", "")) if vat_match else None

        approval_match = _APPROVAL.search(text)
        approval_no = approval_match.group(1) if approval_match else None

        card_masked: str | None = None
        card_match = _CARD.search(text)
        if card_match:
            first4, last4 = card_match.groups()
            card_masked = f"{first4}-****-****-{last4}"

        # Samsung 은 업종 미기재 (사양 명시).
        confidence: dict[str, ConfidenceLabel] = {
            "가맹점명": "high",
            "거래일": "high",
            "거래시각": "high",
            "금액": "high",
            "승인번호": label_rule_based("exact_regex_match" if approval_no else "missing"),
            "카드번호_마스킹": label_rule_based("exact_regex_match" if card_masked else "missing"),
            "공급가액": label_rule_based(
                "partial_match" if supply_amount is not None else "missing"
            ),
            "부가세": label_rule_based("partial_match" if vat_amount is not None else "missing"),
            "업종": "none",
        }

        return ParsedTransaction(
            가맹점명=merchant,
            거래일=tx_date,
            거래시각=tx_time,
            금액=amount,
            공급가액=supply_amount,
            부가세=vat_amount,
            승인번호=approval_no,
            업종=None,
            카드사="samsung",
            카드번호_마스킹=card_masked,
            parser_used="rule_based",
            field_confidence=confidence,
        )
