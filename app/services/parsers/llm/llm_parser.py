"""LLM-only parser — RuleBased/OCR Hybrid 가 모두 실패했을 때 마지막 fallback.

CLAUDE.md §"보안": ``LLM_ENABLED=false`` 면 인스턴스화 자체를 차단 (defence-in-depth).
"""

from __future__ import annotations

import json
from typing import Protocol

import structlog
from PIL.Image import Image as PILImage
from pydantic import ValidationError

from app.domain.parsed_transaction import ParsedTransaction
from app.services.parsers.base import (
    BaseParser,
    FormatMismatchError,
    LLMDisabledError,
    ParserTier,
)
from app.services.parsers.llm.prompt import (
    build_llm_only_user_prompt,
    get_llm_only_system_prompt,
)

_log = structlog.get_logger(__name__)


class _OllamaLike(Protocol):
    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image: PILImage | None = None,
    ) -> dict[str, object]: ...


class LLMOnlyParser(BaseParser):
    """OCR 없이 raw 이미지/문서를 LLM 에 직접 보내 추출.

    인스턴스화는 ``enabled=True`` 일 때만 허용 — 런타임에 잠재적 LLM 호출 자체를
    객체 생명주기 차원에서 차단 (CLAUDE.md §"보안: LLM_ENABLED").
    """

    def __init__(self, *, ollama: _OllamaLike, enabled: bool) -> None:
        if not enabled:
            raise LLMDisabledError(
                "LLM_ENABLED=false — LLMOnlyParser 인스턴스화 금지",
                reason="defence-in-depth: opt-in fallback only",
                tier_attempted="llm",
            )
        self._ollama = ollama

    @property
    def tier(self) -> ParserTier:
        return "llm"

    async def parse(self, content: bytes, *, filename: str) -> list[ParsedTransaction]:
        _log.info("llm_only_parse_start", filename=filename)

        response = await self._ollama.generate(
            system_prompt=get_llm_only_system_prompt(),
            user_prompt=build_llm_only_user_prompt(filename),
            image=None,
        )

        raw = response.get("response", response)
        if isinstance(raw, str):
            try:
                extracted = json.loads(raw)
            except json.JSONDecodeError as e:
                raise FormatMismatchError(
                    "LLM JSON 응답 파싱 실패",
                    tier_attempted="llm",
                    reason=str(e),
                ) from e
        else:
            extracted = raw

        if not isinstance(extracted, dict):
            raise FormatMismatchError(
                "LLM 응답이 dict 아님",
                tier_attempted="llm",
                reason=f"type={type(extracted).__name__}",
            )

        # parser_used 는 LLM 의 자기보고 신뢰 금지 — 우리가 결정.
        extracted["parser_used"] = "llm"
        extracted.setdefault("field_confidence", {})

        # Hallucination 방어 3단: 카드번호 sanitize (OCR Hybrid 와 동일 로직 재사용).
        from app.services.parsers.ocr_hybrid.sanitize import sanitize_card_masked

        if "카드번호_마스킹" in extracted:
            extracted["카드번호_마스킹"] = sanitize_card_masked(extracted.get("카드번호_마스킹"))

        try:
            tx = ParsedTransaction.model_validate(extracted)
        except ValidationError as e:
            raise FormatMismatchError(
                "ParsedTransaction strict 검증 실패",
                tier_attempted="llm",
                reason=str(e),
            ) from e
        # ADR-005: LLM-only 는 단일 결과 list 1 래핑.
        return [tx]
