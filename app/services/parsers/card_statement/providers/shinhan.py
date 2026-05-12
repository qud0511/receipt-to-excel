"""Shinhan 카드 사용내역 — XLSX/CSV 공통 row → ParsedTransaction 매핑.

신한카드 다운로드 양식 가정 (synthetic 합성에 기반, 실 자료 입수 후 보강):
    A=거래일자 B=거래시각 C=가맹점명 D=업종 E=거래금액 F=승인번호 G=카드번호

CLAUDE.md 보안: 카드번호는 마스킹 형식만 영속 (AD-2 canonical).
"""

from __future__ import annotations

import re
from datetime import date, datetime, time
from typing import Any

from app.domain.confidence import ConfidenceLabel
from app.domain.parsed_transaction import ParsedTransaction

# AD-2 canonical: NNNN-****-****-NNNN.
_CARD_MASKED_PATTERN = re.compile(r"(\d{4})-\d{2}\*\*-\*\*\*\*-(\d{4})")
# 거래일자: YYYY-MM-DD 또는 YYYY/MM/DD 또는 YYYY.MM.DD.
_DATE_PATTERN = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")
# 거래시각: HH:MM[:SS]. 초 옵셔널.
_TIME_PATTERN = re.compile(r"(\d{2}):(\d{2})(?::(\d{2}))?")


def parse_shinhan_row(row: dict[str, Any]) -> ParsedTransaction:
    """헤더-값 dict 한 row → ParsedTransaction. 필수 필드 누락 시 ValueError."""
    merchant = _str_required(row, "가맹점명")
    tx_date = _parse_date(_str_required(row, "거래일자"))
    tx_time = _parse_time(_str_required(row, "거래시각"))
    amount = _amount_required(row, "거래금액")

    business_category = _str_optional(row, "업종")
    approval_no = _str_optional(row, "승인번호")
    card_masked = _canonicalize_card(_str_optional(row, "카드번호"))

    confidence: dict[str, ConfidenceLabel] = {
        "가맹점명": "high",
        "거래일": "high",
        "거래시각": "high",
        "금액": "high",
        "업종": "high" if business_category else "none",
        "승인번호": "high" if approval_no else "none",
        "카드번호_마스킹": "high" if card_masked else "none",
    }

    return ParsedTransaction(
        가맹점명=merchant,
        거래일=tx_date,
        거래시각=tx_time,
        금액=amount,
        승인번호=approval_no,
        업종=business_category,
        카드사="shinhan",
        카드번호_마스킹=card_masked,
        parser_used="rule_based",
        field_confidence=confidence,
    )


def _str_required(row: dict[str, Any], key: str) -> str:
    val = row.get(key)
    if val is None or str(val).strip() == "":
        raise ValueError(f"필수 컬럼 누락: {key}")
    return str(val).strip()


def _str_optional(row: dict[str, Any], key: str) -> str | None:
    val = row.get(key)
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _amount_required(row: dict[str, Any], key: str) -> int:
    val = row.get(key)
    if val is None:
        raise ValueError(f"필수 컬럼 누락: {key}")
    if isinstance(val, int):
        amount = val
    elif isinstance(val, float):
        amount = int(val)
    else:
        # "12,000" 같은 문자열 흡수.
        cleaned = str(val).strip().replace(",", "").replace("원", "").strip()
        amount = int(cleaned)
    if amount <= 0:
        raise ValueError(f"금액이 양수가 아님: {amount}")
    return amount


def _parse_date(raw: str) -> date:
    # datetime 이 string 으로 들어온 경우 + ISO 양식 모두 처리.
    match = _DATE_PATTERN.search(raw)
    if not match:
        # openpyxl 이 date 객체로 변환한 경우는 caller 가 isoformat() 으로 전달했을 것.
        try:
            return datetime.fromisoformat(raw).date()
        except ValueError as e:
            raise ValueError(f"거래일자 파싱 실패: {raw}") from e
    y, mo, d = (int(g) for g in match.groups())
    return date(y, mo, d)


def _parse_time(raw: str) -> time:
    match = _TIME_PATTERN.search(raw)
    if not match:
        raise ValueError(f"거래시각 파싱 실패: {raw}")
    hh, mm = int(match.group(1)), int(match.group(2))
    ss = int(match.group(3)) if match.group(3) else 0
    return time(hh, mm, ss)


def _canonicalize_card(raw: str | None) -> str | None:
    """AD-2: NNNN-NN**-****-NNNN → NNNN-****-****-NNNN canonical."""
    if raw is None:
        return None
    match = _CARD_MASKED_PATTERN.match(raw)
    if not match:
        return None
    first4, last4 = match.groups()
    return f"{first4}-****-****-{last4}"
