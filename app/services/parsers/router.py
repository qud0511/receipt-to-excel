"""ParserRouter — provider 감지 + tier 라우팅.

CLAUDE.md §"특이사항: 추출 우선순위 — RuleBased > OCR Hybrid > LLM-only".
ADR-007 §"text-aware provider 감지": PDF font encoding 으로 한글 byte 매칭 불가 →
추출 텍스트에서 한글 시그니처 매칭.
"""

from __future__ import annotations

import asyncio
import re

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
from app.services.parsers.pdf_text_probe import extract_pdf_text, is_text_embedded

_log = structlog.get_logger(__name__)

# Provider byte 시그니처 — ASCII URL 등 raw bytes 에 직접 존재하는 것만.
# 한글 시그니처는 PDF font glyph encoding 으로 raw bytes 에 없으므로 (ADR-007),
# 추출 텍스트 매칭(``_PROVIDER_TEXT_SIGNATURES``) 으로 분리.
_PROVIDER_BYTE_SIGNATURES: dict[CardProvider, tuple[bytes, ...]] = {
    "shinhan": (b"shinhancard.com",),
    "hana": (b"hanacard.co.kr",),
    "samsung": (b"samsungcard.com",),
    "woori": (b"wooricard.com",),
    "hyundai": (b"hyundaicard.com", b"Hyundai Card"),
    "lotte": (b"lottecard.co.kr",),
    "kbank": (b"kbank.com",),
    "kakaobank": (b"kakaobank",),
}

# Provider 추출-텍스트 시그니처 — pdfplumber 가 ToUnicode mapping 으로 복원한 한글.
# JPG/이미지 PDF 는 텍스트 추출 불가 → 본 dict 적용 안 됨 (filename hint fallback).
_PROVIDER_TEXT_SIGNATURES: dict[CardProvider, tuple[str, ...]] = {
    "shinhan": ("신한카드",),
    "hana": ("하나카드",),
    "samsung": ("삼성카드",),
    "woori": ("우리카드",),
    "hyundai": ("현대카드",),
    "lotte": ("롯데카드",),
    "kbank": ("케이뱅크 카드 매출 전표", "케이뱅크"),
    "kakaobank": ("카드매출 온라인전표",),
}

# 우리카드 N-up 발행본은 본문에 브랜드명 "우리카드" 자체가 없음 (ADR-004).
# 텍스트 추출 후 이중 게이트로 보완:
#   ① 블록 마커 "국내전용카드" 존재
#   ② 9500-BIN 카드번호 패턴 존재 (우리카드 BIN, BIN 범위로 확정성 보강)
# byte 매칭은 PDF font encoding 으로 한글 시그니처 무용 → 모두 추출 텍스트에서 매칭.
_WOORI_NUP_MARKER = "국내전용카드"
_WOORI_NUP_BIN = re.compile(r"9500-\*{4}-\*{4}-\d{4}")


def _matches_woori_nup_text(extracted_text: str) -> bool:
    return _WOORI_NUP_MARKER in extracted_text and _WOORI_NUP_BIN.search(extracted_text) is not None


def _matches_hyundai_image(filename: str) -> bool:
    """현대카드 이미지 PDF 파일명 hint — 텍스트 부재 시 OCR Hybrid 경로 라우팅.

    텍스트 추출 가능한 hyundai 본문은 ``_PROVIDER_TEXT_SIGNATURES`` 가 처리.
    본 함수는 이미지 PDF (텍스트 추출 None) 케이스용 fallback.
    """
    return filename.lower().startswith("hyundai") or "현대카드" in filename


def detect_provider(
    content: bytes,
    filename: str = "",
    *,
    extracted_text: str | None = None,
) -> CardProvider:
    """카드사 시그니처 감지 — 3 단계 fallback. 미식별 → "unknown".

    1) byte ASCII 시그니처 — URL 등 raw bytes 에 직접 존재.
    2) 추출 텍스트 한글 시그니처 — ``extracted_text`` 가 주어진 경우만.
       우리카드 N-up dual gate (``_matches_woori_nup_text``) 포함.
    3) 파일명 hint — 이미지 PDF 의 hyundai (텍스트 추출 None 시 fallback).
    """
    # 1) Byte ASCII 시그니처
    for provider, byte_sigs in _PROVIDER_BYTE_SIGNATURES.items():
        for byte_sig in byte_sigs:
            if byte_sig in content:
                return provider

    # 2) 추출 텍스트 한글 시그니처
    if extracted_text:
        for provider, text_sigs in _PROVIDER_TEXT_SIGNATURES.items():
            for text_sig in text_sigs:
                if text_sig in extracted_text:
                    return provider
        if _matches_woori_nup_text(extracted_text):
            return "woori"

    # 3) 이미지 PDF — 텍스트 추출 불가능한 hyundai fallback
    if _matches_hyundai_image(filename):
        return "hyundai"

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
    def detect_provider(
        content: bytes,
        filename: str = "",
        *,
        extracted_text: str | None = None,
    ) -> CardProvider:
        return detect_provider(content, filename=filename, extracted_text=extracted_text)

    @staticmethod
    def is_text_embedded(content: bytes) -> bool:
        return is_text_embedded(content)

    def pick_parser(
        self,
        content: bytes,
        *,
        filename: str = "",
        extracted_text: str | None = None,
    ) -> BaseParser:
        """우선순위 tier 선택. 모두 적용 불가 → ParseError.

        ``extracted_text`` 가 None 이면 byte 시그니처만 사용 — 한글 시그니처 매칭 skip.
        """
        provider = detect_provider(content, filename=filename, extracted_text=extracted_text)
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

    async def parse(self, content: bytes, *, filename: str) -> list[ParsedTransaction]:
        """tier 폴백 체인 — rule_based → ocr_hybrid → llm.

        ADR-005: list[ParsedTransaction] 반환 — N-up 매출전표는 1 파일 → N 거래.
        ADR-007: text-aware provider 감지 — text-embedded PDF 에서 한 번만 추출 후 캐시.

        - ``ParserNotImplementedError`` / ``RequiredFieldMissingError`` 는 다음 tier 로 fall-through
        - 모두 실패 시: provider unknown + OCR 없음 → ``ProviderNotDetectedError``
                     그 외 → ``LLMDisabledError``
        """
        text_embedded = is_text_embedded(content)
        # 텍스트 추출은 동기 IO — async 차단 방지 (CLAUDE.md §"성능").
        extracted_text = (
            await asyncio.to_thread(extract_pdf_text, content) if text_embedded else None
        )
        provider = detect_provider(content, filename=filename, extracted_text=extracted_text)

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
