"""4-label 매핑 정책 — 룰 / OCR / LLM / 사용자 편집.

synthesis/04 §3.3 의 ConfidenceLabel 정책을 단일 파일로 묶음. 추출 tier 별로 별도 함수를
export 해 호출자가 자기 컨텍스트에 맞게 선택. 통합 진입점은 후속에서 도입 가능.

UI 색상 코딩의 단일 진실의 출처 — 라벨 → 색 매핑이 후속에서 바뀌어도 본 모듈만 영향.
"""

from __future__ import annotations

from typing import Literal

from app.domain.confidence import ConfidenceLabel

RuleBasedMode = Literal["exact_regex_match", "partial_match", "missing"]
LLMMode = Literal["regex_validates", "regex_fails_but_present", "missing_or_null"]

# 룰 기반: 정규식이 카드사 규격에 exact 매치하면 high, 일부 결손 보충은 medium.
_RULE_BASED_LABEL: dict[RuleBasedMode, ConfidenceLabel] = {
    "exact_regex_match": "high",
    "partial_match": "medium",
    "missing": "none",
}

# LLM: 자기보고가 정규식을 통과하면 medium (rule_based 보다 낮음 — 검증 강도 차이).
_LLM_LABEL: dict[LLMMode, ConfidenceLabel] = {
    "regex_validates": "medium",
    "regex_fails_but_present": "low",
    "missing_or_null": "none",
}

# OCR Hybrid: EasyOCR confidence 0~1 → 4 단계. 내림차순 순회로 첫 매치 라벨.
_OCR_THRESHOLDS: tuple[tuple[float, ConfidenceLabel], ...] = (
    (0.85, "high"),
    (0.60, "medium"),
    (0.30, "low"),
)


def label_rule_based(mode: RuleBasedMode) -> ConfidenceLabel:
    return _RULE_BASED_LABEL[mode]


def label_ocr(confidence: float) -> ConfidenceLabel:
    """EasyOCR confidence 점수를 4-label 로. < 0.30 은 none (사실상 신뢰 불가)."""
    for threshold, lbl in _OCR_THRESHOLDS:
        if confidence >= threshold:
            return lbl
    return "none"


def label_llm(mode: LLMMode) -> ConfidenceLabel:
    return _LLM_LABEL[mode]


def label_user_edit() -> ConfidenceLabel:
    """사용자가 수정한 필드는 항상 high — AD-1 정신 (사용자 권위)."""
    return "high"
