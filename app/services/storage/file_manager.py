"""Phase 6.1 — FileSystemManager: per-user FS 단일 진입점.

CLAUDE.md "FS 경로는 ``FileSystemManager.from_config(...).session_upload(...)`` 단일 진입점,
``Path`` 직접 조립 금지" 강제.

디렉토리 구조 (root = storage/):
    storage/users/{user_oid}/
        sessions/{session_id}/
            uploads/{uuid_filename}.{ext}
            outputs/{generated_artifact}
        templates/{template_id}/
            template.xlsx

본 manager 외부에서 Path 조립 시 cross-user 누출 위험 — 본 module 만 통과.
"""

from __future__ import annotations

from pathlib import Path


class FileSystemManager:
    """per-user 경로 생성 + 자동 디렉토리 보장."""

    def __init__(self, root: Path) -> None:
        self._root = root

    @classmethod
    def from_config(cls, *, storage_root: Path) -> FileSystemManager:
        """Settings 에서 받은 root 로 인스턴스. core.config 와의 단일 결합 점."""
        return cls(root=storage_root)

    def user_dir(self, *, user_oid: str, create: bool = False) -> Path:
        """``{root}/users/{user_oid}`` — 모든 사용자별 경로의 base."""
        path = self._root / "users" / user_oid
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def session_upload_dir(
        self, *, user_oid: str, session_id: str, create: bool = False
    ) -> Path:
        """업로드 파일 디스크 저장 위치."""
        path = self.user_dir(user_oid=user_oid) / "sessions" / session_id / "uploads"
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def session_output_dir(
        self, *, user_oid: str, session_id: str, create: bool = False
    ) -> Path:
        """생성 artifact (xlsx/pdf/zip) 저장 위치."""
        path = self.user_dir(user_oid=user_oid) / "sessions" / session_id / "outputs"
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def template_path(self, *, user_oid: str, template_id: str) -> Path:
        """등록된 양식 원본 xlsx 경로 — 파일명 fixed ``template.xlsx``."""
        return (
            self.user_dir(user_oid=user_oid)
            / "templates"
            / template_id
            / "template.xlsx"
        )

    def template_dir(
        self, *, user_oid: str, template_id: str, create: bool = False
    ) -> Path:
        """Template 디렉토리 자체 (파일 외 메타 cache 등 향후 확장 대비)."""
        path = self.user_dir(user_oid=user_oid) / "templates" / template_id
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path
