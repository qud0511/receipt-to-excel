"""ParserRouter — provider 감지 + tier 라우팅.

CLAUDE.md §"특이사항: 추출 우선순위 — RuleBased > OCR Hybrid > LLM-only".
"""

from __future__ import annotations

import structlog

from app.domain.parsed_transaction import CardProvider, ParsedTransaction
from app.services.parsers.base import (
    BaseParser,
    LLMDisabledError,
    ParseError,
    ParserNotImplementedError,
    ProviderNotDetectedError,
    RequiredFieldMissingError,
)
from app.services.parsers.pdf_text_probe import is_text_embedded

_log = structlog.get_logger(__name__)

# Provider 시그니처 — header/footer 의 URL 또는 한글 카드사명.
# bytes 기준 매칭 — UTF-8 한글 raw bytes 도 포함.
_PROVIDER_SIGNATURES: dict[CardProvider, tuple[bytes, ...]] = {
    "shinhan": (b"shinhancard.com", "신한카드".encode()),
    "hana": (b"hanacard.co.kr", "하나카드".encode()),
    "samsung": (b"samsungcard.com", "삼성카드".encode()),
    "woori": (b"wooricard.com", "우리카드".encode()),
    "lotte": (b"lottecard.co.kr", "롯데카드".encode()),
    "kbank": (b"kbank.com", "케이뱅크 카드 매출 전표".encode(), "케이뱅크".encode()),
    "kakaobank": (b"kakaobank", "카드매출 온라인전표".encode()),
}

# 우리카드 N-up 발행본은 본문에 브랜드명 자체가 없음 (ADR-004). 이중 게이트로 보완:
#   ① 파일명 hint (woori_ prefix 또는 "우리카드" 포함)
#   ② 텍스트 fingerprint (블록 마커 "국내전용카드")
# CLAUDE.md §"외부 입력 신뢰 금지" 분석: 파일명은 routing hint 일 뿐 인증/권한과 무관.
# 두 게이트가 동시 매칭되어야 woori 로 라우팅 → 단일 hint 위·변조 공격 차단.
_WOORI_BLOCK_MARKER = "국내전용카드".encode()


def _matches_woori_nup(content: bytes, filename: str) -> bool:
    fn_lower = filename.lower()
    filename_hint = fn_lower.startswith("woori") or "우리카드" in filename
    fingerprint = _WOORI_BLOCK_MARKER in content
    return filename_hint and fingerprint


def detect_provider(content: bytes, filename: str = "") -> CardProvider:
    """raw bytes 안의 카드사 시그니처 검색. 미식별 → "unknown".

    ``filename`` 은 woori N-up 이중 게이트(ADR-004)에만 사용. 다른 provider 는 무관.
    """
    for provider, signatures in _PROVIDER_SIGNATURES.items():
        for sig in signatures:
            if sig in content:
                return provider
    if _matches_woori_nup(content, filename):
        return "woori"
    return "unknown"


class ParserRouter:
    """tier 선택 — RuleBased (provider known + text embedded) > OCR Hybrid > LLM.

    LLM 폴백은 ``llm_enabled=True`` 일 때만 (CLAUDE.md §"보안": LLM_ENABLED 명시 제어).
    """

    def __init__(
        self,
        *,
        rule_based_parsers: dict[CardProvider, BaseParser] | None = None,
        ocr_hybrid_parser: BaseParser | None = None,
        llm_parser: BaseParser | None = None,
        llm_enabled: bool = False,
    ) -> None:
        self._rule_parsers: dict[CardProvider, BaseParser] = rule_based_parsers or {}
        self._ocr_parser = ocr_hybrid_parser
        self._llm_parser = llm_parser
        self._llm_enabled = llm_enabled

    @staticmethod
    def detect_provider(content: bytes, filename: str = "") -> CardProvider:
        return detect_provider(content, filename=filename)

    @staticmethod
    def is_text_embedded(content: bytes) -> bool:
        return is_text_embedded(content)

    def pick_parser(self, content: bytes, *, filename: str = "") -> BaseParser:
        """우선순위 tier 선택. 모두 적용 불가 → ParseError."""
        provider = detect_provider(content, filename=filename)
        text_embedded = is_text_embedded(content)

        # 1) RuleBased — provider 알려짐 + 텍스트 임베디드.
        if provider != "unknown" and text_embedded:
            rule_parser = self._rule_parsers.get(provider)
            if rule_parser is not None:
                return rule_parser

        # 2) OCR Hybrid — 스캔/이미지 또는 rule 미가용.
        if self._ocr_parser is not None:
            return self._ocr_parser

        # 3) LLM — 명시적으로 활성화된 경우만.
        if self._llm_enabled and self._llm_parser is not None:
            return self._llm_parser

        raise ParseError(
            "all parser tiers exhausted",
            reason=f"provider={provider} text_embedded={text_embedded} "
            f"rule={bool(self._rule_parsers)} ocr={bool(self._ocr_parser)} "
            f"llm_enabled={self._llm_enabled}",
            tier_attempted="llm" if self._llm_enabled else "ocr_hybrid",
        )

    async def parse(self, content: bytes, *, filename: str) -> ParsedTransaction:
        """tier 폴백 체인 — rule_based → ocr_hybrid → llm.

        - ``ParserNotImplementedError`` / ``RequiredFieldMissingError`` 는 다음 tier 로 fall-through
        - 모두 실패 시: provider unknown + OCR 없음 → ``ProviderNotDetectedError``
                     그 외 → ``LLMDisabledError``
        """
        provider = detect_provider(content, filename=filename)
        text_embedded = is_text_embedded(content)

        # 1) RuleBased — provider 알려짐 + 텍스트 임베디드.
        if provider != "unknown" and text_embedded:
            rule_parser = self._rule_parsers.get(provider)
            if rule_parser is not None:
                try:
                    return await rule_parser.parse(content, filename=filename)
                except ParserNotImplementedError:
                    # 구조화 로그 — fallback 사유 분류.
                    _log.info(
                        "tier_skipped",
                        tier_skipped="rule_based:stub",
                        provider=provider,
                        filename=filename,
                    )
                except RequiredFieldMissingError as e:
                    _log.warning(
                        "tier_failed",
                        tier="rule_based",
                        provider=provider,
                        field=e.field,
                        filename=filename,
                    )

        # 2) OCR Hybrid.
        if self._ocr_parser is not None:
            try:
                return await self._ocr_parser.parse(content, filename=filename)
            except ParseError as e:
                _log.warning(
                    "tier_failed",
                    tier="ocr_hybrid",
                    reason=e.reason,
                    filename=filename,
                )

        # 3) LLM — 명시 활성화 시만.
        if self._llm_enabled and self._llm_parser is not None:
            return await self._llm_parser.parse(content, filename=filename)

        # 모든 tier 소진 — 분류된 에러로 보고.
        if provider == "unknown" and self._ocr_parser is None:
            raise ProviderNotDetectedError(
                f"no provider detected and OCR unavailable for {filename}",
                reason=f"text_embedded={text_embedded}",
                tier_attempted="rule_based",
            )
        raise LLMDisabledError(
            f"all tiers exhausted, LLM disabled for {filename}",
            reason=f"provider={provider} text_embedded={text_embedded}",
            tier_attempted="ocr_hybrid",
        )
