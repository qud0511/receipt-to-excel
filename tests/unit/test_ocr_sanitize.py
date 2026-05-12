"""Phase 4 사후 회귀 — LLM 응답 sanitize (카드번호 AD-2 canonical 정규화)."""

from __future__ import annotations

from app.services.parsers.ocr_hybrid.sanitize import sanitize_card_masked


def test_llm_returns_nnnn_placeholder_sanitized_to_none() -> None:
    """LLM 의 hallucination — 'NNNN-****-****-NNNN' placeholder 는 None 으로."""
    assert sanitize_card_masked("NNNN-****-****-NNNN") is None
    assert sanitize_card_masked("XXXX-****-****-XXXX") is None
    assert sanitize_card_masked("nnnn-****-****-nnnn") is None  # 소문자도


def test_llm_returns_partial_canonical_kept_as_is() -> None:
    """raw 카드사 형식 (NNNN-NN**-****-NNNN) — canonical 로 변환."""
    # Samsung/KBank/Kakaobank/Woori 등 실 카드사 raw 형식.
    assert sanitize_card_masked("9102-34**-****-5567") == "9102-****-****-5567"
    assert sanitize_card_masked("1234-56**-****-7890") == "1234-****-****-7890"


def test_llm_returns_garbage_card_number_sanitized() -> None:
    """garbage / 미준수 형식 — None."""
    assert sanitize_card_masked("garbage") is None
    assert sanitize_card_masked("1234567890123456") is None  # raw 16자리
    assert sanitize_card_masked("카드번호 미확인") is None
    assert sanitize_card_masked("") is None
    assert sanitize_card_masked(None) is None
    assert sanitize_card_masked(12345) is None  # 비문자열


def test_already_canonical_kept() -> None:
    """이미 canonical 한 값은 그대로 (변형 없음)."""
    assert sanitize_card_masked("1234-****-****-7890") == "1234-****-****-7890"
