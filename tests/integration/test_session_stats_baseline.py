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


# ── get_session_stats 계약 (Phase 8.7 Task 4 Part C) ──────────────────────────


@pytest.fixture
def client(tmp_path, monkeypatch):
    """test_sessions_api.py 와 동일 패턴 — per-test SQLite + storage + REQUIRE_AUTH=false."""
    import asyncio
    from pathlib import Path

    from app.main import create_app
    from fastapi.testclient import TestClient
    from sqlalchemy.ext.asyncio import AsyncEngine

    assert isinstance(tmp_path, Path)
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    app = create_app()

    async def _init_db(engine: AsyncEngine) -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_init_db(app.state.db_engine))
    return TestClient(app)


def _seed_session(
    client, *, baseline_ref, processing_s, tx_count, oid="default", with_timestamps=True
):
    """실 ORM 시드: User(oid) + UploadSession(naive 타임스탬프) + tx_count Transaction.

    processing_started/completed_at 을 NAIVE 로 넣어 aiosqlite 재로딩 경로(naive)
    회귀를 의도적으로 자극 — Task-3 회귀 락.

    with_timestamps=False 면 두 타임스탬프 컬럼을 None 으로 남겨
    get_session_stats 의 processing_s=0.0 분기를 잠근다.
    """
    import asyncio
    from datetime import date as _date

    from app.db.models import Transaction, UploadSession

    sm = client.app.state.db_sessionmaker

    async def _seed() -> int:
        async with sm() as db:
            user = await user_repo.get_or_create_by_oid(db, oid=oid, name="t")
            now = datetime.now(UTC)
            year_month = f"{now.year:04d}-{now.month:02d}"
            started = datetime(2026, 5, 15, 12, 0, 0)  # NAIVE — SQLite 재로딩 경로 자극.
            sess = UploadSession(
                user_id=user.id,
                year_month=year_month,
                source_filenames=["a.png"],
                status="awaiting_user",
                processing_started_at=started if with_timestamps else None,
                processing_completed_at=(
                    started + timedelta(seconds=processing_s) if with_timestamps else None
                ),
                baseline_ref_s_per_tx=baseline_ref,
                counted_in_baseline=True,
            )
            db.add(sess)
            await db.flush()
            for _ in range(tx_count):
                db.add(
                    Transaction(
                        session_id=sess.id,
                        user_id=user.id,
                        merchant_name="가맹점",
                        transaction_date=_date(2026, 5, 15),
                        amount=1000,
                        card_provider="테스트카드",
                        parser_used="rule_based",
                        field_confidence={},
                        source_filename="x.png",
                        source_file_path="x.png",
                    )
                )
            await db.commit()
            return sess.id

    return asyncio.run(_seed())


def _get_stats_as(client, sid, *, oid):
    """다른 사용자로 GET — 본 프로젝트 auth stub 은 oid='default' 고정이라
    per-request 신원 전환 불가. 세션은 'owner' user_id 로 시드돼 있고 요청은
    auth stub 의 기본 'default' 사용자로 나가므로 session_repo.get 이
    ForbiddenError(403) 를 던지는지로 IDOR 격리를 검증한다 (oid 인자는 문서용).
    """
    _ = oid
    return client.get(f"/sessions/{sid}/stats")


def test_stats_cold_start_returns_not_ready(client) -> None:
    sid = _seed_session(client, baseline_ref=None, processing_s=100, tx_count=2)
    body = client.get(f"/sessions/{sid}/stats").json()
    assert body["baseline_ready"] is False
    assert body["baseline_s"] is None
    assert body["time_saved_s"] is None
    assert body["processing_time_s"] == 100  # tz-naive reload must NOT raise


def test_stats_ready_signed_saved(client) -> None:
    sid = _seed_session(client, baseline_ref=60.0, processing_s=100, tx_count=2)
    body = client.get(f"/sessions/{sid}/stats").json()
    assert body["baseline_ready"] is True
    assert body["baseline_s"] == 120
    assert body["time_saved_s"] == 20


def test_stats_ready_negative_when_slower(client) -> None:
    sid = _seed_session(client, baseline_ref=30.0, processing_s=100, tx_count=2)
    assert client.get(f"/sessions/{sid}/stats").json()["time_saved_s"] == -40


def test_stats_other_user_forbidden(client) -> None:
    sid = _seed_session(client, baseline_ref=60.0, processing_s=100, tx_count=2, oid="owner")
    r = _get_stats_as(client, sid, oid="intruder")
    assert r.status_code == 403


def test_stats_missing_timestamps_processing_zero(client) -> None:
    sid = _seed_session(
        client, baseline_ref=60.0, processing_s=100, tx_count=2, with_timestamps=False
    )
    body = client.get(f"/sessions/{sid}/stats").json()
    assert body["processing_time_s"] == 0
    # ref 존재 → baseline_ready True, baseline_s=120, time_saved_s = 120 - 0 = 120
    assert body["baseline_ready"] is True
    assert body["baseline_s"] == 120
    assert body["time_saved_s"] == 120


# ── dashboard 누적 baseline 집계 (Phase 8.7 Task 5 Part B) ───────────────────


def test_dashboard_aggregates_ready_sessions(client) -> None:
    _seed_session(client, baseline_ref=60.0, processing_s=100, tx_count=2)
    _seed_session(client, baseline_ref=60.0, processing_s=80, tx_count=2)
    body = client.get("/dashboard/summary").json()
    assert body["this_year"]["baseline_ready"] is True
    assert isinstance(body["this_year"]["time_saved_hours"], int)
    assert body["this_year"]["time_saved_hours"] >= 0


def test_dashboard_not_ready_when_no_ready_sessions(client) -> None:
    _seed_session(client, baseline_ref=None, processing_s=100, tx_count=2)
    body = client.get("/dashboard/summary").json()
    assert body["this_year"]["baseline_ready"] is False
    assert body["this_year"]["time_saved_hours"] == 0
