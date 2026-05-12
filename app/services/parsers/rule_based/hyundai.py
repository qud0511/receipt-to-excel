"""현대카드 룰 기반 파서 — stub.

ADR-005 §"hyundai 라우팅" — 현재 확보된 실 자료(`hyundai_01.pdf`)는 이미지 PDF
(텍스트 임베딩 부재). RuleBased 진입 불가 → OCR Hybrid 경로로 폴백.

향후 텍스트 임베디드 hyundai 매출전표 확보 시 본 stub 을 완전 구현으로 격상.
시그니처 패턴(예상): "현대카드", "Hyundai Card", "현대카드 매출전표".
"""

from __future__ import annotations

from app.domain.parsed_transaction import ParsedTransaction
from app.services.parsers.base import BaseParser, ParserNotImplementedError, ParserTier


class HyundaiRuleBasedParser(BaseParser):
    @property
    def tier(self) -> ParserTier:
        return "rule_based"

    async def parse(self, content: bytes, *, filename: str) -> list[ParsedTransaction]:
        raise ParserNotImplementedError(
            "hyundai rule-based parser is a stub",
            reason="텍스트 임베디드 hyundai 매출전표 미확보 — 이미지 PDF 는 OCR Hybrid 경로",
            tier_attempted="rule_based",
        )
