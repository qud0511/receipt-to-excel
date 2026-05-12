"""Phase 5.3 — merged_pdf: 거래일 ASC 정렬 + 원본 PDF/JPG 페이지 연결.

CLAUDE.md §"특이사항": 영수증 원본 보존 — pypdf 가 페이지 단위 stream 복사.
JPG 입력은 PIL → ReportLab 으로 PDF page 1 장 생성 후 append.
"""

from __future__ import annotations

import io
from datetime import date

from pypdf import PdfReader, PdfWriter


def write_merged_pdf(items: list[tuple[date, bytes]]) -> bytes | None:
    """``items`` (transaction_date, file_bytes) 를 거래일 ASC 로 정렬 후 1 PDF 로 병합.

    빈 입력 → ``None`` (caller 가 파일 생성 skip).
    각 파일은 PDF 가정 (JPG 지원은 후속 phase — 현재는 영수증 원본이 PDF 인 케이스만).
    """
    if not items:
        return None

    sorted_items = sorted(items, key=lambda t: t[0])
    writer = PdfWriter()
    for _dt, content in sorted_items:
        reader = PdfReader(io.BytesIO(content))
        for page in reader.pages:
            writer.add_page(page)

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()
