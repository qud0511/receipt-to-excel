"""Pytest 공통 설정 — Settings 격리 / .env 자동 로드 차단."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

# CLAUDE.md §"TDD": Flaky 방지 — 환경 변수가 테스트 간에 새지 않도록 자동 격리.
_SETTINGS_ENV_KEYS = (
    "REQUIRE_AUTH",
    "AZURE_TENANT_ID",
    "AZURE_CLIENT_ID",
    "DATABASE_URL",
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
    "LLM_ENABLED",
    "LOG_LEVEL",
    "CORS_ORIGINS",
    "MAX_UPLOAD_SIZE_MB",
    "MAX_BATCH_SIZE_MB",
)


@pytest.fixture(autouse=True)
def _isolate_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[None]:
    """Settings 환경 격리 — .env 자동 로드 차단 + 호스트 환경변수 무력화 + DB tmp 격리."""
    for key in _SETTINGS_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    # DB: 각 테스트마다 임시 SQLite 파일. storage/app.db 오염 / cross-test leak 차단.
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")

    from app.core.config import Settings

    # pydantic-settings 가 .env 를 읽지 못하도록 한 곳에서 차단.
    # 사유: 로컬 개발자의 .env 파일이 테스트 결과를 오염시키는 회귀 방지.
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    yield
