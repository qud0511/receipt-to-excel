"""Phase 3 — ConfidenceLabeler 의 4-label 매핑 정책 (룰/OCR/LLM/사용자)."""

from __future__ import annotations

from app.services.extraction.confidence_labeler import (
    label_llm,
    label_ocr,
    label_rule_based,
    label_user_edit,
)


# ── 룰 기반 ──────────────────────────────────────────────────────────────────
def test_rule_based_exact_match_returns_high() -> None:
    assert label_rule_based("exact_regex_match") == "high"


def test_rule_based_partial_returns_medium() -> None:
    assert label_rule_based("partial_match") == "medium"


def test_rule_based_missing_returns_none() -> None:
    assert label_rule_based("missing") == "none"


# ── OCR Hybrid (EasyOCR 0~1 confidence) ───────────────────────────────────────
def test_ocr_threshold_mapping_high_at_0_85() -> None:
    assert label_ocr(0.85) == "high"
    assert label_ocr(0.95) == "high"
    assert label_ocr(1.0) == "high"


def test_ocr_threshold_mapping_medium_at_0_60() -> None:
    assert label_ocr(0.60) == "medium"
    assert label_ocr(0.84) == "medium"


def test_ocr_threshold_mapping_low_at_0_30() -> None:
    assert label_ocr(0.30) == "low"
    assert label_ocr(0.59) == "low"


def test_ocr_below_0_30_returns_none() -> None:
    assert label_ocr(0.29) == "none"
    assert label_ocr(0.0) == "none"


# ── LLM (모델 자기보고 또는 후처리 정규식 검증) ────────────────────────────────
def test_llm_regex_validates_returns_medium() -> None:
    assert label_llm("regex_validates") == "medium"
    assert label_llm("regex_fails_but_present") == "low"
    assert label_llm("missing_or_null") == "none"


# ── 사용자 편집 — AD-1 정신, 사용자 권위 ──────────────────────────────────────
def test_user_edit_overrides_to_high() -> None:
    assert label_user_edit() == "high"
