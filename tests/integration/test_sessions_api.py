"""Phase 6.7 — Sessions API 통합 테스트 (POST + SSE 우선).

CLAUDE.md 강제: auth / IDOR / 422 4 종 통합 테스트 의무.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from app.db.models import Base, UploadSession, User
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """app + per-test SQLite + per-test storage_root + REQUIRE_AUTH=false."""
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    app = create_app()

    async def _init_db(engine: AsyncEngine) -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_init_db(app.state.db_engine))
    return TestClient(app)


def _png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


def test_post_sessions_creates_db_row_and_enqueues_job(client: TestClient) -> None:
    files = {"receipts": ("receipt.png", _png_bytes(), "image/png")}
    data = {"year_month": "2026-05"}
    response = client.post("/sessions", files=files, data=data)

    assert response.status_code == 201, response.text
    body = response.json()
    assert "session_id" in body
    assert body["status"] == "parsing"


def test_post_sessions_writes_files_to_per_user_dir(
    client: TestClient, tmp_path: Path
) -> None:
    """업로드 후 storage/users/default/sessions/{id}/uploads/ 에 uuid 파일 저장."""
    files = {"receipts": ("한글영수증.png", _png_bytes(), "image/png")}
    data = {"year_month": "2026-05"}
    response = client.post("/sessions", files=files, data=data)
    session_id = response.json()["session_id"]

    upload_dir = (
        tmp_path / "storage" / "users" / "default" / "sessions" / str(session_id) / "uploads"
    )
    assert upload_dir.exists(), f"{upload_dir} not created"
    files_on_disk = list(upload_dir.iterdir())
    assert len(files_on_disk) == 1
    # uuid + .png suffix — 한글 부재.
    assert files_on_disk[0].name.endswith(".png")
    assert "한글영수증" not in files_on_disk[0].name


def test_post_sessions_rejects_wrong_magic_bytes(client: TestClient) -> None:
    bad_content = b"%PDF-1.4\n"
    files = {"receipts": ("fake.png", bad_content, "image/png")}
    data = {"year_month": "2026-05"}
    response = client.post("/sessions", files=files, data=data)
    assert response.status_code == 422


def test_post_sessions_rejects_no_files(client: TestClient) -> None:
    data = {"year_month": "2026-05"}
    response = client.post("/sessions", data=data)
    assert response.status_code == 422


def test_sse_stream_includes_retry_60000(client: TestClient) -> None:
    files = {"receipts": ("a.png", _png_bytes(), "image/png")}
    data = {"year_month": "2026-05"}
    create_resp = client.post("/sessions", files=files, data=data)
    session_id = create_resp.json()["session_id"]

    with client.stream("GET", f"/sessions/{session_id}/stream") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers.get("x-accel-buffering") == "no"
        first_chunk = b""
        for chunk in response.iter_bytes(chunk_size=1024):
            first_chunk += chunk
            if b"retry: 60000" in first_chunk:
                break
            if len(first_chunk) > 4096:
                break
        assert b"retry: 60000" in first_chunk


def test_sse_stream_rejects_idor(client: TestClient) -> None:
    """다른 사용자의 session_id 접근 → 403 (REQUIRE_AUTH=false 환경에서 직접 DB 조작)."""

    async def _make_other_user_session() -> int:
        sessionmaker = client.app.state.db_sessionmaker  # type: ignore[attr-defined]
        async with sessionmaker() as db:
            other = User(oid="other-user", name="other", email="other@test.invalid")
            db.add(other)
            await db.flush()
            sess = UploadSession(
                user_id=other.id,
                year_month="2026-05",
                source_filenames=["x.png"],
                status="parsing",
            )
            db.add(sess)
            await db.flush()
            await db.commit()
            return sess.id  # type: ignore[no-any-return]

    other_session_id = asyncio.run(_make_other_user_session())
    response = client.get(f"/sessions/{other_session_id}/stream")
    assert response.status_code in (403, 404)
