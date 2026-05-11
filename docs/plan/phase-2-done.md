# Phase 2 — DB Models + Migrations + Repositories — DONE

- 완료일: 2026-05-11
- 브랜치: 로컬 `main` → `origin/v4`
- Phase 2 commit 범위: `bc7db52` (Task 2.1) → `fd7b887` (Task 2.3) → Task 2.4 마무리

## 산출 모듈

| 파일/디렉토리 | 책임 |
|---|---|
| `alembic.ini` + `app/db/migrations/env.py` | async-friendly alembic, `Settings.database_url` 단일 진실, `render_as_batch=True` (SQLite ALTER 호환) |
| `app/db/migrations/script.py.mako` | autogenerate 템플릿 |
| `app/db/migrations/versions/0001_initial.py` | 11 테이블 + 인덱스 + CHECK + UNIQUE — autogenerate 결과 |
| `app/db/models.py` | SQLAlchemy 2 ORM 11 테이블, `_TimestampMixin`, `User↔Card` use_alter, `Transaction.amount > 0` CHECK, `xlsx_sheet/card_type/status` enum CHECK |
| `app/db/session.py` | `make_engine` + `make_session_maker` + `get_db` dependency; SQLite `PRAGMA foreign_keys=ON` event |
| `app/db/repositories/__init__.py` | 9 모듈 flat re-export |
| `app/db/repositories/session_repo.py` | UploadSession — `create`, `get` (IDOR 게이트), `list_for_user` |
| `app/db/repositories/transaction_repo.py` | `list_for_session` (session+user 동시 필터), `bulk_create` (caller-error guard) |
| `app/db/repositories/vendor_repo.py` | `autocomplete` (last_used_at DESC NULLS LAST → usage_count DESC), `create_or_get` |
| `app/db/repositories/project_repo.py` | `autocomplete` (user+vendor 양쪽 스코프), `create_or_get` |
| `app/db/repositories/card_meta_repo.py` | `get_by_masked` (AD-2 canonical exact match), `list_for_user` |
| `app/db/repositories/template_repo.py` | `list_for_user`, `get` (IDOR 게이트) — Phase 5 확장 |
| `app/db/repositories/team_group_repo.py` | `list_for_user` — Phase 7 확장 |
| `app/db/repositories/merchant_repo.py` | `get_by_name` — Phase 5 확장 |
| `app/db/repositories/expense_record_repo.py` | `get_by_transaction` — Phase 7 확장 |

## 테스트 카운트

총 **34 케이스 통과** (`pytest -q` 34 dots):

| 파일 | 케이스 | 갯수 |
|---|---|---|
| `tests/unit/test_scaffold.py` (Phase 1) | app boot / /healthz / /readyz / Settings env / validator | 5 |
| `tests/unit/test_auth.py` (Phase 1) | stub / garbage / JWKS cache hit+miss / /auth/config /me /me-401 | 7 |
| `tests/unit/test_logging.py` (Phase 1) | correlation_id header / log line / card PII / 한글 파일명 PII | 4 |
| `tests/unit/test_errors.py` (Phase 1) | AppError 매핑 / 500 비공개 | 2 |
| `tests/unit/test_db_models.py` (Phase 2) | User.oid / Card per-user / Vendor per-user / Project per-vendor / TeamMember cascade / year_month accessor / field_confidence JSON / attendees_json JSON | 8 |
| `tests/unit/test_repositories.py` (Phase 2) | session create user_id / transaction filter session+user / vendor autocomplete order / project autocomplete vendor scope / card_meta canonical / **ForbiddenError on other-user IDOR** | 6 |
| `tests/integration/test_migrations.py` (Phase 2) | upgrade head → 11 tables / downgrade base → clean | 2 |

분류: 단위 32 / 통합 2 / e2e 0 / smoke 0.

## Phase 2 DoD 게이트

- [x] **11 테이블 모두 마이그레이션으로 생성/롤백 가능**
  - `alembic upgrade head` 검증 (test) + `upgrade → downgrade → upgrade` 3 단계 smoke 통과
- [x] **모든 리포지토리 메서드 시그니처에 `user_id: int` 키워드 전용 필수**
  - 9 모듈 전체 `(db, *, user_id: int, ...)` 강제
- [x] **외래키·유니크 제약 검증 테스트 통과**
  - User.oid / Card per-user / Vendor per-user / Project per-vendor + SQLite `PRAGMA foreign_keys=ON`
- [x] **JSON 컬럼 라운드트립 검증**
  - `Transaction.field_confidence` (dict[str, str]) + `ExpenseRecord.attendees_json` (list[str] 한글 포함)
- [x] **vendor·project autocomplete 정렬 정확성 검증**
  - last_used_at DESC NULLS LAST → usage_count DESC → name ASC tiebreak
- [x] **`pytest`, `mypy`, `ruff` 통과**
  - pytest 34 passed, mypy 0 error (31 source files), ruff/format clean
- [x] **IDOR 회귀 차단 (Phase 2 자체 추가 게이트)**
  - `session_repo.get(user_id=other)` → `ForbiddenError`
- [x] **`pip-audit --strict` clean**

## 인프라 결정사항 (Phase 2)

1. **SQLite `PRAGMA foreign_keys=ON`**: `make_engine()` 안에서 `connect` event 로 활성화. v1 의 회귀 — cascade/RESTRICT 가 silent 로 무시되어 orphan row 가 쌓이는 위험을 차단.
2. **`User ↔ Card` 순환 FK**: `User.default_card_id` 에 `use_alter=True, name="fk_user_default_card_id"` — alembic 이 deferred FK 로 처리해 양쪽 테이블 create 순서 무관.
3. **`render_as_batch=True`**: SQLite 의 ALTER TABLE 제약 우회 — 향후 컬럼 추가/변경 마이그레이션 호환.
4. **enum 컬럼**: `String(8)` + `CHECK constraint` 로 표현 (Postgres `ENUM` 미사용). Literal type annotation 으로 mypy strict 검증, DB 레벨에서 CHECK 가 fail-fast.
5. **alembic 1.18 deprecation**: `path_separator=os` 명시 — `prepend_sys_path` 의 legacy 분리 규칙 deprecation 해소.
6. **conftest `tmp_path` DB 격리**: 모든 테스트가 격리된 SQLite 파일에서 동작 → cross-test leak 0건.

## Phase 3 진입 의존성

- Phase 2 산출: 11 ORM 모델 + 0001 마이그레이션 + 9 리포지토리 (user_id keyword-only) + IDOR 게이트
- Phase 3 추가 작업:
  - `app/domain/` (pure Pydantic v2) — `ParsedTransaction`, `ExpenseRecord` (도메인), `TemplateMap`, `confidence` 라벨링 정책
  - `services/parsers/base.py` — `ParserBase` ABC + `ParseError` 계층 + `ParsedTransaction` 계약
  - `services/extraction/confidence_labeler.py`
  - `schemas/_mappers.py` 의 한↔영 매핑 진입점
