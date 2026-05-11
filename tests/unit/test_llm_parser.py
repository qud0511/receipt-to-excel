"""Phase 4.6 — LLM-only parser 3 케이스 (opt-in fallback)."""

from __future__ import annotations

import json

import pytest
from app.domain.parsed_transaction import ParsedTransaction
from app.services.parsers.base import LLMDisabledError
from app.services.parsers.llm.llm_parser import LLMOnlyParser

_VALID_RESPONSE = {
    "가맹점명": "스타벅스",
    "거래일": "2026-05-10",
    "거래시각": "14:23:11",
    "금액": 4500,
    "카드사": "unknown",
    "field_confidence": {"가맹점명": "low", "거래일": "low", "금액": "low"},
}


class _MockOllama:
    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image: object | None = None,
    ) -> dict[str, object]:
        return {"response": json.dumps(_VALID_RESPONSE, ensure_ascii=False)}


# ── 1) LLM disabled 기본값 — 인스턴스화 자체가 차단됨 ─────────────────────────
def test_llm_parser_skipped_when_llm_disabled() -> None:
    # CLAUDE.md §"보안": LLM_ENABLED=false 면 LLM 객체 생성 자체 금지.
    with pytest.raises(LLMDisabledError):
        LLMOnlyParser(ollama=_MockOllama(), enabled=False)


# ── 2) same output schema — ParsedTransaction 계약 동일 ──────────────────────
async def test_llm_parser_uses_same_output_schema() -> None:
    parser = LLMOnlyParser(ollama=_MockOllama(), enabled=True)
    result = await parser.parse(b"fake", filename="x.pdf")
    assert isinstance(result, ParsedTransaction)
    assert result.가맹점명 == "스타벅스"
    assert result.금액 == 4500


# ── 3) parser_used="llm" 강제 (LLM 응답이 다른 값을 주장해도 우리가 결정) ──────
async def test_llm_parser_records_parser_used_llm() -> None:
    parser = LLMOnlyParser(ollama=_MockOllama(), enabled=True)
    result = await parser.parse(b"fake", filename="x.pdf")
    assert result.parser_used == "llm"
