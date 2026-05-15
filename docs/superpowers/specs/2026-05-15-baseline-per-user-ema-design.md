# 설계 — Phase 8.7 Baseline 사용자별 누적 EMA

> 작성: 2026-05-15 · 유형: 기능 (백엔드 메트릭) · 브랜치 `phase/8.7-baseline-ema`
> 근거: docs/plan/phase-8-plan.md 8.7. 현재 baseline 15분/거래 하드코드
> (sessions.py get_session_stats, dashboard.py) → 사용자별 누적 EMA 로 대체.

## 1. 문제 / 의도

Result 화면 "처리 시간 N분 N초 · 평소 대비 …" 와 Dashboard "절약된 시간" 이
거래당 15분 고정 가정(`baseline_s = tx_count * 15 * 60`)에 의존. 의미가 빈약하고
사용자/추세 무관. 사용자 본인의 누적 처리속도를 기준("평소")으로 삼아 "이번이 내
평소보다 빠른가/느린가"를 보여주도록 전환.

결정 (브레인스토밍 Q1~Q5):
- "평소" = 사용자 본인 누적 평균 처리시간 (자기 대비). 15분 가정 폐기.
- 누적 = EMA, α=0.3 (`core.config` 조정 가능).
- 콜드스타트(첫 세션) = 비교 없음("학습 중"), 단 baseline 시드.
- 갱신 = 파싱 완료 시 1회, 멱등 플래그로 재처리 중복 차단.
- 응답 = 기존 필드명 유지 + `baseline_ready`, time_saved 부호 유지(음수=느림),
  Dashboard 총합만 비음수 클램프.

## 2. 비목표

- FE 텍스트 변경("평소 대비 N분 빠름/느림", "기준 학습 중"). 8.7 은 백엔드
  응답 계약까지. FE 렌더링은 별도 작업으로 플래그.
- 도메인 객체 변경 (baseline 은 인프라 메트릭, 도메인 모델 아님).
- 15분 상수의 타 용도 (없음 — 전 사용처가 본 대체 대상).

## 3. 스키마 변경 (마이그레이션 1개, upgrade+downgrade, sqlite batch_alter_table)

- `User.baseline_s_per_tx: Mapped[float | None]` (nullable, default None) — EMA 누적기.
- `UploadSession.counted_in_baseline: Mapped[bool]` (default False, nullable=False) — 멱등.
- `UploadSession.baseline_ref_s_per_tx: Mapped[float | None]` (nullable) — 이 세션이
  비교한 기준값 스냅샷(count 시점). None = 이 세션이 콜드스타트 시드(=학습 중).

스냅샷 컬럼 근거: `User.baseline_s_per_tx` 는 세션마다 이동하므로, 동일 세션
`/stats` 재조회 시 숫자가 바뀌면 안 됨(안정성, CLAUDE.md silent skew 금지).
세션별 비교 기준을 고정 저장하여 재현성 확보 + 콜드스타트 판별을 None 으로 단순화.

마이그레이션: 0002/0003 과 동일하게 `batch_alter_table` (SQLite ALTER 제약).
upgrade = 3 컬럼 add. downgrade = 3 컬럼 drop. test_migrations 의
upgrade→downgrade→upgrade 통과.

## 4. 갱신 로직

위치: `app/api/routes/sessions.py` 의 `processing_completed_at` 세팅 지점
(현 ~214, ~225 — 파싱 잡 완료, status→awaiting_user 직전/직후 동일 트랜잭션).

순수 계산은 `app/services/stats/baseline.py` 신규 모듈로 분리(테스트 용이,
라우터는 호출만 — CLAUDE.md 단방향 의존 services 뒤):

```
def next_baseline(prior: float | None, sample_s_per_tx: float, *, alpha: float) -> float:
    """prior=None → 시드(sample 그대로). 아니면 EMA."""
    return sample_s_per_tx if prior is None else alpha * sample_s_per_tx + (1 - alpha) * prior
```

라우터 갱신 절차 (파싱 완료 트랜잭션 내, 조건: `tx_count > 0` and
`processing_started_at and processing_completed_at` and
`upload_session.counted_in_baseline is False`):

```
processing_s = (completed - started).total_seconds()
this = processing_s / tx_count
prior = db_user.baseline_s_per_tx
upload_session.baseline_ref_s_per_tx = prior        # 스냅샷(None=시드세션)
db_user.baseline_s_per_tx = next_baseline(prior, this, alpha=settings.baseline_ema_alpha)
upload_session.counted_in_baseline = True
# 동일 commit 으로 영속
```

빈 세션(`tx_count == 0`) 또는 처리 타임스탬프 누락 → 갱신·플래그 모두 skip
(`counted_in_baseline` False 유지, baseline 불변). 재처리가 정상 완료되면 그때 1회 반영.

`core/config.Settings`: `baseline_ema_alpha: float = Field(default=0.3, gt=0, le=1)`.

## 5. 응답 계약

### GET /sessions/{id}/stats (부작용 없음 — 읽기 전용, 갱신은 위 파싱완료 경로만)

기존: `{session_id, processing_time_s, baseline_s, time_saved_s}` (+ 기타 기존 키 유지).
변경:
- `baseline_ready: bool` 신규 = `upload_session.baseline_ref_s_per_tx is not None`.
- 학습 중(`baseline_ready=False`): `baseline_s = None`, `time_saved_s = None`.
- 준비됨: `ref = upload_session.baseline_ref_s_per_tx`
  - `baseline_s = round(ref * tx_count)`
  - `time_saved_s = int(ref * tx_count - processing_s)` — **부호 유지**(음수=평소보다 느림).
- `processing_time_s` = `int(processing_s)` (불변). 처리 타임스탬프 없으면 기존 동작 유지(0).

### Dashboard (dashboard.py time_saved_hours)

- ready 세션(`baseline_ref_s_per_tx is not None`)에 대해
  `signed_i = ref_i * tx_count_i - processing_s_i` 합산.
- `time_saved_hours = max(0, round(sum(signed_i) / 3600))` — 세션별은 정직히
  부호 유지하나 대시보드 동기부여 총합은 비음수(음수 총합 표시는 UX 악화).
- `baseline_ready: bool` = ready 세션이 1건 이상 존재.
- ready 세션 0건 → `time_saved_hours = 0`, `baseline_ready = False`.

기존 schemas (`schemas/autocomplete.py` time_saved_hours 주석, dashboard 응답
모델, stats 응답) 갱신. `_mappers` 무관(도메인↔스키마 매핑 아님 — 인프라 메트릭).

## 6. 영향 / 롤백

- 변경: `app/db/models.py`(3 컬럼), 신규 마이그레이션 1, `app/services/stats/baseline.py`
  신규, `app/api/routes/sessions.py`(갱신 로직 + stats 응답), `app/api/routes/dashboard.py`,
  `app/core/config.py`(alpha), 관련 `app/schemas/*`(baseline_ready), fixtures, tests.
- 도메인/`_mappers`/FS/UI 무변경.
- 롤백: 마이그레이션 downgrade + 커밋 revert. 외부 상태 없음 — 완전 가역.
  (운영 DB 시 컬럼 추가는 무손실; 기존 row 는 baseline None/플래그 False 로 시작 →
  다음 파싱부터 자연 시드.)

## 7. 테스트 (TDD)

단위 `tests/unit/test_baseline.py`:
- `next_baseline(None, x)` == x (시드)
- `next_baseline(prior, x, alpha=0.3)` == 0.3x + 0.7·prior
- alpha 경계 (config 기본 0.3)

통합 `tests/integration/test_session_stats_baseline.py` (+ dashboard):
- 콜드스타트: 첫 세션 stats → `baseline_ready False`, `baseline_s/time_saved_s None`,
  User.baseline_s_per_tx 시드됨, session.counted_in_baseline True.
- 2번째 세션: `baseline_ready True`, time_saved_s 부호(빠름 양수 / 느림 음수) 정확.
- 멱등: 파싱완료 경로 2회 진입(재처리 모사) → EMA 1회만 반영, 플래그 True 유지.
- 빈 세션(tx 0): 갱신·플래그 skip, baseline 불변.
- Dashboard: ready 세션 집계 + 총합 비음수 클램프 + `baseline_ready`.
- **IDOR**: 다른 사용자 세션 stats 403; 사용자 A 의 baseline 이 B 에 누출 안 됨.
- 마이그레이션: upgrade→downgrade→upgrade.

fixtures: 기존 session/user fixture 확장(처리 타임스탬프·tx 수 제어 가능하게).
시간은 `freezegun` 또는 주입 — `datetime.now()` 직접 호출 금지(CLAUDE.md flaky 방지).
```
