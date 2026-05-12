"""Phase 4.3 — KBank rule parser 합성 PDF 6 케이스 + Phase 4.5 실 PDF 보강."""

from __future__ import annotations

from datetime import date, time
from pathlib import Path

import pytest
from app.services.parsers.rule_based.kbank import KBankRuleBasedParser

from tests.fixtures.synthetic_pdfs import make_kbank_receipt

_REAL_PDFS_DIR = Path(__file__).resolve().parents[1] / "smoke" / "real_pdfs"
_KBANK_03 = _REAL_PDFS_DIR / "kbank_03.pdf"
_KBANK_04 = _REAL_PDFS_DIR / "kbank_04.pdf"


# ── 1) 정상 합성 PDF 전 필드 추출 ─────────────────────────────────────────────
async def test_parses_canonical_kbank_receipt_pdf() -> None:
    pdf = make_kbank_receipt(
        merchant="케이뱅크가맹점",
        transaction_dt="2026/05/10 14:23:11",
        amount=8900,
    )
    parser = KBankRuleBasedParser()
    [result] = await parser.parse(pdf, filename="kbank.pdf")

    assert result.가맹점명 == "케이뱅크가맹점"
    assert result.거래일 == date(2026, 5, 10)
    assert result.거래시각 == time(14, 23, 11)
    assert result.금액 == 8900
    assert result.카드사 == "kbank"


# ── 2) "거래금액: 8,900 원" — 숫자/원 사이 공백 회귀 방지 ────────────────────
async def test_거래금액_has_space_before_원() -> None:
    pdf = make_kbank_receipt(amount=12345)
    parser = KBankRuleBasedParser()
    [result] = await parser.parse(pdf, filename="kbank.pdf")
    # KBank 양식의 공백 패턴이 정규식에 의해 정확히 흡수됨.
    assert result.금액 == 12345


# ── 3) KBank 는 부가세/공급가액 필드 부재 → None ──────────────────────────────
async def test_부가세_공급가액_returns_none() -> None:
    pdf = make_kbank_receipt()
    parser = KBankRuleBasedParser()
    [result] = await parser.parse(pdf, filename="kbank.pdf")
    assert result.공급가액 is None
    assert result.부가세 is None
    # confidence 도 none.
    assert result.field_confidence.get("공급가액") == "none"
    assert result.field_confidence.get("부가세") == "none"


# ── 4) 업종 값 존재 시 추출 + medium confidence ──────────────────────────────
async def test_업종_extracted_when_present() -> None:
    pdf = make_kbank_receipt(business_category="일반음식점")
    parser = KBankRuleBasedParser()
    [result] = await parser.parse(pdf, filename="kbank.pdf")
    assert result.업종 == "일반음식점"
    # 사양: 업종 값 존재 시 → medium (다른 카드사 대비 partial_match 로 분류).
    assert result.field_confidence.get("업종") == "medium"


# ── 5) 주소 multiline 이어도 다른 필드 정상 ─────────────────────────────────
async def test_주소_handles_multiline() -> None:
    pdf = make_kbank_receipt(
        merchant="케이뱅크가맹점",
        address="서울시 강남구 테헤란로\n123-45 4층",
    )
    parser = KBankRuleBasedParser()
    [result] = await parser.parse(pdf, filename="kbank.pdf")
    assert result.가맹점명 == "케이뱅크가맹점"


# ── 6) AD-2 canonical 변환 ──────────────────────────────────────────────────
async def test_card_number_already_canonical() -> None:
    pdf = make_kbank_receipt(card_number_masked="9876-54**-****-3210")
    parser = KBankRuleBasedParser()
    [result] = await parser.parse(pdf, filename="kbank.pdf")
    assert result.카드번호_마스킹 == "9876-****-****-3210"


# ── 7) Phase 4.5: 실 PDF — 거래일시 일+시각 사이 공백 없음 (ADR-008) ──────────
# 실 KBank PDF text dump:
#   '거래일시 2026/04/0612:52:53'  ← 일 06 과 시각 12 사이 공백 없음
#   '거래금액 4,700원'              ← 숫자와 원 사이 공백 없음


@pytest.mark.real_pdf
@pytest.mark.skipif(not _KBANK_03.exists(), reason="kbank_03.pdf 미존재 (gitignore)")
async def test_real_kbank_03_extracts_date_amount_merchant() -> None:
    """실 kbank_03.pdf: 거래일 2026/04/06 12:52:53, 금액 4,700, 가맹점 '할리스커피 여의도파'."""
    content = _KBANK_03.read_bytes()
    parser = KBankRuleBasedParser()
    [result] = await parser.parse(content, filename="kbank_03.pdf")

    assert result.거래일 == date(2026, 4, 6)
    assert result.거래시각 == time(12, 52, 53)
    assert result.금액 == 4_700
    assert "할리스커피" in result.가맹점명
    assert result.업종 == "서양음식"
    assert result.카드사 == "kbank"
    assert result.parser_used == "rule_based"


@pytest.mark.real_pdf
@pytest.mark.skipif(not _KBANK_04.exists(), reason="kbank_04.pdf 미존재 (gitignore)")
async def test_real_kbank_04_extracts_fields() -> None:
    content = _KBANK_04.read_bytes()
    parser = KBankRuleBasedParser()
    [result] = await parser.parse(content, filename="kbank_04.pdf")
    assert result.거래일 == date(2026, 4, 8)
    assert result.거래시각 == time(13, 15, 59)
    assert result.금액 == 9_900
