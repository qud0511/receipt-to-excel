"""Phase 4 (보완) — 우리카드 RuleBased 완전 구현.

ADR-004 결정 사항 검증:
- 라벨 없는 위치 기반 layout (4-line 금액 순서 추정)
- 페이지 발행 timestamp skip
- 거래일+시각 붙음 (yyyy/MM/dd HH:MM:SS, 공백 없음)
- 4-line 금액 비율 검증 가드 (부가세 = 거래금액 x 10/110)
- confidence: 거래금액=high · 부가세=medium · 봉사료/자원순환=low
"""

from __future__ import annotations

from datetime import date, time

import pytest
import structlog
from app.services.parsers.base import RequiredFieldMissingError
from app.services.parsers.rule_based.woori import WooriRuleBasedParser

from tests.fixtures.synthetic_pdfs import make_woori_receipt


# ── 1) 정상 합성 PDF — 단일 블록 전 필드 추출 ────────────────────────────────
async def test_parses_canonical_woori_receipt_single_block() -> None:
    pdf = make_woori_receipt(
        merchant="동백자연에너지",
        transaction_dt="2026/04/1318:04:09",
        amount=70_000,
        service_charge=0,
        vat=6_364,
        recycle_deposit=0,
        approval_no="76427042",
    )
    parser = WooriRuleBasedParser()
    result = await parser.parse(pdf, filename="woori_nup_01.pdf")

    assert result.가맹점명 == "동백자연에너지"
    assert result.거래일 == date(2026, 4, 13)
    assert result.거래시각 == time(18, 4, 9)
    assert result.금액 == 70_000
    assert result.부가세 == 6_364
    assert result.공급가액 == 70_000 - 6_364 - 0 - 0
    assert result.승인번호 == "76427042"
    assert result.카드사 == "woori"
    assert result.parser_used == "rule_based"


# ── 2) AD-2: 카드번호가 이미 canonical NNNN-****-****-NNNN 그대로 ──────────
async def test_card_number_passes_through_canonical() -> None:
    pdf = make_woori_receipt(card_number_masked="9500-99**-****-8751")
    parser = WooriRuleBasedParser()
    result = await parser.parse(pdf, filename="woori_01.pdf")
    # raw "9500-99**-****-8751" → canonical "9500-****-****-8751" (AD-2).
    assert result.카드번호_마스킹 == "9500-****-****-8751"


# ── 3) 거래일+시각 붙음 (우리카드 특이 — 다른 카드사는 공백 있음) ─────────
async def test_parses_concatenated_datetime_without_space() -> None:
    # 실 우리카드 layout: "yyyy/MM/ddHH:mm:ss" (date 와 time 사이 공백 없음).
    pdf = make_woori_receipt(transaction_dt="2026/04/2517:53:15")
    parser = WooriRuleBasedParser()
    result = await parser.parse(pdf, filename="woori_01.pdf")
    assert result.거래일 == date(2026, 4, 25)
    assert result.거래시각 == time(17, 53, 15)


# ── 4) 4-line 금액 비율 가드 — 부가세 ≈ 거래금액 x 10/110 통과 ─────────────
async def test_amount_layout_validation_passes_for_standard_vat_ratio() -> None:
    pdf = make_woori_receipt(amount=11_000, service_charge=0, vat=1_000, recycle_deposit=0)
    parser = WooriRuleBasedParser()
    result = await parser.parse(pdf, filename="woori_01.pdf")
    # 부가세 위치 추정 → exact ratio match → medium 유지.
    assert result.field_confidence["부가세"] == "medium"
    assert result.field_confidence["봉사료"] == "low"
    assert result.field_confidence["자원순환보증금"] == "low"


# ── 5) 4-line 금액 비율 가드 — 부가세 0 (면세) 케이스 정상 통과 ─────────────
async def test_amount_layout_passes_when_vat_is_zero_exempt_merchant() -> None:
    # 면세 사업자 (쏘카 등): 부가세 0 일 때도 가드는 통과해야 한다.
    pdf = make_woori_receipt(amount=7_200, service_charge=0, vat=0, recycle_deposit=0)
    parser = WooriRuleBasedParser()
    result = await parser.parse(pdf, filename="woori_nup_02.pdf")
    assert result.금액 == 7_200
    assert result.부가세 == 0
    # 면세 부가세 0 은 정상 — 비율 가드는 통과, 다만 confidence 는 medium 유지.
    assert result.field_confidence["부가세"] == "medium"


# ── 6) 4-line 금액 비율 가드 — 어긋남 시 경고 로그 + confidence 강등 ──────
async def test_amount_layout_warning_when_vat_ratio_mismatches() -> None:
    # 비율 어긋남 — 부가세 위치 추정이 잘못된 발행 양식 변경 조기 감지.
    pdf = make_woori_receipt(amount=11_000, service_charge=0, vat=5_000, recycle_deposit=0)
    parser = WooriRuleBasedParser()
    with structlog.testing.capture_logs() as logs:
        result = await parser.parse(pdf, filename="woori_01.pdf")

    # confidence 강등 → "low".
    assert result.field_confidence["부가세"] == "low"
    # 구조화 로그 — line 순서 추정 오류 분류.
    mismatch_logs = [e for e in logs if e.get("event") == "woori_amount_layout_mismatch"]
    assert len(mismatch_logs) >= 1, f"expected mismatch log, got: {logs}"


# ── 7) 페이지 발행 timestamp 무시 (거래일로 오인 금지) ─────────────────────
async def test_ignores_page_header_timestamp_line() -> None:
    # 페이지 header "2026.05.04 16:55:07" 와 거래일시 "2026/04/1318:04:09" 가 함께 나오는
    # 케이스 — 거래일은 후자여야 한다.
    pdf = make_woori_receipt(
        transaction_dt="2026/04/1318:04:09",
        include_page_header=True,
    )
    parser = WooriRuleBasedParser()
    result = await parser.parse(pdf, filename="woori_01.pdf")
    assert result.거래일 == date(2026, 4, 13)
    # 페이지 header (2026.05.04) 가 거래일로 오인되면 안 된다.
    assert result.거래일 != date(2026, 5, 4)


# ── 8) 가맹점명 — 주소 line (광역시/도 prefix) 직전 line ───────────────────
async def test_extracts_merchant_before_korean_administrative_prefix() -> None:
    # 가맹점명 추출 휴리스틱: 광역시/도 시작 line 직전이 가맹점명.
    pdf = make_woori_receipt(
        merchant="청정에너지동백점",
        address_lines=("경기도용인시기흥구석성로 666(동백동)",),
    )
    parser = WooriRuleBasedParser()
    result = await parser.parse(pdf, filename="woori_01.pdf")
    assert result.가맹점명 == "청정에너지동백점"


# ── 9) 주소 2 줄 케이스 — 자연에너지 (외 1필지 patten) ───────────────────
async def test_handles_two_line_address_for_subdivision_merchants() -> None:
    pdf = make_woori_receipt(
        merchant="동백자연에너지",
        address_lines=("경기용인시기흥구석성로 531", "외1필지(동백동)"),
        merchant_number="738469994",
    )
    parser = WooriRuleBasedParser()
    result = await parser.parse(pdf, filename="woori_01.pdf")
    assert result.가맹점명 == "동백자연에너지"
    # 2 줄 주소 다음 9 자리 가맹점번호 가 정상 detect 돼야 한다.
    # (가맹점번호 자체는 raw schema 에 없지만 잘못된 line 이 가맹점명에 새지 않으면 성공.)


# ── 10) 블록 마커 ("국내전용카드") 부재 → RequiredFieldMissingError ─────
async def test_raises_required_field_missing_when_no_block_marker() -> None:
    import io

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfgen import canvas

    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("HYSMyeongJo-Medium", 11)
    c.drawString(50, 800, "2026.05.04 16:55:07")
    c.drawString(50, 780, "본문 내용 — 국내전용카드 marker 없음")
    c.save()
    pdf = buf.getvalue()

    parser = WooriRuleBasedParser()
    with pytest.raises(RequiredFieldMissingError):
        await parser.parse(pdf, filename="woori_corrupt.pdf")


# ── 11) Confidence 정책 — 거래금액=high / 부가세=medium / 봉사료·자원순환=low
async def test_confidence_levels_per_adr_004() -> None:
    pdf = make_woori_receipt(amount=11_000, vat=1_000)
    parser = WooriRuleBasedParser()
    result = await parser.parse(pdf, filename="woori_01.pdf")

    assert result.field_confidence["금액"] == "high"
    assert result.field_confidence["거래일"] == "high"
    assert result.field_confidence["거래시각"] == "high"
    assert result.field_confidence["가맹점명"] == "high"
    assert result.field_confidence["부가세"] == "medium"
    assert result.field_confidence["봉사료"] == "low"
    assert result.field_confidence["자원순환보증금"] == "low"
