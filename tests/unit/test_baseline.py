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


def test_prior_zero_is_not_treated_as_seed() -> None:
    # prior=0.0 은 falsy 지만 None 아님 → 시드 아님, EMA 계산.
    # 0.3*100 + 0.7*0.0 = 30.0
    assert next_baseline(0.0, 100.0, alpha=0.3) == pytest.approx(30.0)
