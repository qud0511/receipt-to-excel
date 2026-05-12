"""Phase 6.10 — ZIP bundler: XLSX + PDF 묶음.

ADR-010 자료 검증 추천 1: Result 화면의 'ZIP으로 한 번에 받기' action.
파일명 (R12 + user_name): ``{YYYY}_{MM}_지출결의서_{user_name}.zip``.
"""

from __future__ import annotations

import io
import zipfile


def create_zip(files: list[tuple[str, bytes]]) -> bytes:
    """``files = [(display_filename, content)]`` → ZIP bytes.

    한글 파일명은 ZIP UTF-8 flag (0x800) 자동 (Python zipfile).
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files:
            zf.writestr(filename, content)
    return buf.getvalue()


def generate_zip_filename(year: int, month: int, user_name: str) -> str:
    """R12 + user_name 패턴. user_name 빈 문자열이면 user 부분 생략."""
    if user_name:
        return f"{year:04d}_{month:02d}_지출결의서_{user_name}.zip"
    return f"{year:04d}_{month:02d}_지출결의서.zip"
