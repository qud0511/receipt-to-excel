"""Phase 1 스캐폴드 — FastAPI 부팅, /healthz, /readyz, Settings 로딩 + validator."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport
from pydantic import ValidationError


@pytest.fixture
def app() -> FastAPI:
    from app.main import create_app

    return create_app()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def test_app_starts_up(app: FastAPI) -> None:
    """FastAPI 인스턴스 생성 + 라우터 등록 검증."""
    assert isinstance(app, FastAPI)
    paths = {r.path for r in app.routes if hasattr(r, "path")}  # type: ignore[attr-defined]
    assert "/healthz" in paths
    assert "/readyz" in paths


async def test_healthz_returns_ok(client: httpx.AsyncClient) -> None:
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_readyz_reports_components(client: httpx.AsyncClient) -> None:
    r = await client.get("/readyz")
    assert r.status_code == 200
    body: dict[str, Any] = r.json()
    # CLAUDE.md §"성능": /readyz 는 DB·Ollama·storage 실시간 체크.
    assert "db" in body
    assert "ollama" in body
    assert "storage" in body


def test_settings_load_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REQUIRE_AUTH", "false")
    monkeypatch.setenv("OLLAMA_MODEL", "test-model")
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "30")

    from app.core.config import Settings

    s = Settings()
    assert s.require_auth is False
    assert s.ollama_model == "test-model"
    assert s.max_upload_size_mb == 30


def test_settings_validator_blocks_require_auth_true_with_empty_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    monkeypatch.setenv("AZURE_TENANT_ID", "")

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings()
