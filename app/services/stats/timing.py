"""Phase 8.7 — 처리시간 경과 계산(tz-safe). aiosqlite 가 tz 를 떨궈 naive 로 읽히므로
프로젝트 UTC 기록 관례에 따라 naive=UTC 로 간주 후 차감(CLAUDE.md)."""

from __future__ import annotations

from datetime import UTC, datetime


def elapsed_seconds(started: datetime, completed: datetime) -> float:
    """경과 초. naive 입력은 UTC 로 정규화(프로젝트는 항상 UTC 기록), aware 는 불변."""
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    if completed.tzinfo is None:
        completed = completed.replace(tzinfo=UTC)
    return (completed - started).total_seconds()
