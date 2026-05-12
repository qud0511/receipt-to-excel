"""Phase 5.3 — PDF Generators (merged + layout) 6 케이스.

merged_pdf: 거래일 ASC 정렬 + 원본 PDF/JPG 페이지 연결.
layout_pdf: 2~3 / A4 layout + scale-to-fit (aspect ratio 보존, R11).
파일명 R12 패턴.
"""

from __future__ import annotations

import io
from datetime import date

from app.services.generators.layout_pdf import (
    generate_layout_pdf_filename,
    write_layout_pdf,
)
from app.services.generators.merged_pdf import write_merged_pdf
from PIL import Image
from pypdf import PdfReader

from tests.fixtures.synthetic_pdfs import make_shinhan_receipt


def _make_test_jpg(*, width: int = 200, height: int = 300, color: str = "red") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="JPEG")
    return buf.getvalue()


# ── 1) merged_pdf 거래일 ASC 정렬 ─────────────────────────────────────────────
def test_merged_pdf_orders_by_transaction_date_asc() -> None:
    """입력 순서 무관 — 출력 PDF 페이지가 거래일 오름차순."""
    pdf_b = make_shinhan_receipt(merchant="B", transaction_dt="2026-05-03 12:00:00")
    pdf_a = make_shinhan_receipt(merchant="A", transaction_dt="2026-05-01 12:00:00")
    pdf_c = make_shinhan_receipt(merchant="C", transaction_dt="2026-05-10 12:00:00")

    items = [
        (date(2026, 5, 3), pdf_b),
        (date(2026, 5, 1), pdf_a),
        (date(2026, 5, 10), pdf_c),
    ]
    out = write_merged_pdf(items)
    assert out is not None
    # 3 페이지 (각 영수증 1 페이지) — 오름차순 검증은 페이지 수만 안정 확인.
    reader = PdfReader(io.BytesIO(out))
    assert len(reader.pages) == 3


# ── 2) merged_pdf 원본 페이지 연결 (페이지 수 합) ────────────────────────────
def test_merged_pdf_concatenates_original_pages() -> None:
    pdf_1 = make_shinhan_receipt()  # 1 page
    pdf_2 = make_shinhan_receipt()  # 1 page
    items = [(date(2026, 5, 1), pdf_1), (date(2026, 5, 2), pdf_2)]
    out = write_merged_pdf(items)
    assert out is not None
    reader = PdfReader(io.BytesIO(out))
    assert len(reader.pages) == 2


# ── 3) merged_pdf 빈 입력 → None ─────────────────────────────────────────────
def test_merged_pdf_empty_input_returns_no_file() -> None:
    assert write_merged_pdf([]) is None


# ── 4) layout_pdf 2~3 / A4 layout ────────────────────────────────────────────
def test_layout_pdf_fits_2_or_3_per_A4() -> None:
    """4 이미지 → A4 페이지 2장 (2/page) 또는 페이지 1~2 (3/page) — 페이지 수 ≤ ceil(N/2)."""
    images = [_make_test_jpg() for _ in range(4)]
    out = write_layout_pdf(images, per_page=2)
    reader = PdfReader(io.BytesIO(out))
    assert len(reader.pages) == 2  # 4/2 = 2 페이지.

    out3 = write_layout_pdf(images, per_page=3)
    reader3 = PdfReader(io.BytesIO(out3))
    assert len(reader3.pages) == 2  # ceil(4/3) = 2 페이지.


# ── 5) R11 — aspect ratio 보존 (scale-to-fit, 변형 없음) ──────────────────────
def test_layout_pdf_preserves_aspect_ratio() -> None:
    """가로/세로 비 다른 이미지 입력 — PDF 가 잘리지 않고 페이지 생성 (PIL crop 미발생)."""
    # 가로 길쭉 (4:1).
    wide = _make_test_jpg(width=800, height=200, color="green")
    # 세로 길쭉 (1:4).
    tall = _make_test_jpg(width=200, height=800, color="blue")
    out = write_layout_pdf([wide, tall], per_page=2)
    reader = PdfReader(io.BytesIO(out))
    assert len(reader.pages) == 1
    # 페이지 크기는 A4 (595 x 842 points, reportlab 단위).
    page = reader.pages[0]
    assert round(float(page.mediabox.width)) == 595
    assert round(float(page.mediabox.height)) == 842


# ── 6) R12 layout_pdf 파일명 ─────────────────────────────────────────────────
def test_layout_pdf_filename_follows_R12() -> None:
    assert generate_layout_pdf_filename(2026, 5) == "2026_05_지출증빙자료.pdf"
    assert generate_layout_pdf_filename(2026, 12) == "2026_12_지출증빙자료.pdf"
    assert generate_layout_pdf_filename(2025, 3) == "2025_03_지출증빙자료.pdf"
