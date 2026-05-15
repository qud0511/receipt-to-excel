"""Phase 8.7 — baseline EMA 순수 함수 단위 테스트."""

from __future__ import annotations

import pytest
from app.services.stats.baseline import next_baseline


def test_seed_when_prior_none() -> None:
    assert next_baseline(None, 120.0, alpha=0.3) == 120.0


def test_ema_when_prior_exists() -> None:
    # 0.3*200 + 0.7*100 = 130
    assert next_baseline(100.0, 200.0, alpha=0.3) == pytest.approx(130.0)


def test_alpha_one_takes_sample() -> None:
    assert next_baseline(100.0, 50.0, alpha=1.0) == pytest.approx(50.0)
