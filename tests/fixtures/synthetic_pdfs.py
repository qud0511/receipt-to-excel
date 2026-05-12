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


def make_samsung_receipt(
    *,
    merchant: str = "삼성가맹점",
    transaction_dt: str = "2026/05/10 14:23:11",
    amount_total: int = 11000,
    usage_amount: int | None = 10000,
    vat: int | None = 1000,
    approval_no: str | None = "12345678",
    card_number_masked: str = "1234-56**-****-7890",
    address: str | None = None,
) -> bytes:
    """삼성카드 매출전표 합성 PDF — synthesis/05 §Phase 4 Samsung 사양 layout.

    `address` 가 multiline 이면 줄바꿈 그대로 출력해 가맹점주소 multiline 케이스 검증.
    """
    _ensure_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont(_FONT_NAME, 11)

    y = 800
    c.drawString(50, y, "삼성카드 매출전표")
    y -= 30
    c.drawString(50, y, "samsungcard.com")
    y -= 30
    c.drawString(50, y, f"카드번호: {card_number_masked}")
    y -= 20
    c.drawString(50, y, f"거래일자: {transaction_dt}")
    y -= 20
    if approval_no is not None:
        c.drawString(50, y, f"승인번호: {approval_no}")
        y -= 20
    c.drawString(50, y, f"이용금액 합계: {amount_total:,}원")
    y -= 20
    if usage_amount is not None:
        c.drawString(50, y, f"이용금액: {usage_amount:,}원")
        y -= 20
    if vat is not None:
        c.drawString(50, y, f"부가세: {vat:,}원")
        y -= 20
    c.drawString(50, y, f"가맹점명: {merchant}")
    y -= 20
    if address is not None:
        c.drawString(50, y, "가맹점주소:")
        y -= 20
        for line in address.split("\n"):
            c.drawString(50, y, line)
            y -= 20

    c.save()
    return buf.getvalue()


def make_woori_receipt(
    *,
    merchant: str = "가짜우리가맹점",
    transaction_dt: str = "2026/05/1014:23:11",
    amount: int = 8_900,
    service_charge: int = 0,
    vat: int = 809,
    recycle_deposit: int = 0,
    approval_no: str = "12345678",
    card_number_masked: str = "9999-99**-****-9999",
    address_lines: tuple[str, ...] = ("서울특별시강남구테헤란로 123",),
    merchant_number: str = "123456789",
    biz_number: str = "000-00-00000",
    phone: str = "0212345678",
    include_page_header: bool = True,
) -> bytes:
    """우리카드 매출전표 합성 PDF — 라벨 없는 위치 기반 N-up layout.

    실 우리카드 발행 layout (ADR-004 분석) 재현 — 한 거래 1열 single-block 케이스.
    Task 3 의 N-up 분할 테스트는 별도 fixture (``make_woori_nup_receipt``) 가 담당.

    Layout (line-by-line, 라벨 없음):
        2026.05.04 16:55:07         # page header timestamp (skip 대상)
        국내전용카드                  # block 마커
        9999-99**-****-9999          # card_number (canonical 형식)
        2026/05/1014:23:11           # date+time 공백 없이 붙음 (우리카드 특이)
        일시불                       # installment
        {amount}원                   # 거래금액 (line 1)
        {service_charge}원           # 봉사료    (line 2)
        {vat}원                      # 부가세    (line 3)
        {recycle_deposit}원          # 자원순환보증금 (line 4)
        {approval_no}                # 승인번호 (8 자리)
        {merchant}                   # 가맹점명
        {address}                    # 가맹점주소 (1~2 lines, 광역시/도 시작)
        {merchant_number}            # 가맹점번호 (9 자리)
        {biz_number}                 # 사업자번호 (XXX-XX-XXXXX)
        {phone}                      # 가맹점전화 (10 자리)
    """
    _ensure_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont(_FONT_NAME, 11)

    y = 800
    if include_page_header:
        c.drawString(50, y, "2026.05.04 16:55:07")
        y -= 30
    c.drawString(50, y, "국내전용카드")
    y -= 20
    c.drawString(50, y, card_number_masked)
    y -= 20
    c.drawString(50, y, transaction_dt)
    y -= 20
    c.drawString(50, y, "일시불")
    y -= 20
    c.drawString(50, y, f"{amount:,}원")
    y -= 20
    c.drawString(50, y, f"{service_charge:,}원")
    y -= 20
    c.drawString(50, y, f"{vat:,}원")
    y -= 20
    c.drawString(50, y, f"{recycle_deposit:,}원")
    y -= 20
    c.drawString(50, y, approval_no)
    y -= 20
    c.drawString(50, y, merchant)
    y -= 20
    for line in address_lines:
        c.drawString(50, y, line)
        y -= 20
    c.drawString(50, y, merchant_number)
    y -= 20
    c.drawString(50, y, biz_number)
    y -= 20
    c.drawString(50, y, phone)

    c.save()
    return buf.getvalue()


def make_kbank_receipt(
    *,
    merchant: str = "케이뱅크가맹점",
    transaction_dt: str = "2026/05/10 14:23:11",
    amount: int = 8900,
    approval_no: str | None = "12345678",
    card_number_masked: str = "1234-56**-****-7890",
    business_category: str | None = None,
    address: str | None = None,
) -> bytes:
    """케이뱅크 카드 매출 전표 합성 PDF — synthesis/05 §Phase 4 KBank 사양 layout.

    "거래금액: 8,900 원" — 사양상 숫자와 "원" 사이에 공백 (회귀 방지 회피 어려운 케이스).
    """
    _ensure_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont(_FONT_NAME, 11)

    y = 800
    c.drawString(50, y, "케이뱅크 카드 매출 전표")
    y -= 30
    c.drawString(50, y, f"카드번호: {card_number_masked}")
    y -= 20
    c.drawString(50, y, f"거래일시: {transaction_dt}")
    y -= 20
    if approval_no is not None:
        c.drawString(50, y, f"승인번호: {approval_no}")
        y -= 20
    # 숫자와 "원" 사이 공백 — KBank 양식 특성. parser 가 공백 허용 정규식 필수.
    c.drawString(50, y, f"거래금액: {amount:,} 원")
    y -= 20
    c.drawString(50, y, f"가맹점명: {merchant}")
    y -= 20
    if business_category is not None:
        c.drawString(50, y, f"업종: {business_category}")
        y -= 20
    if address is not None:
        c.drawString(50, y, "주소:")
        y -= 20
        for line in address.split("\n"):
            c.drawString(50, y, line)
            y -= 20

    c.save()
    return buf.getvalue()
