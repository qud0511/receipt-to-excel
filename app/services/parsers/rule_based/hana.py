"""하나카드 룰 기반 파서 — stub. provider 식별만 하고 OCR Hybrid 로 fallback."""

from __future__ import annotations

from app.domain.parsed_transaction import ParsedTransaction
from app.services.parsers.base import BaseParser, ParserNotImplementedError, ParserTier


class HanaRuleBasedParser(BaseParser):
    @property
    def tier(self) -> ParserTier:
        return "rule_based"

    async def parse(self, content: bytes, *, filename: str) -> ParsedTransaction:
        raise ParserNotImplementedError(
            "hana rule-based parser is a stub",
            reason="provider detected but rule_based implementation deferred",
            tier_attempted="rule_based",
        )
