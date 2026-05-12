"""Phase 6.1 — UploadGuard 6 케이스 (CLAUDE.md "업로드 3중 검증" 강제).

검증:
1. 확장자 ∈ {pdf, jpg, jpeg, png, xlsx, csv} (ADR-010 B-4 신규 형식 포함)
2. MIME type 일치 (확장자 ↔ MIME 매핑)
3. 매직바이트 일치 (파일 헤더 첫 N 바이트)
4. 단일 파일 ≤ 50MB / 배치 ≤ 500MB
5. 디스크 파일명: uuid4().hex + suffix (한글 원본명 제거)
6. 원본 한글 파일명은 metadata 로만 보존
"""

from __future__ import annotations

import pytest
from app.core.security import (
    UploadGuard,
    UploadValidationError,
    sanitize_to_disk_name,
)


def _png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


def _jpg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 100


def _pdf_bytes() -> bytes:
    return b"%PDF-1.4\n" + b"\x00" * 100


def _xlsx_bytes() -> bytes:
    # XLSX is a ZIP — PK\x03\x04 magic.
    return b"PK\x03\x04" + b"\x00" * 100


def _csv_bytes() -> bytes:
    # CSV has no magic — UploadGuard accepts on extension + MIME only for text/csv.
    return b"date,amount\n2026-05-01,1000\n"


# 1) 확장자 + MIME + 매직바이트 통과 (정상 케이스)
def test_accepts_pdf_with_correct_magic_bytes() -> None:
    guard = UploadGuard()
    info = guard.validate(
        filename="receipt.pdf",
        content=_pdf_bytes(),
        declared_mime="application/pdf",
    )
    assert info.extension == ".pdf"
    assert info.size <= 50 * 1024 * 1024


# 2) 확장자 mismatch → 차단
def test_rejects_pdf_with_wrong_extension_or_magic_mismatch() -> None:
    guard = UploadGuard()
    # 매직바이트는 PNG 인데 확장자는 .pdf
    with pytest.raises(UploadValidationError, match="매직바이트"):
        guard.validate(
            filename="malicious.pdf",
            content=_png_bytes(),
            declared_mime="application/pdf",
        )


# 3) 단일 파일 크기 초과 → 차단
def test_rejects_oversized_file() -> None:
    guard = UploadGuard()
    too_big = b"\xff\xd8\xff\xe0" + b"\x00" * (50 * 1024 * 1024 + 1)
    with pytest.raises(UploadValidationError, match="크기"):
        guard.validate(
            filename="huge.jpg",
            content=too_big,
            declared_mime="image/jpeg",
        )


# 4) 배치 합계 초과 → 차단
def test_rejects_oversized_batch() -> None:
    guard = UploadGuard()
    big_jpg = b"\xff\xd8\xff\xe0" + b"\x00" * (40 * 1024 * 1024)
    items = [
        ("a.jpg", big_jpg, "image/jpeg"),
        ("b.jpg", big_jpg, "image/jpeg"),
        ("c.jpg", big_jpg, "image/jpeg"),
        ("d.jpg", big_jpg, "image/jpeg"),
        ("e.jpg", big_jpg, "image/jpeg"),
        ("f.jpg", big_jpg, "image/jpeg"),
        ("g.jpg", big_jpg, "image/jpeg"),
        ("h.jpg", big_jpg, "image/jpeg"),
        ("i.jpg", big_jpg, "image/jpeg"),
        ("j.jpg", big_jpg, "image/jpeg"),
        ("k.jpg", big_jpg, "image/jpeg"),
        ("l.jpg", big_jpg, "image/jpeg"),
        ("m.jpg", big_jpg, "image/jpeg"),
    ]  # 13 files x 40 MB = 520 MB > 500 MB
    with pytest.raises(UploadValidationError, match="배치"):
        guard.validate_batch(items)


# 5) 디스크 파일명 — uuid.hex + suffix (한글 원본 무관)
def test_sanitizes_filename_to_ascii_safe() -> None:
    disk = sanitize_to_disk_name("IMG_2025_12_02_본가설렁탕.jpg")
    # uuid.hex 는 32 hex chars + .jpg = 36 chars 총 길이.
    assert disk.endswith(".jpg")
    assert len(disk) == 32 + 4
    # ASCII-safe.
    assert disk.encode("ascii", errors="strict")  # 예외 없으면 ascii.
    # 한글 부재.
    assert "본가설렁탕" not in disk


# 6) 원본 한글 파일명은 metadata 보존 — sanitize 가 반환값 외 원본도 metadata 로 제공
def test_preserves_korean_filename_in_metadata_not_disk() -> None:
    guard = UploadGuard()
    info = guard.validate(
        filename="IMG_2025_12_02_본가설렁탕.jpg",
        content=_jpg_bytes(),
        declared_mime="image/jpeg",
    )
    # metadata 의 원본명 = 한글 그대로.
    assert info.original_filename == "IMG_2025_12_02_본가설렁탕.jpg"
    # disk 파일명 = uuid.hex + .jpg, 한글 부재.
    assert info.disk_filename.endswith(".jpg")
    assert "본가설렁탕" not in info.disk_filename
