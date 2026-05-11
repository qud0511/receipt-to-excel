"""합성 PDF 생성 — 카드사별 매출전표 패턴을 reportlab 으로 직접 생성.

CLAUDE.md §"TDD 특이사항": 합성 fixture 에는 가짜 가맹점명 + ``9999-99**-****-9999``
형식의 마스킹 카드번호 사용. 실 카드사 PDF 는 ``tests/smoke/real_pdfs/`` (gitignore).
"""

from __future__ import annotations

import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

_FONT_NAME = "HYSMyeongJo-Medium"
_FONT_REGISTERED = False


def _ensure_font() -> None:
    """reportlab built-in CID 한글 폰트 — ToUnicode mapping 포함이라 pdfplumber 추출 가능."""
    global _FONT_REGISTERED
    if not _FONT_REGISTERED:
        pdfmetrics.registerFont(UnicodeCIDFont(_FONT_NAME))
        _FONT_REGISTERED = True


def make_shinhan_receipt(
    *,
    merchant: str = "테스트가맹점",
    transaction_dt: str = "2026-05-10 14:23:11",
    amount: int = 8900,
    supply_amount: int | None = 8091,
    vat: int | None = 809,
    approval_no: str | None = "12345678",
    card_number_masked: str = "9999-99**-****-9999",
    business_category: str | None = "음료",
) -> bytes:
    """신한카드 매출전표 합성 PDF — pdfplumber 가 추출 가능한 layout.

    nullable 인자에 None 을 주면 해당 행을 PDF 에 출력하지 않음 (결손 시나리오 테스트).
    """
    _ensure_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont(_FONT_NAME, 11)

    y = 800
    c.drawString(50, y, "신한카드 매출전표")
    y -= 30
    c.drawString(50, y, f"가맹점명: {merchant}")
    y -= 20
    c.drawString(50, y, f"거래일시: {transaction_dt}")
    y -= 20
    c.drawString(50, y, f"거래금액: ₩{amount:,}")
    y -= 20
    if supply_amount is not None:
        c.drawString(50, y, f"공급가액: ₩{supply_amount:,}")
        y -= 20
    if vat is not None:
        c.drawString(50, y, f"부가세: ₩{vat:,}")
        y -= 20
    if approval_no is not None:
        c.drawString(50, y, f"승인번호: {approval_no}")
        y -= 20
    c.drawString(50, y, f"카드번호: {card_number_masked}")
    y -= 20
    if business_category is not None:
        c.drawString(50, y, f"업종: {business_category}")
        y -= 20
    # provider signature — ParserRouter.detect_provider 매칭용.
    c.drawString(50, y, "shinhancard.com")

    c.save()
    return buf.getvalue()
