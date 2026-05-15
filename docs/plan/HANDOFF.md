# Receipt-to-Excel v4 — 세션 인수 문서

> 다음 세션에서 첫 번째로 읽을 파일. CLAUDE.md + 본 문서 + 진행 중 sub-phase
> done.md 만 읽으면 곧장 작업 재개 가능.

- 최종 갱신: 2026-05-15
- HEAD commit: **f26ff56** (origin/v4 동기)
- 브랜치: 로컬 `main` → `origin/v4`

## 한 줄 요약

> **Phase 7 (Frontend UI 5 화면) 완료 + Phase 8.1/8.2/8.3 적용**. 누적 백엔드
> 250 + 프런트 133 = **383 GREEN**. 실 백엔드 + dev MSW 양쪽 사용 가능.
> 다음: Phase 8.4~8.12 또는 운영 배포.

## 누적 진척

| 영역 | 단위 | 통합/e2e | 비고 |
| --- | --- | --- | --- |
| 백엔드 (pytest) | 250 (skip 1) | 통합 29 + smoke 42 | Phase 1~6 + 검증 fix |
| 프런트 (vitest) | **133** | 9 Playwright spec | Phase 7 + 8.1/8.2/8.3 |
| 합계 | **383** | + 80 통합/e2e/smoke | — |

mypy --strict, ruff, ESLint max-warnings 0, tsc --noEmit, pip-audit 모두 clean.

## Phase 진행 상태

| Phase | 상태 | done.md |
| --- | --- | --- |
| 1~6 | ✅ 백엔드 24/24 endpoint | `docs/plan/phase-{N}-done.md` |
| 7 (Frontend UI) | ✅ 5 화면 + Docker/nginx + e2e spec | `docs/plan/phase-7-done.md` |
| 7-postfix | ✅ template path + SessionStats 정합 | commit 7fbe703 |
| 8.1 셀 autocomplete | ✅ | commit 124cef8 |
| 8.3 dev MSW worker | ✅ | commit 5f7c7bc |
| 8.2 참석자 hybrid modal | ✅ | commit f26ff56 |
| 8.4~8.12 | ⏸ 대기 | `docs/plan/phase-8-plan.md` §"Sub-phase 후보" |

## 동작 검증 (실 백엔드 + 합성 fixture)

이전 세션에서 한 번 수행:
1. Templates 등록 → Session 생성 → SSE → Transactions → Dashboard → Generate
   XLSX/ZIP → Download — **모두 정상**
2. ⚠ layout_pdf / merged_pdf 다운로드 422 → 합성 영수증 PDF fixture 한계로 추정.
   운영 실 영수증 JPG/PNG 필요. **Phase 8.8 후보**.

## Phase 8 잔여 sub-phase (plan-8 §"Sub-phase 후보" 순서)

| # | 항목 | 예상 | 가치 |
| --- | --- | --- | --- |
| 8.4 | Templates 셀 편집 (formula bar + 셀 PATCH) | 3-4h | UX 깊이 |
| 8.5 | Templates 풀 편집 (border/병합/줌/status bar) | 4-6h | UX 깊이 |
| 8.6 | 메일 발송 (외부 SMTP / Graph API) | 4-6h | 새 기능 |
| 8.7 | Baseline 사용자별 누적 평균 | 1-2h | 정확도 |
| **8.8** | **PDF 422 조사 (검증 라운드 발견)** | **1-2h** | **버그 fix** |
| 8.9 | 시각 회귀 (Chromatic / Percy) | 2-3h | 회귀 차단 |
| 8.10 | Lighthouse / Bundle 분석 | 1h | 성능 metric |
| 8.11 | docker-compose (UI + backend 통합) | 1-2h | 배포 인프라 |
| 8.12 | CI 자동화 (GitHub Actions) | 2-3h | 자동 검증 |

추천 우선순위:
1. **8.8 PDF 조사** — 검증 라운드 미해결 이슈, 빠른 fix 가능
2. **8.11 docker-compose** — 운영 배포 첫 step
3. **8.12 CI** — pytest + vitest + playwright + 보안 gate 자동화

## 진행 재개 절차

```bash
# 1. 백엔드 (FastAPI 8000) — 별도 터미널
cd /bj-dev/v4
DATABASE_URL="sqlite+aiosqlite:///storage/app.db" uv run alembic upgrade head
DATABASE_URL="sqlite+aiosqlite:///storage/app.db" REQUIRE_AUTH=false \
  uv run uvicorn app.main:app --port 8000

# 2. 프런트 dev (Vite 5173 / 5174) — 별도 터미널
cd /bj-dev/v4/ui
npm install  # node_modules 없으면
npm run dev
# → http://localhost:5173  (실 백엔드 proxy)

# 3. 또는 dev MSW (백엔드 없이 mock)
cd /bj-dev/v4/ui
echo "VITE_USE_MOCK=true" > .env.local
npm run dev
# → http://localhost:5173  (mock 5 화면 풀 동작)

# 4. 전체 test (백엔드 + UI)
cd /bj-dev/v4 && uv run pytest tests/ -q
cd /bj-dev/v4/ui && npm test && npm run typecheck && npm run lint && npm run build
```

## 환경 / 인프라

- Python 3.12 + uv 0.11.13 + FastAPI + SQLAlchemy 2 (alembic 0002)
- Node 20.20.2 + npm 10.8.2 + Vite 5.4 + React 18.3 + TypeScript 5.6
- Tailwind 3.4 + shadcn/ui + TanStack Query 5 + Zustand 5 + MSAL.js 3
- Vitest 2 + MSW 2 + Playwright 1.48 (chromium 만 — libnspr4 시스템 deps 부재 시 로컬 실행 불가)
- Docker multi-stage (node:20-alpine → nginx:alpine, non-root, port 8080)

## 알려진 이슈

1. **Playwright libnspr4** — 로컬 e2e 실행 시 `sudo npx playwright install-deps chromium` 필요. CI 환경(공식 Docker image) 에서는 자동.
2. **PDF 422** (Phase 8.8 후보) — 합성 영수증 PDF fixture 로 generate 시 layout_pdf/merged_pdf 만 422. XLSX + ZIP 은 정상. 운영 실 영수증 입력에서 재현 필요.
3. **UploadGuard MIME strict** — curl 등에서 multipart 업로드 시 `;type=application/...` 명시 필요. 브라우저는 자동.
4. **React Router v7 future flag warning** — vitest log 에 경고. v7 마이그레이션 시 처리 (Phase 9+).

## 참조 문서

| 파일 | 용도 |
| --- | --- |
| `CLAUDE.md` | 세션 디폴트 규칙 (보안/가독성/구조/배포/성능/TDD/특이사항) |
| `docs/plan/phase-7-done.md` | Phase 7 (UI) 완료 정리 |
| `docs/plan/phase-8-plan.md` | Phase 8 sub-phase 후보 + 우선순위 |
| `docs/plan/HANDOFF.md` | **본 문서 — 세션 첫 진입 시 읽기** |
| `docs/architecture/current.md` | 현재 동작 아키텍처 (Phase 7 완료 시점) |
| `docs/decisions/ADR-010..013.md` | UI/디자인/Frontend stack/구현 결정 |
| `synthesis/00~05` | 원본 설계 (시작점, 거의 안 변함) |

## 다음 세션 시작 prompt 권장 형식

```
CLAUDE.md + docs/plan/HANDOFF.md 읽고 채택 확인 후 Phase 8.X 진행해.
```

또는 특정 sub-phase 명시:

```
CLAUDE.md + HANDOFF.md 읽고 채택 확인. Phase 8.8 (PDF 422 조사) 진행.
```

---

## 산출 모듈 (Phase 7 + 8.1/8.2/8.3)

### 백엔드 (`app/`)

이미 phase-6-done 까지 안정. 7-postfix 에서 1 패치:
- `app/api/routes/sessions.py` `_resolve_template_path`: storage_root 이중 prefix 차단

### 프런트엔드 (`ui/`)

```
ui/
├── src/
│   ├── App.tsx + main.tsx + styles/{tokens,globals}.css
│   ├── components/
│   │   ├── Icon, Button, Chip, StatusPill, PurposeTile, SuggestChip,
│   │   ├── ConfidenceBadge, TopNav, StepIndicator
│   │   └── Autocomplete  ← P8.1
│   ├── features/
│   │   ├── dashboard/ (KpiCard, RecentList)
│   │   ├── upload/ (DropZone, UploadProgress)
│   │   ├── verify/ (ReceiptPane, VerifyGrid, FilterChips, BulkBar,
│   │   │            SummaryBar, AttendeesModal ← P8.2)
│   │   ├── result/ (DownloadCard)
│   │   └── templates/ (TemplateList, TemplateGrid, MappingChips)
│   ├── pages/ (Dashboard, Upload, Verify, Result, Templates)
│   ├── lib/
│   │   ├── api/ (client, sessions, templates, dashboard, autocomplete, types)
│   │   ├── hooks/ (useDashboardSummary, useTemplates, useVendors, useTransactions,
│   │   │           useSessionStats, useTemplateGrid, useProjects ← P8.1,
│   │   │           useTeamGroups ← P8.2)
│   │   ├── cn, config, format, constants, query, sse, auth
│   ├── stores/upload.ts
│   ├── mocks/ ← P8.3 (data, handlers, browser)
│   ├── test/ (setup, handlers)
│   └── App.test.tsx + 컴포넌트별 *.test.tsx (33 spec files = 133 tests)
├── e2e/ (5 spec + _mocks.ts, libnspr4 필요)
├── Dockerfile + nginx.conf + .dockerignore
└── package.json + vite.config.ts + tailwind.config.ts + ...
```

24 endpoint → TanStack hook 매핑 표는 `docs/plan/phase-7-done.md` 참조.
