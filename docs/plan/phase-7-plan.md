# Phase 7 — Frontend UI (React + Vite + Tailwind + shadcn/ui)

> 진입 게이트: Phase 6 종료 (commit 7570444). 백엔드 API 24/24 endpoint 가동.
> 시작: 2026-05-15
> 참조: ADR-010 (UI 디자인 톤·자료 검증 결과), `ui_reference_1/` (PNG 5장 + JSX/CSS 시각 자료).

## Task 0 사용자 결정 (확정)

| # | 항목 | 결정 | 근거 |
| --- | --- | --- | --- |
| 1 | Framework | **Vite + React 18 + TypeScript** | SPA + FastAPI 분리, MSAL.js SPA flow 자연, nginx 정적 호스팅 |
| 2 | CSS | **Tailwind CSS** | shadcn/ui 기본, ADR-010 의 utility-first 컴포넌트 카탈로그 자연 매핑 |
| 3 | 컴포넌트 | **shadcn/ui (Radix + Tailwind)** | ADR-010 명시, a11y + 소스 복사 모델로 CreditXLSX 톤 자유 |
| 4 | 상태 | **TanStack Query + Zustand** | 24 endpoint 캐싱·SSE·optimistic update + 클라이언트 전용 UI 상태 분리 |
| 5 | 배포 | **Multi-stage Docker (node build → nginx:alpine serve)** | 30MB 이미지, non-root, gzip, SPA fallback |
| 6 | JSX 자료 | **참조 + 재작성** | shadcn/ui 구조로 새로 작성, ui_reference_1/ 는 디자인 의도 시각 자료 |
| 7 | 테스트 | **Vitest + Playwright + MSW** | Vite 네이티브, ESM 자연, 다중 브라우저, MSW 로 API mock |

## 디렉토리 구조 (Phase 7 시작 시 신규)

```
/bj-dev/v4/
├── ui/                              # ★ Phase 7 신규 (백엔드 app/ 과 별도)
│   ├── src/
│   │   ├── main.tsx                 # entry
│   │   ├── App.tsx                  # router root
│   │   ├── styles/
│   │   │   ├── globals.css          # Tailwind base + CSS vars (CreditXLSX 디자인 토큰)
│   │   │   └── tokens.css           # OKLCH color tokens (warm gray/orange/success)
│   │   ├── lib/
│   │   │   ├── api/                 # fetch 클라이언트 + 24 endpoint hooks
│   │   │   │   ├── client.ts        # base fetch + correlation-id + error
│   │   │   │   ├── sessions.ts      # 10 endpoint
│   │   │   │   ├── templates.ts     # 9 endpoint
│   │   │   │   ├── dashboard.ts     # 1 endpoint
│   │   │   │   └── autocomplete.ts  # 4 endpoint
│   │   │   ├── sse.ts               # EventSource 래퍼 + retry
│   │   │   ├── auth.ts              # MSAL.js (REQUIRE_AUTH=true 시 활성)
│   │   │   └── format.ts            # KRW / 날짜 / mask
│   │   ├── stores/                  # Zustand
│   │   │   ├── upload.ts            # 업로드 progress 단계
│   │   │   ├── verify.ts            # Verify 화면 (선택 row, 활성 row)
│   │   │   └── ui.ts                # global UI state (모달, toast)
│   │   ├── components/              # shadcn-style 컴포넌트 카탈로그
│   │   │   ├── ui/                  # shadcn 원본 (button, input, dialog, ...)
│   │   │   ├── Icon.tsx             # SVG icon set (ADR-010 components.jsx 이식)
│   │   │   ├── Chip.tsx             # .chip
│   │   │   ├── StatusPill.tsx       # .status-pill (tagged/untagged)
│   │   │   ├── PurposeTile.tsx      # .purpose-tile
│   │   │   ├── SuggestChip.tsx      # .suggest-chip
│   │   │   ├── ConfidenceBadge.tsx  # high/medium/low/none color coding
│   │   │   └── TopNav.tsx           # brand + step indicator
│   │   ├── pages/                   # 5 화면
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── UploadPage.tsx
│   │   │   ├── VerifyPage.tsx
│   │   │   ├── ResultPage.tsx
│   │   │   └── TemplatesPage.tsx
│   │   ├── features/                # 화면별 sub-component
│   │   │   ├── verify/
│   │   │   │   ├── ReceiptPane.tsx
│   │   │   │   ├── VerifyGrid.tsx
│   │   │   │   ├── TaggingForm.tsx
│   │   │   │   ├── FilterChips.tsx
│   │   │   │   ├── BulkBar.tsx
│   │   │   │   └── SummaryBar.tsx
│   │   │   ├── upload/
│   │   │   │   ├── DropZone.tsx
│   │   │   │   └── UploadProgress.tsx
│   │   │   ├── dashboard/
│   │   │   │   ├── KpiCard.tsx
│   │   │   │   └── RecentList.tsx
│   │   │   ├── result/
│   │   │   │   └── DownloadCard.tsx
│   │   │   └── templates/
│   │   │       ├── TemplateList.tsx
│   │   │       ├── TemplateGrid.tsx
│   │   │       └── MappingChips.tsx
│   │   └── test/
│   │       ├── setup.ts             # Vitest + MSW 초기화
│   │       └── handlers.ts          # MSW handlers (24 endpoint mock)
│   ├── public/
│   │   └── favicon.svg
│   ├── e2e/                         # Playwright
│   │   ├── dashboard.spec.ts
│   │   ├── upload.spec.ts
│   │   ├── verify.spec.ts
│   │   ├── result.spec.ts
│   │   └── templates.spec.ts
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── postcss.config.js
│   ├── playwright.config.ts
│   ├── vitest.config.ts
│   ├── .eslintrc.cjs
│   ├── .prettierrc
│   ├── Dockerfile                   # multi-stage
│   ├── nginx.conf                   # SPA fallback + gzip
│   └── .dockerignore
├── docs/plan/phase-7-plan.md        # 본 문서
└── docs/decisions/ADR-012-frontend-stack-and-design-tokens.md  # 7건 결정 ADR
```

## 디자인 토큰 (ADR-010 + styles2.css 기반)

```css
:root {
  /* Palette — OKLCH (styles2.css 와 일치) */
  --brand:        oklch(0.55 0.18 35);   /* CreditXLSX orange #c96442 톤 */
  --brand-2:      oklch(0.48 0.16 30);
  --brand-soft:   oklch(0.97 0.04 35);
  --brand-border: oklch(0.88 0.06 35);
  --bg:           oklch(0.97 0.012 80); /* warm gray #f0eee9 톤 */
  --surface:      #ffffff;
  --surface-2:    oklch(0.965 0.008 80);
  --border:       oklch(0.92 0.005 80);
  --border-strong:oklch(0.85 0.008 80);
  --text:         oklch(0.25 0.01 80);
  --text-2:       oklch(0.40 0.01 80);
  --text-3:       oklch(0.55 0.01 80);
  --text-4:       oklch(0.70 0.01 80);
  --success:      oklch(0.55 0.15 155);
  --success-soft: oklch(0.96 0.05 155);

  /* Confidence colors (Verify 셀 컬러 코딩) */
  --conf-high:    var(--success);
  --conf-medium:  oklch(0.75 0.16 80);
  --conf-low:     oklch(0.65 0.18 25);
  --conf-none:    oklch(0.65 0.18 25);

  /* Typography */
  --sans:  "Inter", -apple-system, "Pretendard Variable", "Pretendard", sans-serif;
  --mono:  "JetBrains Mono", "Menlo", monospace;

  /* Shadow */
  --shadow-sm: 0 1px 2px rgb(0 0 0 / 0.04);
  --shadow-md: 0 4px 12px rgb(0 0 0 / 0.06);
  --shadow-lg: 0 12px 32px rgb(0 0 0 / 0.12);
}
```

## 24 endpoint → React Query key 매핑

| Endpoint | Hook | Query key |
| --- | --- | --- |
| GET /dashboard/summary | `useDashboardSummary()` | `["dashboard","summary"]` |
| POST /sessions | `useCreateSession()` | mutation |
| GET /sessions/{id}/stream | `useSessionStream(id)` | SSE (EventSource, TanStack X) |
| GET /sessions/{id}/transactions?status= | `useTransactions(id, status)` | `["sessions",id,"transactions",status]` |
| PATCH .../transactions/{tx_id} | `usePatchTransaction()` | mutation + optimistic |
| POST .../transactions/bulk-tag | `useBulkTag()` | mutation (rollback 409 handling) |
| GET .../transactions/{tx_id}/receipt | `useReceiptUrl(...)` | URL builder, not query |
| GET .../preview-xlsx | `usePreviewXlsx(id)` | `["sessions",id,"preview-xlsx"]` |
| POST .../generate | `useGenerate()` | mutation |
| GET .../download/{kind} | URL builder, anchor download |
| GET .../stats | `useSessionStats(id)` | `["sessions",id,"stats"]` |
| GET /templates | `useTemplates()` | `["templates"]` |
| POST /templates/analyze | `useAnalyzeTemplate()` | mutation |
| POST /templates | `useCreateTemplate()` | mutation |
| GET /templates/{id}/grid | `useTemplateGrid(id)` | `["templates",id,"grid"]` |
| PATCH /templates/{id}/cells | `usePatchCells()` | mutation |
| PATCH /templates/{id}/mapping | `usePatchMapping()` | mutation |
| PATCH /templates/{id} | `usePatchTemplateMeta()` | mutation |
| DELETE /templates/{id} | `useDeleteTemplate()` | mutation |
| GET /templates/{id}/raw | URL builder |
| GET /vendors?q= | `useVendors(q)` | `["autocomplete","vendors",q]` (5분 cache) |
| GET /projects?vendor_id= | `useProjects(vendor_id)` | `["autocomplete","projects",vendor_id]` |
| GET /attendees?q= | `useAttendees(q)` | `["autocomplete","attendees",q]` |
| GET /team-groups | `useTeamGroups()` | `["autocomplete","team-groups"]` |

TanStack `staleTime: 5*60*1000` (autocomplete) / `staleTime: 0` (transactions, dynamic) 차등.

## Sub-Phase 분해 (12 step)

### 7.0 — Plan + ADR-012 작성 ✓ 본 문서
- phase-7-plan.md (본 문서)
- ADR-012-frontend-stack-and-design-tokens.md (7건 결정 근거)
- commit `[P7.0] docs: phase-7-plan + ADR-012 frontend stack`

### 7.1 — 프로젝트 setup
- `ui/` 신규 디렉토리, `npm create vite@latest . -- --template react-ts`
- 의존성: react@18, react-dom, react-router-dom, @tanstack/react-query, zustand,
  @azure/msal-browser, @azure/msal-react, tailwindcss, postcss, autoprefixer,
  class-variance-authority, clsx, tailwind-merge, lucide-react (또는 inline SVG)
- 개발: vitest, @testing-library/react, @testing-library/jest-dom, jsdom,
  msw, @playwright/test, eslint, eslint-plugin-react, eslint-plugin-react-hooks,
  prettier, prettier-plugin-tailwindcss
- shadcn CLI: `npx shadcn@latest init` → `button`, `input`, `dialog`, `dropdown-menu`, `select`, `popover`, `tabs`, `tooltip`, `toast`, `progress`, `separator`
- tsconfig strict, ESLint + Prettier 설정, Vite proxy `/api → http://localhost:8000`
- Vitest setup + MSW 초기 handler 1개 (`GET /healthz`)
- 최소 `App.tsx` 가 "CreditXLSX" 텍스트만 렌더
- 테스트: `App.test.tsx` 1건 (브랜드 텍스트 + a11y title)
- commit `[P7.1] feat: ui setup (vite+react+ts+tailwind+shadcn+tanstack+vitest+msw+playwright)`

### 7.2 — 디자인 토큰 + 공통 컴포넌트 카탈로그
- `styles/tokens.css` — OKLCH 변수 정의 (위 표)
- `styles/globals.css` — Tailwind base + tokens import + 폰트 import (Inter + JetBrains Mono — Google Fonts 또는 self-host)
- `tailwind.config.ts` — colors/font 토큰을 Tailwind 클래스로 노출 (`bg-brand`, `text-text-3`, `font-mono` 등)
- 컴포넌트 신규 (각 vitest 1+ test):
  - `Icon.tsx` — 11종 SVG (Search/Filter/Calendar/Download/Plus/Receipt/Close/Chevron/Check/Sparkle + brand CX logo)
  - `Chip.tsx` — variant (default/active/outline)
  - `StatusPill.tsx` — tagged/untagged
  - `PurposeTile.tsx` — icon emoji + label + active 토글
  - `SuggestChip.tsx` — recent badge
  - `ConfidenceBadge.tsx` — high/medium/low/none color
  - `BrandLogo.tsx` — `CX` gradient square
- 단위 7+ vitest GREEN (각 컴포넌트 렌더 + a11y role)
- commit `[P7.2] feat: design tokens + shadcn-style component catalog (7+ unit)`

### 7.3 — API 클라이언트 + TanStack hooks + SSE + MSAL
- `lib/api/client.ts` — fetch wrapper:
  - base URL = `import.meta.env.VITE_API_BASE || "/api"`
  - `X-Correlation-Id` 자동 (uuid4 클라이언트 생성)
  - 401 → MSAL redirect, 403 → toast "권한 없음", 422 → form error 매핑, 5xx → toast "잠시 후 다시"
  - 응답 JSON 자동 파싱, Pydantic AppError 형태 `{detail, code}` 처리
- `lib/api/{sessions,templates,dashboard,autocomplete}.ts` — 24 endpoint typed wrapper (TypeScript types 는 백엔드 schemas/ 와 1:1 매핑)
- `lib/sse.ts` — `subscribeSession(id, onEvent)`:
  - EventSource + reconnect (retry 헤더 존중)
  - `done`/`error` 시 EventSource.close()
  - cleanup hook 패턴
- `lib/auth.ts` — MSAL config:
  - `REQUIRE_AUTH = import.meta.env.VITE_REQUIRE_AUTH === "true"` (dev=false)
  - `MsalProvider` wrapper, `AuthGate` 컴포넌트 (REQUIRE_AUTH=true 면 unauth → redirect)
- TanStack `QueryClient` 설정 (retry 1, staleTime 차등)
- 단위 vitest:
  - API client (correlation-id 헤더, 401 핸들링) 3건 (MSW mock)
  - SSE 래퍼 (이벤트 디스패치, cleanup) 2건
  - useDashboardSummary, useTemplates, useVendors 각 1건 (MSW mock + waitFor)
- 단위 7+ GREEN
- commit `[P7.3] feat: api client + tanstack hooks + sse + msal (7+ unit)`

### 7.4 — App Layout + routing
- `App.tsx` — `<MsalProvider>` (조건부) > `<QueryClientProvider>` > `<BrowserRouter>` > `<TopNav>` + `<Routes>`
- 라우트: `/` → Dashboard / `/upload` → Upload / `/verify/:sessionId` → Verify / `/result/:sessionId` → Result / `/templates` → Templates
- `TopNav.tsx`:
  - 좌측 brand `CX` + "CreditXLSX"
  - 중앙 tab 또는 step indicator (Verify/Upload/Result 경로에서는 `① 업로드 → ② 검수·수정 → ③ 다운로드` step 표시, 기타는 tab 표시)
  - 우측 사용자 avatar + (REQUIRE_AUTH=true 시 logout)
- `StepIndicator.tsx` — current step prop + done/active/pending visual
- 단위 4+ vitest (routing/active state/step done)
- commit `[P7.4] feat: app layout + routing + topnav`

### 7.5 — Dashboard 화면
- `pages/DashboardPage.tsx`:
  - 인사 (백엔드 응답의 user name 또는 MSAL claim)
  - CTA "지출결의서 작성" → `/upload`
  - KPI 4 (this_month: 총지출/결제건수/prev_diff_pct, this_year: 완료/절약시간)
  - 최근 5 결의서 list (각 row: 양식명·영수증 N장·상태 pill)
- `KpiCard.tsx`, `RecentList.tsx`
- MSW handler: GET /dashboard/summary 합성 response
- vitest 4+ (KPI 표시, 빈 상태, status pill 매핑, click navigation)
- commit `[P7.5] feat: Dashboard 화면 (4+ unit GREEN)`

### 7.6 — Upload 화면
- `pages/UploadPage.tsx`:
  - 헤더 "매출전표 일괄 업로드"
  - 드롭존 (drag-over visual + click-fallback `<input type=file multiple>`)
  - 파일 list 표시 (이름·크기·확장자 thumbnail)
  - `template_id` 선택 dropdown (useTemplates 호출, 없으면 "양식 등록 먼저" 안내 + Templates 이동)
  - 업로드 buttons → POST /sessions multipart → session_id → navigate `/verify/{id}`
  - SSE 진행 progress (8 stage: uploaded/ocr/llm/rule_based/resolved/vendor_failed/done/error)
  - file_idx/total + 단계명 한국어 매핑 (`ocr` → "OCR 진행 중", `llm` → "AI 추출 중" 등)
- `DropZone.tsx`, `UploadProgress.tsx`
- MSW: POST /sessions, GET /sessions/{id}/stream SSE mock
- vitest 5+ (드래그/드롭, file input, template 선택 가드, SSE 진행 표시, 완료 시 navigate)
- commit `[P7.6] feat: Upload 화면 + SSE 진행 (5+ unit GREEN)`

### 7.7 — Verify 화면 (가장 큰 sub-phase)
- `pages/VerifyPage.tsx` — split view (좌 380px Receipt pane / 우 grid pane)
- `ReceiptPane.tsx`:
  - 활성 row 의 영수증 이미지 (GET .../receipt URL)
  - prev/next pager
- `VerifyGrid.tsx`:
  - 컬럼: 체크박스 / AI신뢰도% / 일시 / 가맹점 / 분류 / 거래처 / 프로젝트 / 용도 / 인원 / 참석자 / 상태
  - 셀별 ConfidenceBadge + border-left 컬러 코딩
  - 인라인 편집 (거래처/프로젝트 = autocomplete dropdown, 용도 = PurposeTile popover, 인원 = stepper, 참석자 = chip + 멤버 modal)
  - PATCH /sessions/{id}/transactions/{tx_id} optimistic update (TanStack `onMutate` + rollback on 409)
- `FilterChips.tsx`: 전체/필수누락/재확인/완료 (status query 파라미터 전환)
- `BulkBar.tsx`: 선택 N건 표시 + "일괄 적용" (modal 에서 vendor/project/purpose 입력 후 POST bulk-tag, 409 시 toast + 전체 rollback 안내)
- `SummaryBar.tsx`: 총 N건 / 입력완료 M/N / 합계 ₩X / 마감 D-N
- `TaggingForm.tsx`: 우측 sidebar 모드 (Verify 화면 단순화 — sheet 인라인 편집 시 사용 안 함, 추후 mobile/compact 용)
- MSW: 24 endpoint 중 Verify 관련 8개 (transactions GET/PATCH/bulk-tag/receipt/preview-xlsx/stats/vendors/projects/attendees/team-groups)
- vitest 12+ (각 컬럼 렌더 + autocomplete + bulk-tag 409 rollback + filter chip + 신뢰도 컬러 + 마감 카운트다운)
- commit `[P7.7] feat: Verify 화면 split view + grid + bulk-tag (12+ unit GREEN)`

### 7.8 — Result 화면
- `pages/ResultPage.tsx`:
  - 완성 hero (체크 아이콘 + confetti 1회 애니메이션)
  - 다운로드 카드 4:
    - XLSX (`xlsx`) — primary
    - 증빙 PDF (`layout_pdf`) — 모아찍기
    - merged PDF (`merged_pdf`) — 별도 옵션
    - ZIP (`zip`) — primary
  - 메일 발송 button (Phase 7 deferred — disabled + tooltip "Phase 7+ 예정")
  - 통계 footer (processing_time_s / avg_baseline_s 비교)
  - Back "검수 화면으로"
- `DownloadCard.tsx` — anchor href 로 직접 다운로드 (브라우저가 Content-Disposition 처리)
- MSW: GET /sessions/{id}/stats + POST /generate
- vitest 5+ (4 카드 렌더, 다운로드 anchor href 검증, 통계 표시, disabled 메일, Back navigation)
- commit `[P7.8] feat: Result 화면 + 다운로드 4 (5+ unit GREEN)`

### 7.9 — Templates 화면
- `pages/TemplatesPage.tsx`:
  - 좌 sidebar list (`tpl-sidebar`) — useTemplates + 업로드 button (modal)
  - 우 main — 선택된 template 의 grid preview + mapping chips bar + hint
- `TemplateList.tsx` — item (icon + name + meta + active state)
- `TemplateGrid.tsx` — useTemplateGrid → cells JSON 렌더 (read-only Phase 7 / 셀 편집은 Phase 8+, ADR-010 §D-A-3 후보 B 채택 — read-only + 매핑 chips PATCH 만)
- `MappingChips.tsx` — Phase 5 SheetConfig 의 column_map 표시 (A 거래일·B 거래처…), 클릭 시 PATCH /templates/{id}/mapping
- 업로드 modal: POST /templates/analyze → preview → POST /templates 확정
- "양식만 받기" → GET /templates/{id}/raw anchor download
- vitest 6+ (list, grid 렌더, mapping chip 클릭, analyze preview, IDOR 403 처리, delete confirm)
- commit `[P7.9] feat: Templates 화면 + 매핑 chips (6+ unit GREEN)`

### 7.10 — Playwright e2e + Docker multi-stage + nginx
- `e2e/`:
  - dashboard.spec.ts (KPI 표시 + 최근 list)
  - upload.spec.ts (드롭존 + SSE 완료 → Verify 이동)
  - verify.spec.ts (PATCH 셀 + bulk-tag + filter)
  - result.spec.ts (다운로드 anchor 검증)
  - templates.spec.ts (업로드 + mapping chip)
- `playwright.config.ts` — chromium + webkit, baseURL = test server (Vite preview)
- e2e 는 백엔드 mock 으로 진행 (MSW 가 worker 모드로 동작) — 실 백엔드 통합은 Phase 7.11 docker-compose 시 별도 검증
- `Dockerfile`:
  ```
  FROM node:22-alpine AS build
  WORKDIR /app
  COPY package*.json ./
  RUN npm ci --no-audit
  COPY . .
  RUN npm run build

  FROM nginx:alpine
  COPY --from=build /app/dist /usr/share/nginx/html
  COPY nginx.conf /etc/nginx/conf.d/default.conf
  RUN adduser -D -u 1001 ui && chown -R ui:ui /usr/share/nginx/html /var/cache/nginx /var/log/nginx /var/run
  USER ui
  EXPOSE 8080
  HEALTHCHECK --interval=30s --timeout=3s CMD wget -q -O- http://localhost:8080/ || exit 1
  ```
- `nginx.conf` — SPA fallback (`try_files $uri /index.html`), gzip, security headers (X-Content-Type-Options nosniff, X-Frame-Options DENY), proxy `/api → backend:8000`
- `.dockerignore` — node_modules, dist, .git, e2e/results, playwright-report
- e2e 5+ GREEN (CI 환경 가정, 로컬 옵션)
- commit `[P7.10] feat: playwright e2e + multi-stage docker + nginx (5+ e2e GREEN)`

### 7.11 — phase-7-done.md + ADR + architecture 갱신
- `docs/plan/phase-7-done.md` — 단위 + e2e 카운트, 24 endpoint 화면 매핑 표
- `docs/architecture/current.md` 갱신 — Frontend UI 5/5 화면 가동 표시
- `docs/decisions/ADR-013-frontend-implementation-notes.md` — Phase 7 실 구현 중 발생한 결정 (예: TanStack staleTime 차등, SSE 재연결, Verify 셀 편집 키보드 navigation)
- 누적 단위 ~50+ / e2e 5+ / 백엔드 회귀 0
- commit `[P7.11] docs: phase-7-done + architecture/current 갱신 + ADR-013`

## TDD 적용 범위 (TypeScript)

| 영역 | TDD 적용 | 패턴 |
| --- | --- | --- |
| API 클라이언트 | ★ 엄격 | MSW handler 정의 → 실패 테스트 → fetch 래퍼 구현 |
| TanStack hooks | ★ 엄격 | renderHook + waitFor + MSW mock |
| Zustand store | ★ 엄격 | state transition unit test |
| Utility (format/sse) | ★ 엄격 | pure 함수 단위 |
| Component (visual) | △ render-and-verify | render → role/text 검증 + 클릭 핸들러 invoke |
| Page (composite) | △ shallow integration | render + MSW + waitFor |
| e2e (Playwright) | ★ 사용자 흐름 검증 | 5 화면 × 골든 path |

> 시각 회귀(visual regression) 는 Phase 7 범위 외 — Phase 8+ Chromatic/Percy 검토.

## 보안 (CLAUDE.md §보안 - 프런트엔드 적용)

- **XSS 차단**: React JSX 가 디폴트 escape. `dangerouslySetInnerHTML` 금지. 본 phase 에서 한 번도 사용 안 함.
- **API 응답 신뢰**: 백엔드가 `application/json; charset=utf-8` + `X-Content-Type-Options: nosniff` 보장. 클라이언트 추가 sanitize 불필요.
- **인증**: `REQUIRE_AUTH=true` 시 MSAL.js SPA flow + `AuthGate`. Access token 은 메모리만, sessionStorage X (XSS 누출 차단).
- **CSP**: nginx 응답 헤더 `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' https://login.microsoftonline.com`
- **에러 메시지**: 클라이언트가 받은 백엔드 에러는 분류된 `AppError.detail` 만 toast. 스택트레이스 노출 X.
- **PII**: 카드번호는 백엔드가 마스킹 (`****3821`) 전달, 클라이언트는 그대로 표시만. 한글 파일명은 백엔드 metadata 컬럼 → 화면 표시.

## 성능 (CLAUDE.md §성능 - 프런트엔드 적용)

- **Code-split**: React.lazy + Suspense — 5 page 별 chunk (Dashboard/Upload/Verify/Result/Templates).
- **TanStack staleTime**: autocomplete 5분 / transactions 0 (실시간) / templates 1분.
- **SSE**: 1초 폴링 아닌 EventSource push. retry 헤더 = 60000 (백엔드 동일).
- **Image lazy**: 영수증 thumbnail `loading="lazy"`, IntersectionObserver 기반 prefetch.
- **Bundle target**: gzip 후 < 250 KB initial. shadcn/ui 는 tree-shake 친화 (각 컴포넌트 별 import).
- **Lighthouse**: production build 후 LCP < 2.5s, CLS < 0.1, INP < 200ms (Phase 7.10 verification).

## 자율 진행 / 멈춤 조건

자율 진행 (사용자 승인 불필요):
- 각 sub-phase 의 setup / 코드 작성 / 테스트 작성 / commit / push
- 패키지 추가 (npm install)
- ESLint/Prettier 자동 수정
- 합성 MSW handler 데이터 생성

멈춤 (사용자 승인 필요):
- 백엔드 endpoint 시그니처 변경 필요 (Phase 6 stable, 변경 금지가 디폴트)
- 디자인 톤 변경 (ADR-010 기반 — 변경 시 ADR 추가)
- Phase 7 → Phase 8 진입 전
- 빌드 실패 / 테스트 GREEN 못 만들 때

## Phase 7 DoD (Definition of Done)

- [ ] 5 화면 모두 라우팅 + MSW mock 으로 렌더 GREEN
- [ ] 24 endpoint 모두 TanStack hook 으로 wrap (호출 안 하는 endpoint 라도 type 만 정의)
- [ ] SSE EventSource 정상 동작 (Upload 화면에서 8 stage 표시)
- [ ] MSAL.js (REQUIRE_AUTH=true 환경에서 redirect flow 동작 — 단위 mock 으로 검증)
- [ ] vitest 50+ GREEN, ESLint clean, Prettier clean, tsc --noEmit clean
- [ ] Playwright e2e 5 화면 골든 path GREEN
- [ ] Multi-stage Docker 빌드 성공 (이미지 < 50MB) + nginx 헬스체크 GREEN
- [ ] phase-7-done.md + ADR-013 + architecture/current.md 갱신
- [ ] 백엔드 회귀 0 (test 258 + smoke 88.1 % 유지)

## 이정표 commit 시퀀스 (예측)

```
[P7.0] docs: phase-7-plan + ADR-012 frontend stack
[P7.1] feat: ui setup (vite+react+ts+tailwind+shadcn+tanstack+vitest+msw+playwright)
[P7.2] feat: design tokens + shadcn-style component catalog (7+ unit)
[P7.3] feat: api client + tanstack hooks + sse + msal (7+ unit)
[P7.4] feat: app layout + routing + topnav (4+ unit)
[P7.5] feat: Dashboard 화면 (4+ unit GREEN)
[P7.6] feat: Upload 화면 + SSE 진행 (5+ unit GREEN)
[P7.7] feat: Verify 화면 split view + grid + bulk-tag (12+ unit GREEN)
[P7.8] feat: Result 화면 + 다운로드 4 (5+ unit GREEN)
[P7.9] feat: Templates 화면 + 매핑 chips (6+ unit GREEN)
[P7.10] feat: playwright e2e + multi-stage docker + nginx (5+ e2e GREEN)
[P7.11] docs: phase-7-done + architecture/current 갱신 + ADR-013
```

각 commit 은 `Refs: synthesis/05 §Phase 7` 푸터 동반.

---

> Phase 7 진입 — 백엔드 24 endpoint stable, 디자인 톤 ADR-010 명세, 7건 결정 ADR-012 영속. 자율 진행 모드 활성.
