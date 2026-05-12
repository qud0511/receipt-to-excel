"""Phase 4.2 — Shinhan rule parser 합성 PDF 7 케이스."""

from __future__ import annotations

from datetime import date, time

import pytest
from app.services.parsers.base import RequiredFieldMissingError
from app.services.parsers.rule_based.shinhan import ShinhanRuleBasedParser

from tests.fixtures.synthetic_pdfs import make_shinhan_receipt


# ── 1) 정상 합성 PDF 전 필드 추출 ─────────────────────────────────────────────
async def test_parses_canonical_shinhan_receipt_pdf() -> None:
    pdf = make_shinhan_receipt(
        merchant="테스트가맹점",
        transaction_dt="2026-05-10 14:23:11",
        amount=8900,
    )
    parser = ShinhanRuleBasedParser()
    [result] = await parser.parse(pdf, filename="shinhan.pdf")

    assert result.가맹점명 == "테스트가맹점"
    assert result.거래일 == date(2026, 5, 10)
    assert result.거래시각 == time(14, 23, 11)
    assert result.금액 == 8900
    assert result.카드사 == "shinhan"
    assert result.parser_used == "rule_based"


# ── 2) AD-2: raw "NNNN-NN**-****-NNNN" → canonical "NNNN-****-****-NNNN" ─────
async def test_normalizes_card_number_to_canonical_nnnn_format() -> None:
    pdf = make_shinhan_receipt(card_number_masked="1234-56**-****-7890")
    parser = ShinhanRuleBasedParser()
    [result] = await parser.parse(pdf, filename="shinhan.pdf")

    # AD-2 canonical 형식: NNNN-****-****-NNNN.
    assert result.카드번호_마스킹 == "1234-****-****-7890"


# ── 3) AD-1: 업종 raw 값 보존 (정규화 없음) ──────────────────────────────────
async def test_extracts_business_category_raw() -> None:
    pdf = make_shinhan_receipt(business_category="일반음식점")
    parser = ShinhanRuleBasedParser()
    [result] = await parser.parse(pdf, filename="shinhan.pdf")
    assert result.업종 == "일반음식점"


# ── 4) 필수 필드 모두 high confidence ────────────────────────────────────────
async def test_assigns_high_confidence_to_all_required_fields() -> None:
    pdf = make_shinhan_receipt()
    parser = ShinhanRuleBasedParser()
    [result] = await parser.parse(pdf, filename="shinhan.pdf")
    for required in ("가맹점명", "거래일", "금액"):
        assert result.field_confidence.get(required) == "high", (
            f"{required} should be high, got {result.field_confidence.get(required)}"
        )


# ── 5) Optional 필드 결손 시 그 필드 confidence none, 다른 optional 은 medium ──
async def test_returns_medium_confidence_when_optional_field_missing() -> None:
    # 부가세는 결손, 공급가액은 존재.
    pdf = make_shinhan_receipt(vat=None, supply_amount=8091)
    parser = ShinhanRuleBasedParser()
    [result] = await parser.parse(pdf, filename="shinhan.pdf")
    # 결손된 부가세 → none.
    assert result.부가세 is None
    assert result.field_confidence.get("부가세") == "none"
    # 존재하는 공급가액 → medium (optional partial_match).
    assert result.공급가액 == 8091
    assert result.field_confidence.get("공급가액") == "medium"


# ── 6) 필수 필드 결손 → RequiredFieldMissingError ────────────────────────────
async def test_raises_parse_error_when_required_field_missing() -> None:
    # 금액 행을 빼고 PDF 생성하기 위해 amount=0 우회 — 합성 함수가 amount=0 도 출력하므로
    # 대신 가맹점명 ":" 결손 케이스를 만든다. 단순화: 정규식 매칭 안 되는 PDF 를 직접 작성.
    import io

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfgen import canvas

    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("HYSMyeongJo-Medium", 11)
    c.drawString(50, 800, "신한카드 매출전표")
    c.drawString(50, 780, "shinhancard.com")
    # 가맹점명 / 거래일시 / 거래금액 모두 결손.
    c.save()
    pdf = buf.getvalue()

    parser = ShinhanRuleBasedParser()
    with pytest.raises(RequiredFieldMissingError):
        await parser.parse(pdf, filename="shinhan-empty.pdf")


# ── 7) AD-4: ParsedTransaction 에 card_type / project_id 등 derived 비포함 ────
async def test_field_set_does_not_include_card_type_or_client_project() -> None:
    pdf = make_shinhan_receipt()
    parser = ShinhanRuleBasedParser()
    [result] = await parser.parse(pdf, filename="shinhan.pdf")

    # ParsedTransaction 은 AD-4 raw fields only — Resolver 의 derived 결과는 별개 레이어.
    fields = set(result.model_fields_set)
    forbidden = {"card_type", "project_id", "xlsx_sheet", "expense_column"}
    leak = fields & forbidden
    assert not leak, f"ParsedTransaction leaked derived fields: {leak}"
