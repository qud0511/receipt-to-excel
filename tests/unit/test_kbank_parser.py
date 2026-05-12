"""Phase 4.3 — KBank rule parser 합성 PDF 6 케이스."""

from __future__ import annotations

from datetime import date, time

from app.services.parsers.rule_based.kbank import KBankRuleBasedParser

from tests.fixtures.synthetic_pdfs import make_kbank_receipt


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
