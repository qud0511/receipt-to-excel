"""Phase 4.4 — OCR Hybrid parser 9 cases.

Docling config + Ollama payload + prompt 디리미터 + Pydantic strict + PII 필터 통합.
"""

from __future__ import annotations

import base64
import io
import json

import pytest
import structlog
from app.core.logging import configure_logging
from app.services.parsers.base import FormatMismatchError
from app.services.parsers.ocr_hybrid.docling_service import default_pipeline_config
from app.services.parsers.ocr_hybrid.ollama_vision_client import build_payload
from app.services.parsers.ocr_hybrid.parser import OCRHybridParser
from app.services.parsers.ocr_hybrid.prompt import (
    DELIM_BEGIN,
    DELIM_END,
    build_user_prompt,
    wrap_ocr_text,
)
from PIL import Image

_VALID_LLM_RESPONSE = {
    "가맹점명": "스타벅스",
    "거래일": "2026-05-10",
    "거래시각": "14:23:11",
    "금액": 4500,
    "공급가액": None,
    "부가세": None,
    "승인번호": "12345678",
    "업종": "음료",
    "카드사": "shinhan",
    "카드번호_마스킹": "1234-****-****-7890",
    "parser_used": "ocr_hybrid",
    "field_confidence": {"가맹점명": "medium", "거래일": "medium", "금액": "medium"},
}


class _MockDocling:
    """Docling stub — 단위 테스트에서 실제 OCR 회피."""

    async def extract_text(self, content: bytes, *, filename: str = "input.pdf") -> str:
        return "이용금액: 4,500원\n가맹점명: 스타벅스"


class _MockOllama:
    """Ollama stub — generate() 가 dict 반환 (인자로 설정 가능)."""

    def __init__(self, response_json: object) -> None:
        self._response_json = response_json

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image: object | None = None,
    ) -> dict[str, object]:
        if isinstance(self._response_json, str):
            return {"response": self._response_json}
        return {"response": json.dumps(self._response_json, ensure_ascii=False)}


# ── 1) Docling pipeline — Korean EasyOCR (v1 자산 회복) ──────────────────────
def test_docling_pipeline_uses_korean_easyocr() -> None:
    config = default_pipeline_config()
    assert "ko" in config.languages
    assert "en" in config.languages
    assert config.force_full_page_ocr is True


# ── 2) Docling pipeline — 무거운 분석 비활성 ───────────────────────────────────
def test_docling_pipeline_disables_heavy_analysis() -> None:
    config = default_pipeline_config()
    assert config.do_table_structure is False
    assert config.do_picture_classification is False
    assert config.do_picture_description is False
    assert config.do_formula_enrichment is False


# ── 3) Ollama payload — PIL Image 주어지면 base64 PNG 포함 ─────────────────────
def test_ollama_payload_includes_image_base64_when_pil_given() -> None:
    img = Image.new("RGB", (10, 10), color="white")
    payload = build_payload(
        model="gemma4",
        system_prompt="sys",
        user_prompt="usr",
        image=img,
    )
    assert len(payload["images"]) == 1
    decoded = base64.b64decode(payload["images"][0])
    # PNG signature: 89 50 4E 47 0D 0A 1A 0A
    assert decoded.startswith(b"\x89PNG\r\n\x1a\n")


# ── 4) Ollama payload — temperature=0.0 (CLAUDE.md §"특이사항") ──────────────
def test_ollama_payload_temperature_zero() -> None:
    payload = build_payload(model="gemma4", system_prompt="s", user_prompt="u")
    assert payload["options"]["temperature"] == 0.0


# ── 5) Ollama payload — format="json" (CLAUDE.md §"특이사항") ────────────────
def test_ollama_format_json_enforced() -> None:
    payload = build_payload(model="gemma4", system_prompt="s", user_prompt="u")
    assert payload["format"] == "json"


# ── 6) Prompt 디리미터로 OCR 텍스트 감쌈 — injection 방어 ─────────────────────
def test_prompt_wraps_ocr_text_in_delimiters() -> None:
    ocr_text = "이용금액: 8,900원\n가맹점: 스타벅스"
    wrapped = wrap_ocr_text(ocr_text)
    assert DELIM_BEGIN in wrapped
    assert DELIM_END in wrapped
    # OCR text 가 디리미터 사이에 위치.
    begin_pos = wrapped.index(DELIM_BEGIN)
    end_pos = wrapped.index(DELIM_END)
    between = wrapped[begin_pos:end_pos]
    assert ocr_text in between

    # build_user_prompt 도 wrap 결과를 포함.
    user = build_user_prompt(ocr_text)
    assert DELIM_BEGIN in user
    assert DELIM_END in user


# ── 7) 추출 결과 Pydantic strict — 잘못된 필드는 FormatMismatchError ──────────
async def test_extracted_fields_validated_against_schema() -> None:
    bad_response = {**_VALID_LLM_RESPONSE, "금액": 0}  # gt=0 위반
    parser = OCRHybridParser(docling=_MockDocling(), ollama=_MockOllama(bad_response))
    with pytest.raises(FormatMismatchError):
        await parser.parse(b"fake-pdf", filename="x.jpg")


# ── 8) Invalid JSON 응답 → FormatMismatchError ────────────────────────────────
async def test_invalid_json_response_raises_parse_error() -> None:
    parser = OCRHybridParser(
        docling=_MockDocling(),
        ollama=_MockOllama("not valid json {{["),
    )
    with pytest.raises(FormatMismatchError):
        await parser.parse(b"fake-pdf", filename="x.jpg")


# ── 9) 한국어 파일명이 로그에 raw 노출 안 됨 — Phase 1 PII 필터 통합 ──────────
async def test_user_facing_filename_redacted_in_logs() -> None:
    buf = io.StringIO()
    configure_logging(stream=buf)

    # session_id+idx 를 contextvars 에 bind — _pii_filter 가 한글 filename 을 마스킹.
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(session_id="sess-abc", idx=0)
    try:
        parser = OCRHybridParser(
            docling=_MockDocling(),
            ollama=_MockOllama(_VALID_LLM_RESPONSE),
        )
        await parser.parse(b"fake", filename="거래내역서_5월.pdf")
    finally:
        structlog.contextvars.clear_contextvars()

    line = buf.getvalue()
    # 한글 raw 파일명이 로그에 그대로 등장하면 안 됨.
    assert "거래내역서" not in line
    # 마스킹된 형태 검증 — session_sess-abc_idx_0.
    assert "session_sess-abc_idx_0" in line
