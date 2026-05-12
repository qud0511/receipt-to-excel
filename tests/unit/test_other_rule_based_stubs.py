"""Phase 4.1 — hana/lotte stubs + Router fallback 체인 + 구조화 로그.

(우리카드는 Phase 4 보완 단계에서 완전 구현 — ADR-004. 본 파일에서는 stub 검증 제외.)
"""

from __future__ import annotations

from datetime import date

import pytest
import structlog
from app.domain.parsed_transaction import ParsedTransaction
from app.services.parsers.base import (
    BaseParser,
    ParserNotImplementedError,
    ParserTier,
    ProviderNotDetectedError,
)
from app.services.parsers.router import ParserRouter
from app.services.parsers.rule_based.hana import HanaRuleBasedParser
from app.services.parsers.rule_based.lotte import LotteRuleBasedParser

# ── 모의 PDF bytes (provider signature 만 포함, 본문은 stub 동작 검증용) ──────
_HANA_PDF = b"%PDF-1.4\nBT\nhanacard.co.kr footer\nET\n%%EOF"
_LOTTE_PDF = b"%PDF-1.4\nBT\nlottecard.co.kr\nET\n%%EOF"
_UNKNOWN_PDF = b"%PDF-1.4\nBT\nplain invoice text no provider\nET\n%%EOF"


class _OcrStub(BaseParser):
    """Fallback 검증용 OCR Hybrid 스텁."""

    @property
    def tier(self) -> ParserTier:
        return "ocr_hybrid"

    async def parse(self, content: bytes, *, filename: str) -> list[ParsedTransaction]:
        return [
            ParsedTransaction(
                가맹점명="ocr-resolved",
                거래일=date(2026, 1, 1),
                금액=1000,
                parser_used="ocr_hybrid",
                field_confidence={"가맹점명": "medium", "금액": "medium"},
            )
        ]


# ── 1~2) 2 stubs (hana / lotte) 가 ParserNotImplementedError 를 던진다 ──────
async def test_hana_stub_raises_parser_not_implemented() -> None:
    parser = HanaRuleBasedParser()
    with pytest.raises(ParserNotImplementedError):
        await parser.parse(_HANA_PDF, filename="hana.pdf")


async def test_lotte_stub_raises_parser_not_implemented() -> None:
    parser = LotteRuleBasedParser()
    with pytest.raises(ParserNotImplementedError):
        await parser.parse(_LOTTE_PDF, filename="lotte.pdf")


# ── 4) router 가 stub 만나면 OCR Hybrid 로 자동 fallback ──────────────────────
async def test_router_falls_back_to_ocr_hybrid_when_stub_raises() -> None:
    router = ParserRouter(
        rule_based_parsers={"hana": HanaRuleBasedParser()},
        ocr_hybrid_parser=_OcrStub(),
    )
    [result] = await router.parse(_HANA_PDF, filename="hana.pdf")
    assert result.parser_used == "ocr_hybrid"


# ── 5) provider 자체 미식별 → ProviderNotDetectedError ─────────────────────────
async def test_router_raises_provider_not_detected_when_no_match() -> None:
    # provider unknown + OCR 없음 + LLM 비활성 — 분류 사유가 명확히 ProviderNotDetected.
    router = ParserRouter()
    with pytest.raises(ProviderNotDetectedError):
        await router.parse(_UNKNOWN_PDF, filename="unknown.pdf")


# ── 6) fallback 시 구조화 로그에 tier_skipped="rule_based:stub" 기록 ──────────
async def test_log_records_tier_skipped_rule_based_stub_when_fallback() -> None:
    router = ParserRouter(
        rule_based_parsers={"hana": HanaRuleBasedParser()},
        ocr_hybrid_parser=_OcrStub(),
    )
    with structlog.testing.capture_logs() as logs:
        await router.parse(_HANA_PDF, filename="hana.pdf")

    skip_logs = [entry for entry in logs if entry.get("tier_skipped") == "rule_based:stub"]
    assert len(skip_logs) >= 1, f"expected tier_skipped log, got: {logs}"
    assert skip_logs[0].get("provider") == "hana"
