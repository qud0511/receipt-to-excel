# Baseline 사용자별 누적 EMA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 거래당 15분 하드코드 baseline 을 사용자 본인 누적 EMA(자기 대비)로 대체하고 stats/dashboard 응답을 `baseline_ready`·부호유지 계약으로 전환.

**Architecture:** 순수 EMA 계산은 `app/services/stats/baseline.py` 에 격리. 파싱 잡 성공 완료 시점(`_run_job_background` 성공 분기)에서 멱등하게 `User.baseline_s_per_tx`(EMA) 갱신 + 세션에 비교 기준 스냅샷(`UploadSession.baseline_ref_s_per_tx`) 저장. GET stats/dashboard 는 스냅샷만 읽어 안정적 응답.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async, Alembic(batch), pydantic-settings, pytest, uv.

---

## File Structure

- Create: `app/services/stats/__init__.py` (빈 패키지 init)
- Create: `app/services/stats/baseline.py` — 순수 `next_baseline()` EMA 함수. 책임 1개.
- Create: `app/db/migrations/versions/0004_phase8_baseline_columns.py` — 3컬럼 추가(양방향).
- Create: `tests/unit/test_baseline.py`
- Create: `tests/integration/test_session_stats_baseline.py`
- Modify: `app/core/config.py` — `baseline_ema_alpha` 설정.
- Modify: `app/db/models.py` — User 1컬럼 + UploadSession 2컬럼.
- Modify: `app/db/repositories/user_repo.py` — `get_by_id`.
- Modify: `app/api/routes/sessions.py` — 파싱완료 갱신 + `get_session_stats` 응답.
- Modify: `app/api/routes/dashboard.py` — ready 세션 집계 + `baseline_ready`.
- Modify: `app/schemas/autocomplete.py` — `ThisYearMetric.baseline_ready`.
- Test ref (회귀 오라클, 무변경 통과): `tests/integration/test_sessions_api.py`, `tests/integration/test_autocomplete_dashboard.py`, `tests/integration/test_migrations.py`.

프로젝트 규약(모든 Task 공통): 작업 디렉토리 `/bj-dev/v4`, 모든 Bash 는 `cd /bj-dev/v4 && ...` prefix. 브랜치 `phase/8.7-baseline-ema` 직접 커밋(워크트리/별도브랜치 없음). section-sign 문자 금지. mypy --strict·ruff 통과. `datetime.now()` 직접 호출 금지(주입/freezegun). 시크릿/PII 로깅 금지.

---

## Task 1: config alpha + 순수 EMA 함수

**Files:**
- Modify: `app/core/config.py`
- Create: `app/services/stats/__init__.py`, `app/services/stats/baseline.py`
- Test: `tests/unit/test_baseline.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/unit/test_baseline.py`:

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `cd /bj-dev/v4 && uv run pytest tests/unit/test_baseline.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.stats'`

- [ ] **Step 3: 구현**

Create `app/services/stats/__init__.py` (빈 파일, 내용 없음).

Create `app/services/stats/baseline.py`:

```python
"""Phase 8.7 — 사용자별 처리시간 baseline EMA (순수 함수, openpyxl/IO 무관)."""

from __future__ import annotations


def next_baseline(
    prior: float | None,
    sample_s_per_tx: float,
    *,
    alpha: float,
) -> float:
    """다음 baseline(거래당 초). prior=None 이면 시드(sample 그대로), 아니면 EMA.

    EMA: alpha*sample + (1-alpha)*prior. alpha 클수록 최근값 가중.
    """
    if prior is None:
        return sample_s_per_tx
    return alpha * sample_s_per_tx + (1.0 - alpha) * prior
```

Modify `app/core/config.py` — `Settings` 클래스에 `max_batch_size_mb` 필드 바로 아래(또는 관측성 그룹 인근, 기존 Field 패턴과 동일하게) 추가:

```python
    # Phase 8.7: 사용자별 baseline EMA 평활 계수. 클수록 최근 세션 가중.
    baseline_ema_alpha: float = Field(default=0.3, gt=0, le=1)
```

(`Field` 가 이미 import 되어 있음 — `from pydantic import Field`. 없으면 import 에 추가.)

- [ ] **Step 4: 통과 확인**

Run: `cd /bj-dev/v4 && uv run pytest tests/unit/test_baseline.py -q && uv run mypy --strict app/services/stats/baseline.py app/core/config.py && uv run ruff check app/services/stats/ app/core/config.py tests/unit/test_baseline.py && uv run ruff format --check app/services/stats/ tests/unit/test_baseline.py`
Expected: 3 passed / mypy Success / ruff All checks passed / format clean. (format 불일치 시 `uv run ruff format <경로>` 후 재확인.)

- [ ] **Step 5: 커밋**

```bash
cd /bj-dev/v4 && git add app/services/stats/ app/core/config.py tests/unit/test_baseline.py && git commit -m "$(cat <<'EOF'
[P8.7] feat: baseline EMA 순수 함수 + config alpha

next_baseline(prior, sample, alpha): prior None=시드, else EMA.
Settings.baseline_ema_alpha 기본 0.3.

Refs: docs/superpowers/specs/2026-05-15-baseline-per-user-ema-design.md
EOF
)"
```

---

## Task 2: 스키마 3컬럼 + 마이그레이션 (양방향)

**Files:**
- Modify: `app/db/models.py`
- Create: `app/db/migrations/versions/0004_phase8_baseline_columns.py`
- Test: `tests/integration/test_migrations.py` (회귀 오라클 — 무변경, 본 마이그레이션 포함해 통과해야)

- [ ] **Step 1: 기준선 — 기존 마이그레이션 테스트 GREEN 확인**

Run: `cd /bj-dev/v4 && uv run pytest tests/integration/test_migrations.py -q`
Expected: all passed. 카운트 기록(변경 후 동일+신규 검증).

- [ ] **Step 2: models.py 컬럼 추가**

`app/db/models.py` 의 `class User(...)` 에서 `default_card_id` mapped_column 정의 바로 다음 줄에 추가:

```python
    # Phase 8.7: 사용자별 처리시간 baseline EMA 누적기(거래당 초). None=아직 없음.
    baseline_s_per_tx: Mapped[float | None] = mapped_column(Float, nullable=True)
```

`class UploadSession(...)` 에서 `submitted_at` mapped_column 정의 바로 다음 줄에 추가:

```python
    # Phase 8.7: baseline EMA 멱등 — 이미 반영된 세션은 재처리해도 재반영 안 함.
    counted_in_baseline: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    # Phase 8.7: 이 세션이 비교한 baseline 스냅샷(거래당 초). None=콜드스타트 시드(학습 중).
    baseline_ref_s_per_tx: Mapped[float | None] = mapped_column(Float, nullable=True)
```

`app/db/models.py` 상단 import 에 `Float`, `Boolean` 가 SQLAlchemy 에서 import 되어 있는지 확인하고 없으면 기존 `from sqlalchemy import (...)` 묶음에 `Boolean`, `Float` 추가(알파벳 순서 유지, ruff I 정렬).

- [ ] **Step 3: 마이그레이션 생성** — `app/db/migrations/versions/0004_phase8_baseline_columns.py`:

먼저 `cd /bj-dev/v4 && ls app/db/migrations/versions/` 로 직전 리비전 파일을 확인하고, 그 파일 상단의 `revision = "..."` 값을 본 파일의 `down_revision` 으로 사용한다(체인 정확성 필수). 아래 `<PREV_REVISION>` 을 그 값으로 치환:

```python
"""Phase 8.7 — baseline EMA 컬럼.

신규: user.baseline_s_per_tx, upload_session.counted_in_baseline,
upload_session.baseline_ref_s_per_tx. CLAUDE.md: upgrade+downgrade,
SQLite batch_alter_table.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_phase8_baseline_columns"
down_revision = "<PREV_REVISION>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("baseline_s_per_tx", sa.Float(), nullable=True))
    with op.batch_alter_table("upload_session") as batch_op:
        batch_op.add_column(
            sa.Column(
                "counted_in_baseline",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column("baseline_ref_s_per_tx", sa.Float(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("upload_session") as batch_op:
        batch_op.drop_column("baseline_ref_s_per_tx")
        batch_op.drop_column("counted_in_baseline")
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("baseline_s_per_tx")
```

- [ ] **Step 4: 양방향 검증**

Run: `cd /bj-dev/v4 && rm -f /tmp/bl_mig.db && DATABASE_URL="sqlite+aiosqlite:////tmp/bl_mig.db" uv run alembic upgrade head && DATABASE_URL="sqlite+aiosqlite:////tmp/bl_mig.db" uv run alembic downgrade base && DATABASE_URL="sqlite+aiosqlite:////tmp/bl_mig.db" uv run alembic upgrade head && rm -f /tmp/bl_mig.db && uv run pytest tests/integration/test_migrations.py -q`
Expected: alembic 3 단계 무오류 + test_migrations Step 1 카운트와 동일(또는 신규 리비전 포함해 통과). mypy: `uv run mypy --strict app/db/models.py` Success. ruff clean.

- [ ] **Step 5: 커밋**

```bash
cd /bj-dev/v4 && git add app/db/models.py app/db/migrations/versions/0004_phase8_baseline_columns.py && git commit -m "$(cat <<'EOF'
[P8.7] feat: baseline EMA 3컬럼 + 마이그레이션 0004 (양방향)

user.baseline_s_per_tx, upload_session.counted_in_baseline,
upload_session.baseline_ref_s_per_tx. SQLite batch, upgrade+downgrade.

Refs: docs/superpowers/specs/2026-05-15-baseline-per-user-ema-design.md
EOF
)"
```

---

## Task 3: 파싱완료 시 멱등 EMA 갱신

**Files:**
- Modify: `app/db/repositories/user_repo.py` (`get_by_id` 추가)
- Modify: `app/api/routes/sessions.py` (`_run_job_background` 성공 분기)
- Test: `tests/integration/test_session_stats_baseline.py`

- [ ] **Step 1: user_repo.get_by_id 실패 테스트 + 통합 테스트 작성**

Create `tests/integration/test_session_stats_baseline.py` (기존 `tests/integration/test_sessions_api.py` 의 client fixture 패턴을 그대로 따른다 — 그 파일 상단 1~35줄을 읽어 동일한 `client`/`_init_db` fixture 와 import 를 복제):

```python
"""Phase 8.7 — baseline EMA 갱신 + stats/dashboard 계약 통합 테스트."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.db.models import Base, Transaction, UploadSession, User
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
```

- [ ] **Step 2: 실패 확인**

Run: `cd /bj-dev/v4 && uv run pytest tests/integration/test_session_stats_baseline.py::test_get_by_id_returns_user -q`
Expected: FAIL — `AttributeError: module 'app.db.repositories.user_repo' has no attribute 'get_by_id'`

- [ ] **Step 3: user_repo.get_by_id 구현**

`app/db/repositories/user_repo.py` 에 함수 추가(기존 `get_or_create_by_oid` 의 시그니처/스타일·키워드전용 규약을 그대로 따른다 — 파일을 먼저 읽어 import·세션 타입 확인):

```python
async def get_by_id(db: AsyncSession, *, user_id: int) -> User:
    """PK 로 User 조회. 잡 컨텍스트(user_id 만 보유)에서 baseline 갱신용."""
    user = await db.get(User, user_id)
    if user is None:
        raise ValueError(f"user {user_id} not found")
    return user
```

(`AsyncSession`, `User` 가 해당 파일에 이미 import 돼 있으면 재사용. 없으면 기존 import 블록에 추가.)

- [ ] **Step 4: get_by_id 통과 확인**

Run: `cd /bj-dev/v4 && uv run pytest tests/integration/test_session_stats_baseline.py::test_get_by_id_returns_user -q`
Expected: 1 passed

- [ ] **Step 5: 갱신 로직 통합 테스트 작성** — 같은 파일에 append. 잡 백그라운드를 직접 호출하기 복잡하므로, 갱신 로직을 **순수 헬퍼**로 분리해 그 헬퍼를 직접 검증한다(아래 Step 7 에서 헬퍼 구현). append:

```python
def _apply(prior, sample, *, counted, alpha=0.3):
    """Step 7 의 apply_session_baseline 을 통합 시나리오로 검증하기 위한 호출 래퍼."""
    from types import SimpleNamespace

    from app.api.routes.sessions import apply_session_baseline

    user = SimpleNamespace(baseline_s_per_tx=prior)
    sess = SimpleNamespace(
        counted_in_baseline=counted,
        baseline_ref_s_per_tx=None,
        processing_started_at=datetime(2026, 5, 15, tzinfo=UTC),
        processing_completed_at=datetime(2026, 5, 15, tzinfo=UTC) + timedelta(seconds=sample * 2),
    )
    apply_session_baseline(user, sess, tx_count=2, alpha=alpha)
    return user, sess


def test_cold_start_seeds_and_marks_no_comparison() -> None:
    user, sess = _apply(None, 60.0, counted=False)
    # 처리 120s / 2tx = 60s/tx. prior None → 시드.
    assert user.baseline_s_per_tx == pytest.approx(60.0)
    assert sess.baseline_ref_s_per_tx is None  # 콜드 = 학습 중
    assert sess.counted_in_baseline is True


def test_second_session_emas_and_snapshots_prior() -> None:
    user, sess = _apply(100.0, 200.0, counted=False)  # sample=200s/tx
    assert sess.baseline_ref_s_per_tx == pytest.approx(100.0)  # 비교는 직전값
    assert user.baseline_s_per_tx == pytest.approx(0.3 * 200 + 0.7 * 100)  # 130
    assert sess.counted_in_baseline is True


def test_idempotent_when_already_counted() -> None:
    user, sess = _apply(100.0, 200.0, counted=True)
    assert user.baseline_s_per_tx == 100.0  # 불변
    assert sess.counted_in_baseline is True
```

- [ ] **Step 6: 실패 확인**

Run: `cd /bj-dev/v4 && uv run pytest tests/integration/test_session_stats_baseline.py -k "cold_start or second_session or idempotent" -q`
Expected: FAIL — `ImportError: cannot import name 'apply_session_baseline' from 'app.api.routes.sessions'`

- [ ] **Step 7: 헬퍼 구현 + 잡 분기 연결**

`app/api/routes/sessions.py` 에 모듈 함수 추가(파일 상단 import 에 `from app.services.stats.baseline import next_baseline` 추가; `_run_job_background` 정의 근처, 라우터 함수 밖):

```python
def apply_session_baseline(
    db_user: object,
    upload_session: object,
    *,
    tx_count: int,
    alpha: float,
) -> None:
    """파싱 완료 세션의 처리시간으로 사용자 baseline EMA 를 멱등 갱신.

    조건 불충족(이미 반영/빈 세션/타임스탬프 누락) 시 무변경. 호출 측이
    동일 트랜잭션에서 commit. db_user/upload_session 은 ORM 인스턴스(덕타이핑).
    """
    if getattr(upload_session, "counted_in_baseline", False):
        return
    if tx_count <= 0:
        return
    started = getattr(upload_session, "processing_started_at", None)
    completed = getattr(upload_session, "processing_completed_at", None)
    if started is None or completed is None:
        return
    processing_s = (completed - started).total_seconds()
    sample = processing_s / tx_count
    prior = db_user.baseline_s_per_tx
    upload_session.baseline_ref_s_per_tx = prior
    db_user.baseline_s_per_tx = next_baseline(prior, sample, alpha=alpha)
    upload_session.counted_in_baseline = True
```

그리고 `_run_job_background` 의 **성공 분기**(현재 `upload_session.status = "awaiting_user"` / `upload_session.processing_completed_at = datetime.now(UTC)` 직후, `await db.commit()` 직전 — 파일을 읽어 정확 위치 확인. 실패 분기 `status="failed"` 에는 넣지 않음)에 삽입:

```python
            upload_session.status = "awaiting_user"
            upload_session.processing_completed_at = datetime.now(UTC)
            db_user = await user_repo.get_by_id(db, user_id=user_id)
            apply_session_baseline(
                db_user,
                upload_session,
                tx_count=len(tx_rows),
                alpha=request.app.state.settings.baseline_ema_alpha,
            )
            await db.commit()
```

(`request` 가 `_run_job_background` 시그니처에 있는지 확인 — 있으면 `request.app.state.settings`. 없고 다른 app 핸들이 있으면 그 핸들로 settings 접근. `user_repo` 가 이미 import 돼 있음.)

- [ ] **Step 8: 통과 확인 + 회귀 오라클**

Run: `cd /bj-dev/v4 && uv run pytest tests/integration/test_session_stats_baseline.py tests/integration/test_sessions_api.py -q && uv run mypy --strict app/ && uv run ruff check app/ tests/ && uv run ruff format --check app/ tests/`
Expected: 신규 4 passed (get_by_id + 3 시나리오) + test_sessions_api Step1 대비 회귀 0. mypy Success / ruff clean. (format 불일치 시 해당 파일 `ruff format` 후 재확인.)

- [ ] **Step 9: 커밋**

```bash
cd /bj-dev/v4 && git add app/db/repositories/user_repo.py app/api/routes/sessions.py tests/integration/test_session_stats_baseline.py && git commit -m "$(cat <<'EOF'
[P8.7] feat: 파싱완료 시 baseline EMA 멱등 갱신

apply_session_baseline: 빈세션/재처리/타임스탬프누락 skip, 콜드=시드+
ref None, 이후 EMA+ref 스냅샷. user_repo.get_by_id 추가.

Refs: docs/superpowers/specs/2026-05-15-baseline-per-user-ema-design.md
EOF
)"
```

---

## Task 4: get_session_stats 응답 계약

**Files:**
- Modify: `app/api/routes/sessions.py` (`get_session_stats`)
- Test: `tests/integration/test_session_stats_baseline.py` (append)

- [ ] **Step 1: 실패 테스트 append**

`tests/integration/test_session_stats_baseline.py` 에 추가. 기존 `test_sessions_api.py` 의 `client` fixture 와 동일 방식으로 세션/유저/타임스탬프를 DB 에 직접 seed 하는 헬퍼를 쓴다(그 파일 120~140줄의 `_create_tx`/직접 DB seed 패턴 참고). 핵심 단언만:

```python
def test_stats_cold_start_returns_not_ready(client) -> None:  # noqa: ANN001
    # baseline_ref_s_per_tx 가 None 인 세션 → baseline_ready False, null 들.
    sid = _seed_session(client, baseline_ref=None, processing_s=100, tx_count=2)
    r = client.get(f"/sessions/{sid}/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["baseline_ready"] is False
    assert body["baseline_s"] is None
    assert body["time_saved_s"] is None
    assert body["processing_time_s"] == 100


def test_stats_ready_signed_saved(client) -> None:  # noqa: ANN001
    # ref=60s/tx, 2tx → baseline 120s. 처리 100s → +20 절약(양수).
    sid = _seed_session(client, baseline_ref=60.0, processing_s=100, tx_count=2)
    body = client.get(f"/sessions/{sid}/stats").json()
    assert body["baseline_ready"] is True
    assert body["baseline_s"] == 120
    assert body["time_saved_s"] == 20


def test_stats_ready_negative_when_slower(client) -> None:  # noqa: ANN001
    # ref=30s/tx, 2tx → 60s. 처리 100s → -40(평소보다 느림, 부호 유지).
    sid = _seed_session(client, baseline_ref=30.0, processing_s=100, tx_count=2)
    assert client.get(f"/sessions/{sid}/stats").json()["time_saved_s"] == -40


def test_stats_other_user_forbidden(client) -> None:  # noqa: ANN001
    sid = _seed_session(client, baseline_ref=60.0, processing_s=100, tx_count=2, oid="owner")
    r = client.get(f"/sessions/{sid}/stats", headers=_auth_headers("intruder"))
    assert r.status_code in (403, 404)
```

`_seed_session(client, *, baseline_ref, processing_s, tx_count, oid="default")` 와 `_auth_headers(oid)` 는 같은 파일에 헬퍼로 작성한다. `_seed_session` 은: User 생성(or default), UploadSession 생성(`processing_started_at=T`, `processing_completed_at=T+processing_s`, `baseline_ref_s_per_tx=baseline_ref`, `counted_in_baseline=True`, status="awaiting_user", year_month 현재), Transaction `tx_count` 개 bulk insert, session_id 반환. 인증 방식은 기존 `test_sessions_api.py` 가 쓰는 방식과 동일하게 맞춘다(그 파일에서 인증 우회/헤더 패턴을 복사 — 프로젝트는 `REQUIRE_AUTH=false` dev 모드 또는 테스트 의존성 오버라이드를 사용).

- [ ] **Step 2: 실패 확인**

Run: `cd /bj-dev/v4 && uv run pytest tests/integration/test_session_stats_baseline.py -k stats -q`
Expected: FAIL (현재 stats 는 `baseline_ready` 키 없음·15분 하드코드·`max(0,..)` 클램프 → 단언 불일치).

- [ ] **Step 3: get_session_stats 본문 교체**

`app/api/routes/sessions.py` 의 `get_session_stats` 에서 `tx_count = len(txs)` 다음부터 `return {...}` 까지를 아래로 치환(앞쪽 db_user/upload_session/txs 조회는 유지):

```python
    tx_count = len(txs)
    if upload_session.processing_started_at and upload_session.processing_completed_at:
        processing_s = (
            upload_session.processing_completed_at - upload_session.processing_started_at
        ).total_seconds()
    else:
        processing_s = 0.0

    ref = upload_session.baseline_ref_s_per_tx
    baseline_ready = ref is not None
    if baseline_ready:
        baseline_s: int | None = round(ref * tx_count)
        time_saved_s: int | None = int(ref * tx_count - processing_s)
    else:
        baseline_s = None
        time_saved_s = None

    return {
        "session_id": session_id,
        "processing_time_s": int(processing_s),
        "baseline_ready": baseline_ready,
        "baseline_s": baseline_s,
        "time_saved_s": time_saved_s,
        "transaction_count": tx_count,
    }
```

기존 docstring 의 "15분/거래 하드코드" 문장은 "Phase 8.7: 사용자 누적 baseline(스냅샷) 대비. baseline_ref None=학습 중." 으로 갱신(WHY 주석).

- [ ] **Step 4: 통과 + 회귀**

Run: `cd /bj-dev/v4 && uv run pytest tests/integration/test_session_stats_baseline.py tests/integration/test_sessions_api.py -q && uv run mypy --strict app/ && uv run ruff check app/ tests/`
Expected: stats 4 신규 passed + 회귀 0. mypy Success / ruff clean.

- [ ] **Step 5: 커밋**

```bash
cd /bj-dev/v4 && git add app/api/routes/sessions.py tests/integration/test_session_stats_baseline.py && git commit -m "$(cat <<'EOF'
[P8.7] feat: get_session_stats baseline_ready 계약 (부호 유지)

15분 하드코드 제거. baseline_ref 스냅샷 기반: 학습중=null,
준비됨=signed time_saved_s(음수=평소보다 느림). IDOR 테스트 포함.

Refs: docs/superpowers/specs/2026-05-15-baseline-per-user-ema-design.md
EOF
)"
```

---

## Task 5: dashboard 집계 + baseline_ready

**Files:**
- Modify: `app/schemas/autocomplete.py` (`ThisYearMetric`)
- Modify: `app/api/routes/dashboard.py`
- Test: `tests/integration/test_session_stats_baseline.py` (append) + 회귀 `tests/integration/test_autocomplete_dashboard.py`

- [ ] **Step 1: 실패 테스트 append**

```python
def test_dashboard_aggregates_ready_sessions(client) -> None:  # noqa: ANN001
    # ready 세션 2개: (ref60,2tx,proc100)->+20, (ref60,2tx,proc80)->+40. 합 60s.
    _seed_session(client, baseline_ref=60.0, processing_s=100, tx_count=2)
    _seed_session(client, baseline_ref=60.0, processing_s=80, tx_count=2)
    body = client.get("/dashboard").json()
    assert body["this_year"]["baseline_ready"] is True
    # 60s → 0h (round). 음수 클램프/시간 환산만 검증: 0 이상 정수.
    assert isinstance(body["this_year"]["time_saved_hours"], int)
    assert body["this_year"]["time_saved_hours"] >= 0


def test_dashboard_not_ready_when_no_ready_sessions(client) -> None:  # noqa: ANN001
    _seed_session(client, baseline_ref=None, processing_s=100, tx_count=2)  # 학습중
    body = client.get("/dashboard").json()
    assert body["this_year"]["baseline_ready"] is False
    assert body["this_year"]["time_saved_hours"] == 0
```

(dashboard 경로는 실제 라우트가 `/dashboard` 인지 `app/api/routes/dashboard.py` 의 `@router` prefix 로 확인해 맞춘다.)

- [ ] **Step 2: 실패 확인**

Run: `cd /bj-dev/v4 && uv run pytest tests/integration/test_session_stats_baseline.py -k dashboard -q`
Expected: FAIL — 응답에 `this_year.baseline_ready` 없음 / time_saved_hours 가 15분 기반.

- [ ] **Step 3: 스키마 + dashboard 구현**

`app/schemas/autocomplete.py` `class ThisYearMetric` 에 필드 추가:

```python
    baseline_ready: bool  # Phase 8.7: ready 세션 1건 이상이면 True. False=학습 중.
```

그리고 `time_saved_hours` 주석을 `# Phase 8.7: 사용자 누적 baseline 대비 절약(시간, 총합 비음수).` 로 갱신.

`app/api/routes/dashboard.py`:
- 상단 import 에 `from app.db.models import ... Transaction, UploadSession, User` 에 `User` 포함 확인(없으면 추가).
- 기존 `_count_completed_sessions_this_year` 헬퍼 바로 아래에 신규 헬퍼 추가:

```python
async def _sum_time_saved_s_this_year(
    db: AsyncSession,
    user_id: int,
    year: int,
) -> tuple[float, bool]:
    """올해 ready 세션(baseline_ref NOT NULL, counted)들의 signed 절약초 합 + ready 여부.

    signed = ref * tx_count - 처리초. tx_count 는 세션별 Transaction 수.
    """
    year_prefix = f"{year:04d}-"
    tx_count_sq = (
        select(func.count(Transaction.id))
        .where(Transaction.session_id == UploadSession.id)
        .correlate(UploadSession)
        .scalar_subquery()
    )
    rows = (
        await db.execute(
            select(
                UploadSession.baseline_ref_s_per_tx,
                UploadSession.processing_started_at,
                UploadSession.processing_completed_at,
                tx_count_sq,
            )
            .where(UploadSession.user_id == user_id)
            .where(UploadSession.year_month.startswith(year_prefix))
            .where(UploadSession.counted_in_baseline.is_(True))
            .where(UploadSession.baseline_ref_s_per_tx.is_not(None))
        )
    ).all()
    total = 0.0
    ready = False
    for ref, started, completed, txn in rows:
        if ref is None or started is None or completed is None or txn <= 0:
            continue
        ready = True
        processing_s = (completed - started).total_seconds()
        total += ref * txn - processing_s
    return total, ready
```

`get_dashboard_summary` 에서 기존 두 줄

```python
    this_year_tx_count = await _count_transactions_this_year(db, db_user.id, now.year)
    time_saved_hours = (this_year_tx_count * _BASELINE_MIN_PER_TRANSACTION) // 60
```

을 아래로 치환:

```python
    saved_s, baseline_ready = await _sum_time_saved_s_this_year(db, db_user.id, now.year)
    time_saved_hours = max(0, round(saved_s / 3600))
```

`ThisYearMetric(...)` 생성 호출에 `baseline_ready=baseline_ready` 인자 추가. 사용하지 않게 된 `_BASELINE_MIN_PER_TRANSACTION` 상수와 `_count_transactions_this_year`(다른 데서 미사용일 때만) 는 ruff F401/미사용으로 잡히면 제거; 다른 곳에서 쓰면 유지. `_count_transactions_this_year` 가 본 변경 후 어디서도 안 쓰이면 함수째 제거(YAGNI), 쓰이면 유지.

- [ ] **Step 4: 통과 + 회귀**

Run: `cd /bj-dev/v4 && uv run pytest tests/integration/test_session_stats_baseline.py tests/integration/test_autocomplete_dashboard.py -q && uv run mypy --strict app/ && uv run ruff check app/ tests/`
Expected: dashboard 2 신규 passed + test_autocomplete_dashboard 회귀 0(기존 테스트가 time_saved_hours 특정 15분값을 단언했다면 그 테스트가 깨질 수 있음 — 깨지면 그 테스트가 회귀 오라클이 아니라 *명세 변경 대상*이므로, 해당 단언을 새 baseline 계약에 맞게 갱신하고 그 사실을 커밋 메시지에 명시). mypy Success / ruff clean.

- [ ] **Step 5: 커밋**

```bash
cd /bj-dev/v4 && git add app/schemas/autocomplete.py app/api/routes/dashboard.py tests/integration/test_session_stats_baseline.py && git commit -m "$(cat <<'EOF'
[P8.7] feat: dashboard time_saved_hours 누적 baseline 기반 + baseline_ready

15분 하드코드 제거. ready 세션 signed 절약합 → 시간(총합 비음수 클램프).
ThisYearMetric.baseline_ready 추가.

Refs: docs/superpowers/specs/2026-05-15-baseline-per-user-ema-design.md
EOF
)"
```

---

## Task 6: 전체 검증 게이트 (컨트롤러 실행)

**Files:** 없음(검증만)

- [ ] **Step 1: 백엔드 전체 게이트**

Run: `cd /bj-dev/v4 && uv run ruff check app/ tests/ && uv run ruff format --check app/ tests/ && uv run mypy --strict app/ && uv run lint-imports && uv run pytest -m "not real_pdf" -p no:cacheprovider 2>&1 | grep -E "passed|failed" | tail -1 && uv run pip-audit --strict 2>&1 | tail -1`
Expected: ruff clean / format clean / mypy Success / import-linter 3 kept 0 broken / pytest all passed 0 failed / pip-audit no vulnerabilities.

- [ ] **Step 2: 마이그레이션 3단계 재확인**

Run: `cd /bj-dev/v4 && rm -f /tmp/bl_v.db && DATABASE_URL="sqlite+aiosqlite:////tmp/bl_v.db" uv run alembic upgrade head && DATABASE_URL="sqlite+aiosqlite:////tmp/bl_v.db" uv run alembic downgrade base && DATABASE_URL="sqlite+aiosqlite:////tmp/bl_v.db" uv run alembic upgrade head && rm -f /tmp/bl_v.db && echo OK`
Expected: OK (무오류).

- [ ] **Step 3: 최종 보고**

`git log --oneline -6` 으로 Task1~5 커밋 5개 확인. pytest 정확 카운트(이전 261 → 신규 단위 3 + 통합 ~9 증가 예상) 보고. push 는 사용자 명시 요청 시(별도 feature 브랜치, PR 워크플로).

---

## Self-Review (작성자 점검)

**Spec 커버리지:** §3 스키마=Task2 / §4 갱신로직=Task3(헬퍼+잡분기) / §5 stats 계약=Task4 / §5 dashboard=Task5 / §1 EMA·config=Task1 / §7 테스트=각 Task TDD(단위 EMA, 콜드/2nd/멱등/빈세션은 Task3 _apply 시나리오, stats null/부호/IDOR=Task4, dashboard 집계/클램프/ready=Task5, 마이그레이션=Task2/6). 누락: 빈 세션(tx 0) skip 은 Task3 `apply_session_baseline` 의 `tx_count<=0` 분기로 구현되며 단위적으로 `_apply` 변형으로 커버 가능 — Task3 Step5 테스트에 빈세션 케이스 1개 추가 권장(`_apply(None,0,...)` 류는 tx_count 파라미터 0). **수정**: Task3 Step5 에 `test_empty_session_skips` 추가:

```python
def test_empty_session_skips() -> None:
    from types import SimpleNamespace
    from app.api.routes.sessions import apply_session_baseline
    user = SimpleNamespace(baseline_s_per_tx=100.0)
    sess = SimpleNamespace(counted_in_baseline=False, baseline_ref_s_per_tx=None,
                           processing_started_at=datetime(2026,5,15,tzinfo=UTC),
                           processing_completed_at=datetime(2026,5,15,tzinfo=UTC)+timedelta(seconds=10))
    apply_session_baseline(user, sess, tx_count=0, alpha=0.3)
    assert user.baseline_s_per_tx == 100.0
    assert sess.counted_in_baseline is False
```
(Task3 Step6 의 `-k` 필터에 `or empty_session` 추가.)

**Placeholder 스캔:** `<PREV_REVISION>` 은 의도된 지시(직전 리비전 확인 후 치환) — 실행자가 `ls versions/` 로 결정. 그 외 모든 코드 스텝 실코드 포함. "회귀 오라클 깨지면 명세 변경 대상" 류는 구체 지침(갱신+커밋명시) 동반 — 모호 아님.

**타입 일관성:** `next_baseline(prior: float|None, sample_s_per_tx, *, alpha)` Task1 정의 ↔ Task3 호출 일치. `apply_session_baseline(db_user, upload_session, *, tx_count, alpha)` Task3 정의 ↔ 테스트 호출 일치. `baseline_ref_s_per_tx`/`counted_in_baseline`/`baseline_s_per_tx` 컬럼명 Task2 정의 ↔ Task3/4/5 사용 일치. 응답 키 `baseline_ready`/`baseline_s`/`time_saved_s` Task4 ↔ 테스트 일치. `ThisYearMetric.baseline_ready` Task5 스키마 ↔ 테스트 일치.
