"""BaseParser ABC + ParseError 계층 — 모든 추출 tier 의 공통 계약.

CLAUDE.md §"특이사항: 추출 우선순위 — Rule > OCR > LLM, 모두 동일 ParsedTransaction 계약".
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from app.domain.parsed_transaction import ParsedTransaction

ParserTier = Literal["rule_based", "ocr_hybrid", "llm"]


class ParseError(Exception):
    """파서 추출 실패. router 가 다음 tier 로 폴백 결정 시 사용.

    DoD: field/reason/tier_attempted 필드 보유 — 로깅·UI 진단에 모두 사용.
    """

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        reason: str | None = None,
        tier_attempted: ParserTier | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.field = field
        self.reason = reason
        self.tier_attempted = tier_attempted


class ProviderNotDetectedError(ParseError):
    """카드사 자체 식별 실패 — header/footer 어디서도 시그니처 매칭 안 됨."""


class ParserNotImplementedError(ParseError):
    """provider 는 식별됐으나 RuleBased 구현이 stub. router 가 OCR Hybrid 로 fallback."""


class RequiredFieldMissingError(ParseError):
    """추출 시도했으나 필수 필드 (가맹점명/거래일/금액) 결손."""


class FormatMismatchError(ParseError):
    """필드는 추출됐으나 형식이 도메인 검증 (AD-2 canonical 등) 미통과."""


class LLMDisabledError(ParseError):
    """모든 tier 실패 + ``LLM_ENABLED=false`` — UI 가 사용자에게 옵트인 안내."""


class BaseParser(ABC):
    """모든 추출 tier (rule_based / ocr_hybrid / llm) 의 공통 인터페이스."""

    @property
    @abstractmethod
    def tier(self) -> ParserTier:
        """이 파서의 tier 식별자 — ParsedTransaction.parser_used 에 그대로 기록."""

    @abstractmethod
    async def parse(self, content: bytes, *, filename: str) -> ParsedTransaction:
        """raw bytes → ParsedTransaction. 실패 시 ParseError 또는 서브클래스."""
