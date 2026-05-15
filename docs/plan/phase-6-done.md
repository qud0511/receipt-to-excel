# Phase 6 — Sessions + Templates + Upload + Jobs + SSE + 카드사용내역 파서 — DONE

> 임시 워크어라운드 (유지): JPG hana/kakaobank 5건은 vendor_name 수동 입력 — ADR-009 별도 트랙
> (`docs/limitations/ocr_qwen_vendor_name.md`).

- 시작: 2026-05-12
- 완료: 2026-05-12 (commit a5990ff)
- 브랜치: 로컬 `main` → `origin/v4`
- Phase 6 commit 범위: `5c04d6d` (Phase 5 종료) ~ `a5990ff` (Phase 6.10 + current.md 갱신)

## Phase 6 진척

| Sub-phase | 영역 | 단위 | 통합 |
| --- | --- | --- | --- |
| 6.1 | UploadGuard + FileSystemManager | 10 | — |
| 6.2 | alembic 0002 (status rename + 5 컬럼 + GeneratedArtifact) + 3단계 검증 | — | — |
| 6.3 | 카드 사용내역 XLSX/CSV 파서 (shinhan MVP) | 10 | — |
| 6.4 | Transaction Matcher (±5분/금액) | 5 | — |
| 6.5 | Template Analyzer ADR-011 휴리스틱 (Field/Category mode 공존) | 4 신규 | — |
| 6.6 | JobRunner + JobEventBus (8 stage SSE) | 9 | — |
| 6.7a | Sessions API POST + SSE stream | — | 6 |
| 6.7b | ParserRouter wire + GET transactions + PATCH + bulk-tag + receipt + preview-xlsx + generate + download + stats | — | 9 (skip 1) |
| 6.8 | Templates API 9 endpoint | — | 7 |
| 6.9 | 자동완성 4 + Dashboard summary | — | 6 |
| 6.10 | e2e 통합 1 케이스 | — | 1 |
| 6.11 | smoke 회귀 검증 | — | 88.1% 유지 |
| **합계** | — | **38 신규** | **29 (skip 1)** |

## 산출 모듈

| 영역 | 파일 | 책임 |
| --- | --- | --- |
| 보안 | `app/core/security.py` | UploadGuard 3중 검증 + uuid 디스크명 |
| 저장소 | `app/services/storage/file_manager.py` | per-user FS 단일 진입점 |
| 잡 | `app/services/jobs/event_bus.py` | per-session in-memory pub/sub (8 stage) |
| 잡 | `app/services/jobs/runner.py` | BackgroundTasks + Semaphore(2) + JobResult |
| 매처 | `app/services/matchers/transaction_matcher.py` | 영수증 ↔ 카드 사용내역 ±5분/금액 |
| 파서 | `app/services/parsers/card_statement/{base,xlsx_parser,csv_parser}.py` | 카드 사용내역 신규 (shinhan MVP) |
| 파서 | `app/services/parsers/card_statement/providers/shinhan.py` | row dict → ParsedTransaction |
| 분석기 | `app/services/templates/analyzer.py` | ADR-011 suffix-free 휴리스틱 |
| 생성기 | `app/services/generators/zip_bundler.py` | XLSX + PDF 묶음 (UTF-8 한글) |
| repo | `app/db/repositories/{user,template,generated_artifact}_repo.py` | Phase 6 CRUD 확장 |
| 마이그레이션 | `app/db/migrations/versions/0002_phase6_session_status_artifacts.py` | 양방향 + 데이터 보정 |
| API | `app/api/routes/sessions.py` | 10 endpoint |
| API | `app/api/routes/templates.py` | 9 endpoint |
| API | `app/api/routes/autocomplete.py` | 4 endpoint |
| API | `app/api/routes/dashboard.py` | 1 endpoint |
| Schema | `app/schemas/{session,template,autocomplete}.py` | 요청/응답 |

## API 표면 — 24/24 endpoint 가동

| 카테고리 | Method | Path | 상태 |
| --- | --- | --- | --- |
| Sessions | POST | /sessions | ✓ |
| Sessions | GET | /sessions/{id}/stream | ✓ SSE retry:60000 |
| Sessions | GET | /sessions/{id}/transactions | ✓ status filter |
| Sessions | PATCH | /sessions/{id}/transactions/{tx_id} | ✓ last-write-wins |
| Sessions | POST | /sessions/{id}/transactions/bulk-tag | ✓ rollback 409 |
| Sessions | GET | /sessions/{id}/transactions/{tx_id}/receipt | ✓ FileResponse + path traversal 차단 |
| Sessions | GET | /sessions/{id}/preview-xlsx | ✓ row JSON |
| Sessions | POST | /sessions/{id}/generate | ✓ XLSX + PDF + ZIP |
| Sessions | GET | /sessions/{id}/download/{kind} | ✓ 한글 파일명 |
| Sessions | GET | /sessions/{id}/stats | ✓ baseline 15분/거래 |
| Templates | GET | /templates | ✓ |
| Templates | POST | /templates/analyze | ✓ 영속 X |
| Templates | POST | /templates | ✓ 분석 + FS |
| Templates | GET | /templates/{id}/grid | ✓ 셀 grid JSON |
| Templates | PATCH | /templates/{id}/cells | ✓ 셀 값 (style deferred) |
| Templates | PATCH | /templates/{id}/mapping | ✓ chip override |
| Templates | PATCH | /templates/{id} | ✓ 메타 (name) |
| Templates | DELETE | /templates/{id} | ✓ IDOR |
| Templates | GET | /templates/{id}/raw | ✓ 원본 다운로드 |
| 자동완성 | GET | /vendors | ✓ Cache-Control: max-age=300 |
| 자동완성 | GET | /projects | ✓ vendor scope |
| 자동완성 | GET | /attendees | ✓ name 부분 일치 |
| 자동완성 | GET | /team-groups | ✓ 팀 → 멤버 nested |
| Dashboard | GET | /dashboard/summary | ✓ 4 KPI + 최근 5 결의서 |

## 누적 테스트 카운트 (Phase 5 → Phase 6)

| 영역 | Phase 5 종료 | Phase 6 신규 | 합계 |
| --- | --- | --- | --- |
| 단위 | 191 | +38 | **229** |
| 통합 | 6 (skip 1) | +23 (skip 1) | **29 (skip 2)** |
| smoke (real_pdf) | 42 | 0 (parser 무변경) | 42 |
| **합계** | **239** | **+61** | **300 (skip 2)** |

mypy --strict (107 source files) + ruff + pip-audit 통과.

## ADR 매핑

| ADR | Phase 6 영향 |
| --- | --- |
| 003 | real fixture naming (smoke 회귀 안정) |
| 006 | Template Analyzer 결과 활용 (Phase 5 산출 → Phase 6 등록 흐름) |
| 007 | text-aware provider 감지 — Smoke 88% 유지 |
| 008 | rule_based 정규식 보강 — Smoke 88% 유지 |
| 010 | UI 자료 검증 추천 7건 모두 반영 (다운로드 정책 / 카드 파서 / 셀 편집 / 휴리스틱 / baseline / 참석자 hybrid / 영수증 파일명) |
| 011 | Template Analyzer suffix-free + analyzable flag — Field/Category mode 양식 공존 |

## Smoke Gate 회귀 (Phase 6 종료 시점)

`tests/smoke/results/20260515.md` (PII 마스킹, gitignore).

| 회차 | 적용 | PASSED | Δ |
| --- | --- | --- | --- |
| 1차 | (Phase 4.5 baseline) | 11 / 42 = 26 % | — |
| 2차 | text-aware router (ADR-007) | 17 / 42 = 40.5 % | +14.5 pp |
| 3차 | + ADR-008 정규식 보강 | 37 / 42 = 88.1 % | +47.6 pp |
| 4차 (Phase 5 종료) | + ADR-006/011 + Phase 5 generators | 37 / 42 = 88.1 % | 0 (parser 무변경) |
| **5차 (Phase 6 종료)** | + Phase 6 인프라/잡/API/UI 백엔드 | **37 / 42 = 88.1 %** | **0 (회귀 안정)** |

FAILED 5건 = hana 2 + kakaobank 3 (결함 3 — `docs/limitations/ocr_qwen_vendor_name.md` 격리, ADR-009 별도 트랙).

## 검증 가능한 사용자 흐름 (curl, UI 부재 시)

```bash
cd /bj-dev/v4
mkdir -p storage
DATABASE_URL="sqlite+aiosqlite:///storage/app.db" uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# 1. 양식 등록
curl -X POST http://localhost:8000/templates \
  -F "file=@template.xlsx" -F "name=A사 파견용 양식"

# 2. 영수증 + template_id 업로드
curl -X POST http://localhost:8000/sessions \
  -F "receipts=@receipt.pdf" -F "year_month=2026-05" -F "template_id=1"

# 3. SSE 진행
curl -N http://localhost:8000/sessions/1/stream

# 4. 추출 결과
curl http://localhost:8000/sessions/1/transactions

# 5. 검수 (자동완성 활용)
curl "http://localhost:8000/vendors?q=신"
curl http://localhost:8000/team-groups
curl -X PATCH http://localhost:8000/sessions/1/transactions/1 \
  -H "Content-Type: application/json" \
  -d '{"purpose":"중식","headcount":3,"attendees":["홍길동"]}'

# 6. 결의서 생성 + 다운로드
curl -X POST http://localhost:8000/sessions/1/generate
curl -OJ http://localhost:8000/sessions/1/download/xlsx
curl -OJ http://localhost:8000/sessions/1/download/zip

# 7. Dashboard 반영
curl http://localhost:8000/dashboard/summary
```

전 흐름 자동화 e2e 통합 테스트: `tests/integration/test_e2e_session_lifecycle.py` 1/1 GREEN.

## Phase 6 DoD — 모두 통과

- [x] UploadGuard 6 케이스 (CLAUDE.md 보안 강제)
- [x] 카드 사용내역 XLSX 파서 (shinhan MVP, 합성 fixture 통과)
- [x] Sessions API 통합 6+9 케이스 (auth/IDOR/422/bulk-tag rollback)
- [x] SSE retry:60000 + X-Accel-Buffering 검증
- [x] Templates API 통합 7 케이스 (cells PATCH + mapping PATCH + IDOR + 422)
- [x] Generate + Download (3 artifact + 한글 파일명)
- [x] Template Analyzer 단위 +4 (ADR-011 신규)
- [x] e2e 1 케이스 (전 흐름 통과)
- [x] mypy --strict + ruff + pip-audit 통과
- [x] alembic upgrade → downgrade → upgrade 3 단계 통과 (양방향)
- [x] smoke 88.1% 유지 (parser 무변경 sanity check)

## Phase 7 진입 게이트 — **사용자 결정 대기**

CLAUDE.md §"자율 진행 원칙": Phase 경계 (Phase 6 → Phase 7) 사용자 승인 필요.

### Phase 7 작업 범위 (개요)

1. **React 프론트엔드 5 화면** (CreditXLSX 디자인 톤 — ADR-010)
   - Dashboard / Upload / Verify / Result / Templates
   - Inter + JetBrains Mono 폰트, warm gray bg + orange accent
2. **클라이언트 routing** (React Router 또는 Next.js)
3. **API 클라이언트** (fetch/axios — 기존 24 endpoint 호출)
4. **SSE 클라이언트** (EventSource API)
5. **컴포넌트 카탈로그** (shadcn-style — `.btn-ghost`, `.chip`, `.purpose-tile`, `.suggest-chip`, `.status-pill`)
6. **인증 통합** (Azure AD MSAL.js — REQUIRE_AUTH=true 운영 환경)
7. **deploy 인프라** (Dockerfile + docker-compose + healthcheck)

### Phase 7+ 후속 작업

- 메일 발송 (UI Result 의 "팀장님께 메일로 보내기")
- Templates editor 의 style/병합/줌/formula bar 풀 구현
- Baseline 사용자별 누적 평균 (history 누적 후)
- ADR-009 OCR LLM 가맹점명 빈 응답 해소

---

> Phase 6 최종 상태: **단위 229 + 통합 29 (skip 2) = 258 통과 + Smoke 88.1 % 유지 + 백엔드 API 24/24 endpoint 가동**. Phase 7 UI 진입 시 모든 백엔드 stable.
