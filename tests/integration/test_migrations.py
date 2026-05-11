"""Phase 2 — Alembic upgrade head + downgrade base 양방향 검증.

CLAUDE.md §"버전 관리": Alembic 마이그레이션은 upgrade + downgrade 둘 다.
CI 가 upgrade → downgrade → upgrade 3 단계 검증 (Task 2.4 단위 테스트는 1+1 단계).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

# 11 도메인 테이블 — alembic_version 은 별도.
_EXPECTED_DOMAIN_TABLES = {
    "user",
    "card",
    "template",
    "vendor",
    "project",
    "merchant",
    "team_group",
    "team_member",
    "upload_session",
    "transaction",
    "expense_record",
}


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _table_names(sqlite_path: Path) -> set[str]:
    conn = sqlite3.connect(sqlite_path)
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    finally:
        conn.close()
    return {r[0] for r in rows}


def test_alembic_upgrade_head_creates_all_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_file = tmp_path / "mig_up.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    # env.py 가 Settings() 로 읽는 단일 진실의 출처.
    monkeypatch.setenv("DATABASE_URL", db_url)

    cfg = _alembic_cfg(db_url)
    command.upgrade(cfg, "head")

    tables = _table_names(db_file)
    assert _EXPECTED_DOMAIN_TABLES.issubset(tables), (
        f"missing domain tables: {_EXPECTED_DOMAIN_TABLES - tables}"
    )
    assert "alembic_version" in tables


def test_alembic_downgrade_base_is_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_file = tmp_path / "mig_down.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    cfg = _alembic_cfg(db_url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    tables = _table_names(db_file)
    # 도메인 테이블 모두 제거 — alembic_version 만 남거나(=0건 row), 그것도 없을 수 있음.
    domain_left = tables & _EXPECTED_DOMAIN_TABLES
    assert domain_left == set(), f"residual domain tables: {domain_left}"
