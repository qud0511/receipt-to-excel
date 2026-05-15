"""Phase 8.7 — elapsed_seconds tz-safe 단위 테스트."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.services.stats.timing import elapsed_seconds


def test_both_naive() -> None:
    a = datetime(2026, 5, 15, 12, 0, 0)
    b = datetime(2026, 5, 15, 12, 1, 0)
    assert elapsed_seconds(a, b) == pytest.approx(60.0)


def test_naive_and_aware_mixed() -> None:
    a = datetime(2026, 5, 15, 12, 0, 0)  # naive → UTC
    b = datetime(2026, 5, 15, 12, 0, 30, tzinfo=UTC)
    assert elapsed_seconds(a, b) == pytest.approx(30.0)


def test_both_aware_unchanged() -> None:
    a = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
    b = datetime(2026, 5, 15, 12, 2, 0, tzinfo=UTC)
    assert elapsed_seconds(a, b) == pytest.approx(120.0)
