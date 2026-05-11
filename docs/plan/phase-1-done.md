# Phase 1 — Scaffold + Auth + CI — DONE

- 완료일: 2026-05-11
- 브랜치: 로컬 `main` → `origin/v4`
- 커밋 범위: `1149c3f` ~ Phase 1 종료 시점

## 산출 모듈

| 파일 | 책임 |
|---|---|
| `pyproject.toml` + `uv.lock` | Python 3.12 핀, mypy strict + pydantic plugin, ruff (E,F,W,I,N,B,UP,S,RUF,ASYNC,ANN401), pytest asyncio_mode=auto + real_pdf 마커 |
| `.env.example` | 11 키 (REQUIRE_AUTH, AZURE_*, DATABASE_URL, OLLAMA_*, LLM_ENABLED, LOG_LEVEL, CORS_ORIGINS, MAX_UPLOAD_SIZE_MB, MAX_BATCH_SIZE_MB) |
| `.github/workflows/ci.yml` | ruff + mypy + pytest (`-m "not real_pdf"`) + pip-audit --strict |
| `app/main.py` | `create_app()` factory — Settings/Verifier 싱글톤, 미들웨어/핸들러/라우터 등록 |
| `app/core/config.py` | `Settings` (pydantic-settings) + REQUIRE_AUTH ↔ Azure 자격 boot-time validator |
| `app/core/auth.py` | `AzureADVerifier` — async httpx + 1h TTL JWKS 캐시 + RS256 jose 검증 + 시간 주입 (`now` 콜러블) |
| `app/core/logging.py` | structlog JSON 로거 + `CorrelationIdMiddleware` (X-Correlation-Id uuid4) + PII 마스킹 (카드번호/한글 파일명) |
| `app/core/errors.py` | `AppError` 계층 (BadRequest/Unauthorized/Forbidden/NotFound/Conflict/Unprocessable) + 비공개 500 핸들러 |
| `app/api/deps.py` | `get_current_user` — `app.state.verifier` 재사용으로 JWKS 캐시 공유 |
| `app/api/routes/health.py` | `/healthz` (liveness) + `/readyz` (db/ollama/storage component report) |
| `app/api/routes/auth.py` | `/auth/config` (FE 분기용) + `/auth/me` (Depends) |
| `app/schemas/auth.py` | `UserInfo`, `AuthConfigResponse` |
| `docs/decisions/ADR-001` | `disallow_any_explicit` 제거 사유 — pydantic v2 BaseModel 메타클래스 비호환 |

## 테스트 카운트

총 **18 케이스 통과** (`pytest -q` 18 dots, 모두 `not real_pdf`):

| 파일 | 케이스 | 갯수 |
|---|---|---|
| `tests/unit/test_scaffold.py` | app boot / /healthz / /readyz / Settings env / validator 부팅 차단 | 5 |
| `tests/unit/test_auth.py` | stub mode / garbage token / JWKS 1h TTL (cache hit + miss) / /auth/config / /auth/me stub / /auth/me 401 missing-Bearer | 7 |
| `tests/unit/test_logging.py` | X-Correlation-Id header / correlation_id 로그 주입 / 카드번호 마지막 4 / 한글 파일명 session+idx | 4 |
| `tests/unit/test_errors.py` | AppError → JSON code+message / unhandled 500 + 스택트레이스 비노출 | 2 |

분류: 단위 18 / 통합 0 / e2e 0 / smoke 0.
(통합·e2e·smoke 는 Phase 2~6 에서 라우터/DB/외부 의존성이 추가될 때 생성 예정.)

## DoD 게이트

- [x] `pytest -q` 18 passed
- [x] `mypy --strict app/` 0 error (14 source files)
- [x] `ruff check app/ tests/` clean
- [x] `ruff format --check app/ tests/` clean
- [x] `uv run pip-audit --strict` clean (pytest 9.0.3 + starlette 0.49.3 + fastapi 0.129.2 로 CVE-2025-71176, CVE-2025-62727 해소)
- [x] `REQUIRE_AUTH=false` 로컬 기동 → `/healthz` 200 + `/auth/me` `oid="default"` 응답 확인
- [x] `REQUIRE_AUTH=true` + `AZURE_TENANT_ID=""` 부팅 시 `ValidationError` raise 확인
- [x] 모든 응답에 `X-Correlation-Id` 헤더 + 모든 로그 라인에 `correlation_id` 키
- [x] `.env.example` 11 키 모두 명시

## 인프라 결정사항 (ADR / 참고)

1. **ADR-001**: `mypy.disallow_any_explicit` 제거 — pydantic v2 `BaseModel` 메타클래스가 내부적으로 `Any` 노출. 대체 장치는 `ruff ANN401` (함수 시그니처 Any 차단) + mypy strict 의 `disallow_any_generics` + `warn_return_any`.
2. **respx 0.21 URL 매처 우회**: 본 환경에서 respx 의 URL exact-match / host-match 모두 매칭 실패 — JWKS cache 테스트는 `httpx.MockTransport` + counter 패턴으로 대체. respx 의존성은 유지 (후속 phase 에서 외부 HTTP mock 으로 활용 여지).
3. **CVE 패치 일괄 upgrade**:
   - `pytest 8.4.2 → 9.0.3` (CVE-2025-71176)
   - `pytest-asyncio 0.24 → 1.3.0` (pytest 9 호환)
   - `starlette 0.48.0 → 0.49.3` (CVE-2025-62727 DoS)
   - `fastapi 0.115 → 0.129.2` (starlette 0.49.x 호환 범위)
4. **GitHub 리모트 매핑**: 로컬 `main` → `origin/v4`. 같은 repo 의 `origin/main` 은 v1~v3 legacy 보존 (force-push 금지). push 명령은 `git push origin HEAD:v4`.
5. **Application 싱글톤**: `Settings` + `AzureADVerifier` 를 `app.state` 에 1회만 생성 → JWKS 캐시가 모든 요청에서 공유.

## Phase 2 진입 의존성

- Phase 1 결과물: `Settings`, `AppError` 계층, `get_current_user`, `correlation_id` 미들웨어, `X-Correlation-Id` 응답 헤더.
- Phase 2 는 `app/db/` 모델 11종 + Alembic 마이그레이션 + Repository 시그니처 `*, user_id: int` 강제를 추가.
