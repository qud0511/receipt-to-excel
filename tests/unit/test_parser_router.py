"""Phase 3 — ParserRouter / pdf_text_probe / ParseError 필드 보유."""

from __future__ import annotations

from datetime import date

import pytest
from app.domain.parsed_transaction import ParsedTransaction
from app.services.parsers.base import BaseParser, ParseError, ParserTier
from app.services.parsers.pdf_text_probe import is_text_embedded
from app.services.parsers.router import ParserRouter, detect_provider

# ── 모의 PDF bytes 픽스처 ────────────────────────────────────────────────────
# 텍스트 임베디드 PDF — BT...ET 블록 + provider signature.
_SHINHAN_PDF = b"%PDF-1.4\nBT\n" + "신한카드 매출전표".encode() + b"\nshinhancard.com\nET\n%%EOF"
_HANA_PDF = b"%PDF-1.4\nBT\nfooter: https://hanacard.co.kr/print\nET\n%%EOF"
_UNKNOWN_TEXT_PDF = b"%PDF-1.4\nBT\nSome random invoice text\n123-456\nET\n%%EOF"
# 스캔 PDF — BT 토큰 없음 (텍스트 레이어 부재).
_SCANNED_PDF = b"%PDF-1.4\n%scanned image only, no text layer\n%%EOF"


class _StubParser(BaseParser):
    """테스트용 — pick_parser 결과만 확인하므로 parse() 는 미구현."""

    def __init__(self, tier: ParserTier) -> None:
        self._tier = tier

    @property
    def tier(self) -> ParserTier:
        return self._tier

    async def parse(self, content: bytes, *, filename: str) -> list[ParsedTransaction]:
        # 본 테스트 스위트에서는 호출되지 않음.
        return [
            ParsedTransaction(
                가맹점명="stub",
                거래일=date(2026, 1, 1),
                금액=1,
                parser_used=self._tier,
                field_confidence={"가맹점명": "high"},
            )
        ]


# ── 1) shinhan 헤더 감지 ─────────────────────────────────────────────────────
def test_router_detects_shinhan_from_header() -> None:
    assert detect_provider(_SHINHAN_PDF) == "shinhan"


# ── 2) hana — footer URL 패턴 감지 ──────────────────────────────────────────
def test_router_detects_hana_from_footer_url() -> None:
    assert detect_provider(_HANA_PDF) == "hana"


# ── 3) 미식별 provider → "unknown" ──────────────────────────────────────────
def test_router_returns_unknown_for_unrecognized_pdf() -> None:
    assert detect_provider(_UNKNOWN_TEXT_PDF) == "unknown"


# ── 4) 텍스트 임베디드 PDF 양성 ──────────────────────────────────────────────
def test_router_probe_detects_text_embedded_pdf() -> None:
    assert is_text_embedded(_SHINHAN_PDF) is True


# ── 5) 스캔 PDF — 텍스트 레이어 없음 ─────────────────────────────────────────
def test_router_probe_flags_scanned_pdf() -> None:
    assert is_text_embedded(_SCANNED_PDF) is False


# ── 6) provider 알려짐 + 텍스트 임베디드 → rule_based ────────────────────────
def test_router_picks_rule_based_when_provider_known_and_text_embedded() -> None:
    rule = _StubParser("rule_based")
    router = ParserRouter(rule_based_parsers={"shinhan": rule})
    picked = router.pick_parser(_SHINHAN_PDF)
    assert picked is rule


# ── 7) 스캔 또는 이미지 → ocr_hybrid ────────────────────────────────────────
def test_router_picks_ocr_hybrid_when_scanned_or_image() -> None:
    ocr = _StubParser("ocr_hybrid")
    router = ParserRouter(ocr_hybrid_parser=ocr)
    picked = router.pick_parser(_SCANNED_PDF)
    assert picked is ocr


# ── 8) llm_enabled=True 인 경우만 LLM 폴백 ──────────────────────────────────
def test_router_falls_back_to_llm_only_when_enabled() -> None:
    llm = _StubParser("llm")
    # provider unknown, OCR 없음 — LLM 만 가용.
    router = ParserRouter(llm_parser=llm, llm_enabled=True)
    picked = router.pick_parser(_UNKNOWN_TEXT_PDF)
    assert picked is llm


# ── 9) 모든 tier 실패 + llm 비활성 → ParseError ───────────────────────────────
def test_router_raises_when_all_tiers_fail_and_llm_disabled() -> None:
    router = ParserRouter(llm_enabled=False)
    with pytest.raises(ParseError):
        router.pick_parser(_UNKNOWN_TEXT_PDF)


# ── 9a) Woori N-up 이중 게이트 — 추출 텍스트에 "국내전용카드" + 9500 BIN 둘 다 ──
def test_router_detects_woori_when_text_has_marker_and_bin() -> None:
    # ADR-007: byte 가 아닌 추출 텍스트에서 이중 게이트 평가.
    content = b"%PDF-1.4\nBT\nbody\nET\n%%EOF"
    text = "2026.05.0416:55:07\n국내전용카드\n9500-****-****-8751\n70,000원\n"
    assert detect_provider(content, extracted_text=text) == "woori"


# ── 9b) 마커만 + BIN 부재 → unknown (이중 게이트 strict) ──────────────────
def test_router_does_not_detect_woori_when_only_marker_in_text() -> None:
    content = b"%PDF-1.4\nBT\nbody\nET\n%%EOF"
    text = "국내전용카드\nother content without bin\n"
    assert detect_provider(content, extracted_text=text) == "unknown"


# ── 9c) BIN만 + 마커 부재 → unknown (이중 게이트 strict) ──────────────────
def test_router_does_not_detect_woori_when_only_bin_in_text() -> None:
    content = b"%PDF-1.4\nBT\nbody\nET\n%%EOF"
    text = "9500-****-****-8751\nother content without marker\n"
    assert detect_provider(content, extracted_text=text) == "unknown"


# ── 9d) hyundai 이미지 PDF — 파일명 hint fallback (텍스트 추출 None) ────────
def test_router_detects_hyundai_via_filename_hint_for_image_pdf() -> None:
    content = b"%PDF-1.4\n%scanned image only, no text layer\n%%EOF"
    # extracted_text=None (이미지 PDF) — 파일명 hint fallback 발동.
    assert detect_provider(content, filename="hyundai_01.pdf") == "hyundai"
    assert detect_provider(content, filename="현대카드_매출전표.pdf") == "hyundai"


# ── 9e) hyundai — 추출 텍스트의 "현대카드" 한글 시그니처 ─────────────────────
def test_router_detects_hyundai_via_extracted_text_signature() -> None:
    content = b"%PDF-1.4\nBT\nbody\nET\n%%EOF"
    text = "현대카드 매출전표\n..."
    assert detect_provider(content, extracted_text=text) == "hyundai"


# ── 9f) ADR-007 신규 — 신한 한글 시그니처 추출 텍스트 매칭 ──────────────────
def test_detects_shinhan_from_extracted_text() -> None:
    content = b"%PDF-1.4\nBT\nbody\nET\n%%EOF"
    text = "26. 1. 2. 오전 11:21 카드매출전표 < 신한카드\n2026.1.2\x0111:21:53\n"
    assert detect_provider(content, extracted_text=text) == "shinhan"


# ── 9g) ADR-007 신규 — 삼성 한글 시그니처 추출 텍스트 매칭 ──────────────────
def test_detects_samsung_from_extracted_text() -> None:
    content = b"%PDF-1.4\nBT\nbody\nET\n%%EOF"
    text = "팝업 | 카드 이용내역 - 삼성카드\n카드매출전표\n"
    assert detect_provider(content, extracted_text=text) == "samsung"


# ── 9h) ADR-007 신규 — 케이뱅크 한글 시그니처 추출 텍스트 매칭 ──────────────
def test_detects_kbank_from_extracted_text() -> None:
    content = b"%PDF-1.4\nBT\nbody\nET\n%%EOF"
    text = "케이뱅크 카드 매출 전표\n카드번호 1234-****-****-5678\n"
    assert detect_provider(content, extracted_text=text) == "kbank"


# ── 9i) ADR-007 신규 — 우리 단순 매출전표 (N-up 외) 추출 텍스트 매칭 ─────────
def test_detects_woori_from_extracted_text_simple_signature() -> None:
    # N-up 이 아닌 일반 우리카드 본문 (가상) — "우리카드" 텍스트로 매칭.
    content = b"%PDF-1.4\nBT\nbody\nET\n%%EOF"
    text = "우리카드 매출전표\n카드번호 1234-****-****-5678\n"
    assert detect_provider(content, extracted_text=text) == "woori"


# ── 9j) ADR-007 신규 — 추출 텍스트 + byte 모두 매칭 없음 → unknown ──────────
def test_unknown_when_no_text_and_no_byte_match() -> None:
    content = b"%PDF-1.4\nBT\nbody\nET\n%%EOF"
    # extracted_text 미전달 + byte URL 부재 → unknown.
    assert detect_provider(content) == "unknown"
    # 추출 텍스트도 어떤 카드사 시그니처도 없음.
    assert detect_provider(content, extracted_text="just plain body\nno provider\n") == "unknown"


# ── 10) DoD — ParseError 가 field/reason/tier_attempted 필드 보유 ────────────
def test_parse_error_has_field_reason_tier_attempted() -> None:
    e = ParseError(
        "extract failed",
        field="amount",
        reason="not numeric",
        tier_attempted="rule_based",
    )
    assert e.field == "amount"
    assert e.reason == "not numeric"
    assert e.tier_attempted == "rule_based"
    assert e.message == "extract failed"
