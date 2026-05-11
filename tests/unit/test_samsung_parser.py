"""Phase 4.3 — Samsung rule parser 합성 PDF 6 케이스."""

from __future__ import annotations

from datetime import date, time

from app.services.parsers.rule_based.samsung import SamsungRuleBasedParser

from tests.fixtures.synthetic_pdfs import make_samsung_receipt


# ── 1) 정상 합성 PDF 전 필드 추출 ─────────────────────────────────────────────
async def test_parses_canonical_samsung_receipt_pdf() -> None:
    pdf = make_samsung_receipt(
        merchant="삼성가맹점",
        transaction_dt="2026/05/10 14:23:11",
        amount_total=11000,
        usage_amount=10000,
        vat=1000,
    )
    parser = SamsungRuleBasedParser()
    result = await parser.parse(pdf, filename="samsung.pdf")

    assert result.가맹점명 == "삼성가맹점"
    assert result.거래일 == date(2026, 5, 10)
    assert result.거래시각 == time(14, 23, 11)
    assert result.금액 == 11000  # 합계
    assert result.공급가액 == 10000  # 이용금액
    assert result.부가세 == 1000
    assert result.카드사 == "samsung"


# ── 2) 금액 = 합계 / 공급가액 = 이용금액 구분 회귀 방지 ────────────────────────
async def test_extracts_합계금액_not_이용금액() -> None:
    pdf = make_samsung_receipt(amount_total=11000, usage_amount=10000, vat=1000)
    parser = SamsungRuleBasedParser()
    result = await parser.parse(pdf, filename="samsung.pdf")
    # 금액 (최종 청구액) 은 "이용금액 합계" 에서 와야 — "이용금액" 만 잡혀서 10000 이 되면 회귀.
    assert result.금액 == 11000
    assert result.공급가액 == 10000


# ── 3) AD-2 canonical — Samsung raw 형식 입력 그대로 canonical 변환 ───────────
async def test_card_number_already_canonical() -> None:
    pdf = make_samsung_receipt(card_number_masked="1234-56**-****-7890")
    parser = SamsungRuleBasedParser()
    result = await parser.parse(pdf, filename="samsung.pdf")
    # AD-2 canonical: NNNN-****-****-NNNN.
    assert result.카드번호_마스킹 == "1234-****-****-7890"


# ── 4) Samsung 은 업종 미기재 — None + confidence "none" ──────────────────────
async def test_업종_returns_none_with_none_confidence() -> None:
    pdf = make_samsung_receipt()
    parser = SamsungRuleBasedParser()
    result = await parser.parse(pdf, filename="samsung.pdf")
    assert result.업종 is None
    assert result.field_confidence.get("업종") == "none"


# ── 5) 거래일자 앞 10자 → 거래일, 뒤 8자 → 거래시각 ─────────────────────────────
async def test_거래시각_parsed_from_거래일자_field() -> None:
    pdf = make_samsung_receipt(transaction_dt="2026/12/31 23:59:58")
    parser = SamsungRuleBasedParser()
    result = await parser.parse(pdf, filename="samsung.pdf")
    assert result.거래일 == date(2026, 12, 31)
    assert result.거래시각 == time(23, 59, 58)


# ── 6) 가맹점주소 multiline 이어도 가맹점명 정상 추출 (주소는 저장 안 함) ────────
async def test_가맹점주소_handles_multiline() -> None:
    pdf = make_samsung_receipt(
        merchant="삼성가맹점",
        address="서울특별시 종로구\n광화문로 1-1\n2층 201호",
    )
    parser = SamsungRuleBasedParser()
    result = await parser.parse(pdf, filename="samsung.pdf")
    # 가맹점명은 multiline 주소 영향 없이 정확 추출.
    assert result.가맹점명 == "삼성가맹점"
