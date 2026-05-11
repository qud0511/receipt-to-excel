"""OCRHybridParser — Docling OCR + Ollama Vision → ParsedTransaction.

CLAUDE.md §"특이사항: Hallucination 방어 4단": (1) JSON 파싱 → (2) Pydantic strict →
(3) 정규식 후처리 (Phase 4.5 postprocessor) → (4) validate_and_fix (Phase 6+).
"""

from __future__ import annotations

import json
from typing import Protocol

import structlog
from pydantic import ValidationError

from app.domain.parsed_transaction import ParsedTransaction
from app.services.parsers.base import (
    BaseParser,
    FormatMismatchError,
    ParserTier,
)

_log = structlog.get_logger(__name__)


class _DoclingLike(Protocol):
    async def extract_text(self, content: bytes) -> str: ...


class _OllamaLike(Protocol):
    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image: object | None = None,
    ) -> dict[str, object]: ...


class OCRHybridParser(BaseParser):
    def __init__(
        self,
        *,
        docling: _DoclingLike,
        ollama: _OllamaLike,
    ) -> None:
        self._docling = docling
        self._ollama = ollama

    @property
    def tier(self) -> ParserTier:
        return "ocr_hybrid"

    async def parse(self, content: bytes, *, filename: str) -> ParsedTransaction:
        # PII 마스킹은 structlog._pii_filter 가 filename+session_id+idx 동반 시 발동 —
        # session_id/idx 는 호출자(router/job runner) 가 contextvars 로 bind.
        _log.info("ocr_hybrid_parse_start", filename=filename)

        ocr_text = await self._docling.extract_text(content)

        # Hallucination 방어 1단: prompt 디리미터.
        from app.services.parsers.ocr_hybrid.prompt import (
            build_user_prompt,
            get_system_prompt,
        )

        response = await self._ollama.generate(
            system_prompt=get_system_prompt(),
            user_prompt=build_user_prompt(ocr_text),
            image=None,
        )

        raw = response.get("response", response)
        if isinstance(raw, str):
            try:
                extracted = json.loads(raw)
            except json.JSONDecodeError as e:
                # Hallucination 방어 1단 실패 — JSON 파싱.
                raise FormatMismatchError(
                    "LLM JSON 응답 파싱 실패",
                    tier_attempted="ocr_hybrid",
                    reason=str(e),
                ) from e
        else:
            extracted = raw

        if not isinstance(extracted, dict):
            raise FormatMismatchError(
                "LLM 응답이 dict 아님",
                tier_attempted="ocr_hybrid",
                reason=f"type={type(extracted).__name__}",
            )

        # parser_used 는 항상 우리가 결정 — LLM 의 자기보고 신뢰 금지.
        extracted["parser_used"] = "ocr_hybrid"
        extracted.setdefault("field_confidence", {})

        # Hallucination 방어 2단: Pydantic strict.
        try:
            return ParsedTransaction.model_validate(extracted)
        except ValidationError as e:
            raise FormatMismatchError(
                "ParsedTransaction strict 검증 실패",
                tier_attempted="ocr_hybrid",
                reason=str(e),
            ) from e
