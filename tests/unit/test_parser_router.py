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


# ── 9a) Woori N-up 이중 게이트 — filename hint + "국내전용카드" fingerprint ──
def test_router_detects_woori_when_filename_and_fingerprint_both_match() -> None:
    content = b"%PDF-1.4\nBT\n" + "국내전용카드".encode() + b"\nET\n%%EOF"
    assert detect_provider(content, filename="woori_nup_01.pdf") == "woori"
    assert detect_provider(content, filename="우리카드_매출전표_1.pdf") == "woori"


# ── 9b) 파일명만 매칭 + fingerprint 부재 → unknown (이중 게이트 차단) ───────
def test_router_does_not_detect_woori_when_only_filename_matches() -> None:
    content = b"%PDF-1.4\nBT\nrandom invoice body\nET\n%%EOF"
    # "국내전용카드" 마커 없음 → 파일명만으로는 통과 불가.
    assert detect_provider(content, filename="woori_fake.pdf") == "unknown"


# ── 9c) fingerprint 매칭 + 파일명 미일치 → unknown (이중 게이트 차단) ───────
def test_router_does_not_detect_woori_when_only_fingerprint_matches() -> None:
    content = b"%PDF-1.4\nBT\n" + "국내전용카드".encode() + b"\nET\n%%EOF"
    # 파일명에 woori/우리카드 힌트 없음 → 통과 불가.
    assert detect_provider(content, filename="random_receipt.pdf") == "unknown"


# ── 9d) hyundai 이미지 PDF — 파일명 hint 만으로 provider 결정 (OCR Hybrid 폴백 전제) ──
def test_router_detects_hyundai_via_filename_hint_for_image_pdf() -> None:
    # 텍스트 없는 이미지 PDF — byte 시그니처 매칭 불가, 파일명 hint 만 사용.
    content = b"%PDF-1.4\n%scanned image only, no text layer\n%%EOF"
    assert detect_provider(content, filename="hyundai_01.pdf") == "hyundai"
    assert detect_provider(content, filename="현대카드_매출전표.pdf") == "hyundai"


def test_router_detects_hyundai_via_byte_signature_when_present() -> None:
    # 향후 텍스트 임베디드 hyundai 매출전표 — byte 시그니처 직접 매칭.
    content = b"%PDF-1.4\nBT\n" + "현대카드".encode() + b"\nET\n%%EOF"
    assert detect_provider(content, filename="anything.pdf") == "hyundai"


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
