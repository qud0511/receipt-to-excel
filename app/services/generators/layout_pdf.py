"""Phase 5.3 — layout_pdf: 2~3 / A4 layout + scale-to-fit (aspect ratio 보존, R11).

reportlab Canvas + drawImage 의 자동 scaling — aspect ratio 강제 보존.
R12 파일명 `YYYY_MM_지출증빙자료.pdf`.
"""

from __future__ import annotations

import io
from typing import Literal

from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

PerPage = Literal[2, 3]
_OUTPUT_FILENAME_FMT = "{yyyy:04d}_{mm:02d}_지출증빙자료.pdf"


def write_layout_pdf(images: list[bytes], *, per_page: PerPage = 2) -> bytes:
    """이미지 N 개를 ``per_page`` 단위로 A4 페이지에 배치 → PDF bytes.

    각 페이지를 세로 ``per_page`` 등분 → 이미지를 영역에 scale-to-fit
    (aspect ratio 보존, R11). 빈 입력은 빈 PDF 1 페이지 반환 (caller 가 skip 판단).
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4
    slot_h = page_h / per_page
    margin = 20  # 모든 방향 여백.

    for idx, img_bytes in enumerate(images):
        slot_idx_in_page = idx % per_page
        if idx > 0 and slot_idx_in_page == 0:
            c.showPage()

        # 슬롯 사각형 — 페이지 상단부터 아래로 배치.
        slot_y_top = page_h - slot_idx_in_page * slot_h
        slot_box_w = page_w - 2 * margin
        slot_box_h = slot_h - 2 * margin

        # 이미지 원본 크기 — aspect ratio 계산.
        with Image.open(io.BytesIO(img_bytes)) as img:
            img_w, img_h = img.size
        scale = min(slot_box_w / img_w, slot_box_h / img_h)
        draw_w = img_w * scale
        draw_h = img_h * scale

        # 슬롯 안 중앙 정렬 (좌우 center, 슬롯 상단부터 아래로).
        x = (page_w - draw_w) / 2
        y = slot_y_top - margin - draw_h
        c.drawImage(
            ImageReader(io.BytesIO(img_bytes)),
            x,
            y,
            width=draw_w,
            height=draw_h,
            preserveAspectRatio=True,
        )

    c.save()
    return buf.getvalue()


def generate_layout_pdf_filename(year: int, month: int) -> str:
    """R12 — `YYYY_MM_지출증빙자료.pdf`."""
    return _OUTPUT_FILENAME_FMT.format(yyyy=year, mm=month)
