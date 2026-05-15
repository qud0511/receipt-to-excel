"""Phase 4.2 — Shinhan rule parser 합성 PDF 7 케이스 + Phase 4.5 실 PDF 보강."""

from __future__ import annotations

from datetime import date, time
from pathlib import Path

import pytest
from app.services.parsers.base import RequiredFieldMissingError
from app.services.parsers.rule_based.shinhan import ShinhanRuleBasedParser

from tests.fixtures.synthetic_pdfs import make_shinhan_receipt

_REAL_PDFS_DIR = Path(__file__).resolve().parents[1] / "smoke" / "real_pdfs"
_SHINHAN_01 = _REAL_PDFS_DIR / "shinhan_01.pdf"
_SHINHAN_TAXI_01 = _REAL_PDFS_DIR / "shinhan_taxi_01.pdf"


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


# ── 8) Phase 4.5: 실 PDF 거래일 layout — 점 구분자 + \x01 + 초 없음 (ADR-008) ──
# 실 신한 PDF text dump:
#   '2026.1.2\x0111:21:53'         ← 페이지 출력 시각 (TX 아님, 무시해야 함)
#   '거래일 2025.12.05\x0115:15'   ← 진짜 거래일 (라벨, dot, \x01, 초 없음)
#   '에슬로우\x01대치1호점(ESLOW)' ← 가맹점명 (라벨 없음, '가맹점 정보' block 에 반복)
#   '10,300' / '원'                ← 금액 (라벨 없음, 두 줄 분리)


@pytest.mark.real_pdf
@pytest.mark.skipif(not _SHINHAN_01.exists(), reason="shinhan_01.pdf 미존재 (gitignore)")
async def test_real_shinhan_01_extracts_date_amount_merchant() -> None:
    """실 shinhan_01.pdf: 거래일 2025.12.05 15:15, 금액 10,300, 가맹점 에슬로우 대치1호점."""
    content = _SHINHAN_01.read_bytes()
    parser = ShinhanRuleBasedParser()
    [result] = await parser.parse(content, filename="shinhan_01.pdf")

    # 거래일 라벨 우선 — 페이지 헤더 '2026.1.2' 가 아닌 본문 '2025.12.05' 추출.
    assert result.거래일 == date(2025, 12, 5)
    assert result.거래시각 == time(15, 15)  # 초 없음 → 0
    assert result.금액 == 10_300
    # 가맹점명 raw 보존 — \x01 컨트롤 문자 포함 (AD-1 immutable).
    assert "에슬로우" in result.가맹점명
    assert result.카드사 == "shinhan"
    assert result.parser_used == "rule_based"


@pytest.mark.real_pdf
@pytest.mark.skipif(not _SHINHAN_TAXI_01.exists(), reason="shinhan_taxi_01.pdf 미존재 (gitignore)")
async def test_real_shinhan_taxi_01_extracts_fields() -> None:
    """실 shinhan_taxi_01.pdf — 동일 layout, 업종=택시."""
    content = _SHINHAN_TAXI_01.read_bytes()
    parser = ShinhanRuleBasedParser()
    [result] = await parser.parse(content, filename="shinhan_taxi_01.pdf")

    assert result.거래일 == date(2025, 12, 16)
    assert result.거래시각 == time(22, 34)
    assert result.금액 == 18_700
    assert "이동의즐거움" in result.가맹점명
    assert result.업종 == "택시"


# ── 9) Phase 4.5: 합성 fixture 거래일 dot 변형 회귀 방지 ─────────────────────
async def test_synthetic_shinhan_with_dot_separator_still_parses() -> None:
    """ADR-008 §"양쪽 동작 보장": 새 regex 가 대시 합성 fixture 와 dot 실 자료 양쪽 매칭."""
    # 합성 fixture 의 기본 대시 + 공백 + 초 layout 회귀.
    pdf = make_shinhan_receipt(transaction_dt="2026-05-10 14:23:11")
    parser = ShinhanRuleBasedParser()
    [result] = await parser.parse(pdf, filename="shinhan-dash.pdf")
    assert result.거래일 == date(2026, 5, 10)
    assert result.거래시각 == time(14, 23, 11)
