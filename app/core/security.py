"""Phase 6.1 — UploadGuard: 업로드 3중 검증 (CLAUDE.md 강제).

검증 순서:
1. 확장자 화이트리스트 검사 (.pdf/.jpg/.jpeg/.png/.xlsx/.csv)
2. MIME type 일치 (확장자 ↔ 허용 MIME)
3. 매직바이트 일치 (파일 첫 N 바이트)
4. 크기 제약 (단일 ≤ 50MB / 배치 ≤ 500MB)
5. 디스크 파일명 sanitize — uuid4().hex + suffix
6. 원본명은 ``UploadInfo.original_filename`` metadata 로만 보존

본 module 은 외부 입력 신뢰 0 정책 — caller (Sessions API) 가 multipart 받자마자 호출.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath

_MAX_FILE_BYTES = 50 * 1024 * 1024
_MAX_BATCH_BYTES = 500 * 1024 * 1024

# 확장자 → (허용 MIME, 매직바이트 prefix). CSV 는 매직바이트 없음 (text/csv 만 검사).
_ALLOWED: dict[str, tuple[tuple[str, ...], tuple[bytes, ...] | None]] = {
    ".pdf": (("application/pdf",), (b"%PDF",)),
    ".jpg": (("image/jpeg", "image/jpg"), (b"\xff\xd8\xff",)),
    ".jpeg": (("image/jpeg",), (b"\xff\xd8\xff",)),
    ".png": (("image/png",), (b"\x89PNG\r\n\x1a\n",)),
    ".xlsx": (
        (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
            "application/zip",  # 일부 클라이언트가 ZIP 으로 신고.
        ),
        (b"PK\x03\x04",),
    ),
    ".csv": (("text/csv", "application/csv", "text/plain"), None),
}


class UploadValidationError(ValueError):
    """업로드 검증 실패 — 422 Unprocessable Entity 매핑."""


@dataclass(frozen=True)
class UploadInfo:
    """검증 통과한 업로드 1 건의 metadata.

    AD-1 (한국어 보존): ``original_filename`` 은 한글 그대로.
    보안 (CLAUDE.md): ``disk_filename`` 은 uuid.hex + suffix — ASCII safe.
    """

    original_filename: str
    disk_filename: str
    extension: str
    declared_mime: str
    size: int


class UploadGuard:
    """업로드 검증 단일 진입점. caller 는 항상 ``validate`` / ``validate_batch`` 사용."""

    def validate(
        self,
        *,
        filename: str,
        content: bytes,
        declared_mime: str,
    ) -> UploadInfo:
        """단일 파일 검증 — 통과 시 ``UploadInfo`` 반환, 실패 시 ``UploadValidationError``."""
        ext = _extract_extension(filename)
        if ext not in _ALLOWED:
            raise UploadValidationError(f"허용되지 않은 확장자: {ext}")

        allowed_mimes, magic_prefixes = _ALLOWED[ext]
        if declared_mime not in allowed_mimes:
            raise UploadValidationError(f"MIME 불일치: {declared_mime} (허용: {allowed_mimes})")

        if magic_prefixes is not None and not any(content.startswith(p) for p in magic_prefixes):
            raise UploadValidationError(f"매직바이트 불일치: {filename}")

        if len(content) > _MAX_FILE_BYTES:
            raise UploadValidationError(f"파일 크기 초과: {len(content)} > {_MAX_FILE_BYTES}")

        return UploadInfo(
            original_filename=filename,
            disk_filename=sanitize_to_disk_name(filename),
            extension=ext,
            declared_mime=declared_mime,
            size=len(content),
        )

    def validate_batch(self, items: list[tuple[str, bytes, str]]) -> list[UploadInfo]:
        """다중 파일 검증 — 한 건이라도 실패하면 전체 실패. 배치 총합 ≤ 500MB."""
        total = sum(len(content) for _, content, _ in items)
        if total > _MAX_BATCH_BYTES:
            raise UploadValidationError(f"배치 크기 초과: {total} > {_MAX_BATCH_BYTES}")
        infos: list[UploadInfo] = []
        for filename, content, declared_mime in items:
            infos.append(
                self.validate(filename=filename, content=content, declared_mime=declared_mime)
            )
        return infos


def sanitize_to_disk_name(filename: str) -> str:
    """``filename`` 의 확장자를 보존한 ASCII-safe 디스크명 = ``uuid4().hex + .ext``.

    한글 원본명은 본 함수의 반환값에 절대 포함되지 않음 — 메타 컬럼 별도 저장 책임은 caller.
    """
    ext = _extract_extension(filename)
    return uuid.uuid4().hex + ext


def _extract_extension(filename: str) -> str:
    """``PurePosixPath`` 로 확장자 추출 (lowercase). 확장자 없음 → 빈 문자열."""
    return PurePosixPath(filename).suffix.lower()
