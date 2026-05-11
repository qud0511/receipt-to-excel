"""Phase 3 — ParsedTransaction 검증 (AD-1 immutable / AD-2 canonical / 금액 gt 0 / 4-label)."""

from __future__ import annotations

from datetime import date

import pytest
from app.domain.parsed_transaction import ParsedTransaction
from pydantic import ValidationError


def _base() -> dict[str, object]:
    """공통 valid payload — 각 테스트가 일부 필드만 override."""
    return {
        "가맹점명": "스타벅스",
        "거래일": date(2026, 5, 11),
        "금액": 4500,
        "카드사": "shinhan",
        "parser_used": "rule_based",
        "field_confidence": {"가맹점명": "high", "금액": "high"},
    }


def test_card_number_canonical_format_validates() -> None:
    # AD-2: NNNN-****-****-NNNN canonical.
    obj = ParsedTransaction(**_base(), 카드번호_마스킹="1234-****-****-9999")
    assert obj.카드번호_마스킹 == "1234-****-****-9999"


def test_card_number_rejects_non_canonical() -> None:
    # 16자리 raw / 하이픈 없음 / 별표 위치 다름 — 모두 거부.
    for bad in ["1234999999999999", "1234-5678-9012-3456", "1234****99999999", ""]:
        with pytest.raises(ValidationError):
            ParsedTransaction(**_base(), 카드번호_마스킹=bad)


def test_amount_must_be_positive() -> None:
    for bad in [0, -100, -1]:
        kwargs = _base()
        kwargs["금액"] = bad
        with pytest.raises(ValidationError):
            ParsedTransaction(**kwargs)


def test_field_confidence_only_allows_4_labels() -> None:
    kwargs = _base()
    # 4-label 외 라벨 — ValidationError.
    kwargs["field_confidence"] = {"가맹점명": "uncertain"}
    with pytest.raises(ValidationError):
        ParsedTransaction(**kwargs)


def test_merchant_name_preserves_whitespace_and_case() -> None:
    # AD-1: raw merchant_name 은 strip/normalize/대소문자 변형 금지.
    raw = " STARBUCKS  코리아 "
    kwargs = _base()
    kwargs["가맹점명"] = raw
    obj = ParsedTransaction(**kwargs)
    assert obj.가맹점명 == raw
