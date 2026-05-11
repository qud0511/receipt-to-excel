"""LLM-only parser prompt — OCR 없이 raw 이미지/문서로 직접 추출 요청.

OCR Hybrid 와 system prompt 는 공유 (디리미터 패턴 동일). user prompt 만 분기.
"""

from __future__ import annotations

from app.services.parsers.ocr_hybrid.prompt import get_system_prompt


def get_llm_only_system_prompt() -> str:
    """OCR Hybrid 와 동일한 system prompt 재사용 — JSON 스키마 + 디리미터 정책 단일 출처."""
    return get_system_prompt()


def build_llm_only_user_prompt(filename: str) -> str:
    """OCR 텍스트 없이 raw 이미지/문서를 LLM 에 보내는 user prompt."""
    return (
        f"첨부된 영수증({filename})에서 거래 정보를 JSON 으로 추출하세요. "
        "OCR 결과가 제공되지 않으므로 이미지를 직접 분석해야 합니다."
    )
