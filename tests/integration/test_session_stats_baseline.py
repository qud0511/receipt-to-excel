"""Phase 8.7 — baseline EMA 갱신 + stats/dashboard 계약 통합 테스트."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from app.db.models import Base, User
from app.db.repositories import user_repo


@pytest.mark.asyncio
async def test_get_by_id_returns_user() -> None:
    from app.db.session import make_engine, make_session_maker

    engine = make_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = make_session_maker(engine)
    async with sm() as db:
        u = User(oid="o1", name="n", email="e@x")
        db.add(u)
        await db.commit()
        got = await user_repo.get_by_id(db, user_id=u.id)
        assert got.id == u.id
        assert got.baseline_s_per_tx is None


def _apply(prior, sample, *, counted, tx_count=2, alpha=0.3):
    """apply_session_baseline 호출 래퍼 (덕타이핑 SimpleNamespace)."""
    from app.api.routes.sessions import apply_session_baseline

    user = SimpleNamespace(baseline_s_per_tx=prior)
    sess = SimpleNamespace(
        counted_in_baseline=counted,
        baseline_ref_s_per_tx=None,
        processing_started_at=datetime(2026, 5, 15, tzinfo=UTC),
        processing_completed_at=datetime(2026, 5, 15, tzinfo=UTC)
        + timedelta(seconds=sample * tx_count),
    )
    apply_session_baseline(user, sess, tx_count=tx_count, alpha=alpha)
    return user, sess


def test_cold_start_seeds_and_marks_no_comparison() -> None:
    user, sess = _apply(None, 60.0, counted=False)
    assert user.baseline_s_per_tx == pytest.approx(60.0)
    assert sess.baseline_ref_s_per_tx is None
    assert sess.counted_in_baseline is True


def test_second_session_emas_and_snapshots_prior() -> None:
    user, sess = _apply(100.0, 200.0, counted=False)
    assert sess.baseline_ref_s_per_tx == pytest.approx(100.0)
    assert user.baseline_s_per_tx == pytest.approx(0.3 * 200 + 0.7 * 100)
    assert sess.counted_in_baseline is True


def test_idempotent_when_already_counted() -> None:
    user, sess = _apply(100.0, 200.0, counted=True)
    assert user.baseline_s_per_tx == 100.0
    assert sess.counted_in_baseline is True


def test_empty_session_skips() -> None:
    user = SimpleNamespace(baseline_s_per_tx=100.0)
    sess = SimpleNamespace(
        counted_in_baseline=False,
        baseline_ref_s_per_tx=None,
        processing_started_at=datetime(2026, 5, 15, tzinfo=UTC),
        processing_completed_at=datetime(2026, 5, 15, tzinfo=UTC) + timedelta(seconds=10),
    )
    from app.api.routes.sessions import apply_session_baseline

    apply_session_baseline(user, sess, tx_count=0, alpha=0.3)
    assert user.baseline_s_per_tx == 100.0
    assert sess.counted_in_baseline is False
