"""Phase 6.1 — FileSystemManager 4 케이스.

CLAUDE.md: "FS 경로는 FileSystemManager.from_config(...).session_upload(...) 단일 진입점,
Path 직접 조립 금지." 본 module 이 user_id scoped 경로 생성을 strict 강제.

디렉토리 구조:
    {root}/users/{user_oid}/
        sessions/{session_id}/uploads/{uuid_filename}
        sessions/{session_id}/outputs/{generated_artifact}
        templates/{template_id}/template.xlsx
"""

from __future__ import annotations

from pathlib import Path

from app.services.storage.file_manager import FileSystemManager


def test_per_user_directory_isolation(tmp_path: Path) -> None:
    """사용자별 디렉토리 격리 — user_a 의 경로가 user_b 경로 아래에 없음."""
    fm = FileSystemManager(root=tmp_path)
    a_path = fm.session_upload_dir(user_oid="user-a", session_id="s1")
    b_path = fm.session_upload_dir(user_oid="user-b", session_id="s1")

    assert "user-a" in str(a_path)
    assert "user-b" in str(b_path)
    # cross-prefix 차단 — a_path 가 b_path 의 prefix 아니고 그 반대도 아님.
    assert not str(a_path).startswith(str(b_path))
    assert not str(b_path).startswith(str(a_path))


def test_template_path_uses_user_dir(tmp_path: Path) -> None:
    """Template 파일 경로는 user 디렉토리 아래."""
    fm = FileSystemManager(root=tmp_path)
    tpath = fm.template_path(user_oid="alice", template_id="t-001")
    # 형태: {root}/users/alice/templates/t-001/template.xlsx
    assert tpath.parent.parent.parent.name == "alice"
    assert tpath.name == "template.xlsx"


def test_session_uploads_dir_creates_on_demand(tmp_path: Path) -> None:
    """session_upload_dir 호출이 디렉토리 자동 생성."""
    fm = FileSystemManager(root=tmp_path)
    target = fm.session_upload_dir(user_oid="bob", session_id="s42", create=True)
    assert target.exists()
    assert target.is_dir()


def test_outputs_dir_creates_on_demand(tmp_path: Path) -> None:
    """session_output_dir 호출이 디렉토리 자동 생성."""
    fm = FileSystemManager(root=tmp_path)
    out = fm.session_output_dir(user_oid="charlie", session_id="s7", create=True)
    assert out.exists()
    assert out.is_dir()
    # output 경로가 session 경로 아래.
    upload = fm.session_upload_dir(user_oid="charlie", session_id="s7")
    assert out.parent == upload.parent
