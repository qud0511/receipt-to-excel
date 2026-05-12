"""LLM 응답 post-validation — AD-2 canonical 카드번호 sanitize.

CLAUDE.md §"특이사항: Hallucination 방어 4단" 의 3단 (정규식 후처리) 의 일반화 버전.
Kakaobank postprocessor 와 별개 — 모든 OCR Hybrid 응답에 적용.

전략 (카드번호_마스킹):
1. None / 빈 문자열 → None
2. placeholder 패턴 (NNNN/XXXX) → None
3. 이미 canonical (NNNN-****-****-NNNN) → 그대로
4. partial canonical (NNNN-NN**-****-NNNN) → canonical 로 변환
5. 그 외 (garbage / 한국어 텍스트 / 형식 미준수) → None
"""

from __future__ import annotations

import re

# AD-2 canonical — pydantic ParsedTransaction.카드번호_마스킹 의 pattern.
_CANONICAL = re.compile(r"^\d{4}-\*{4}-\*{4}-\d{4}$")
# Raw 카드사 형식 (Samsung/KBank/Kakaobank 가 그대로 출력): NNNN-NN**-****-NNNN.
_PARTIAL_CANONICAL = re.compile(r"^(\d{4})-\d{2}\*\*-\*\*\*\*-(\d{4})$")
# Placeholder — LLM hallucination 의 전형. NNNN/XXXX 등 영문 letter.
_PLACEHOLDER = re.compile(r"^[A-Za-z]{4}-\*{4}-\*{4}-[A-Za-z]{4}$")


def sanitize_card_masked(value: object) -> str | None:
    """LLM 의 카드번호_마스킹 응답을 AD-2 canonical 로 정규화 또는 None.

    호출자(OCRHybridParser/LLMOnlyParser) 가 ParsedTransaction.model_validate 직전 사용.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    v = value.strip()
    if not v:
        return None
    if _PLACEHOLDER.match(v):
        return None
    if _CANONICAL.match(v):
        return v
    partial = _PARTIAL_CANONICAL.match(v)
    if partial:
        first4, last4 = partial.groups()
        return f"{first4}-****-****-{last4}"
    return None
