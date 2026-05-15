---
id: ADR-012
title: Frontend stack 7건 결정 + 디자인 토큰
date: 2026-05-15
status: accepted
refs:
  - ADR-010 (UI 예제 분석)
  - docs/plan/phase-7-plan.md
  - ui_reference_1/ (PNG 5장 + JSX/CSS 시각 자료)
---

# 결정

Phase 7 프런트엔드 진입 시 7건 결정 확정. 사용자 답변 + ADR-010 분석 + ui_reference_1/ 자료
검증 결과의 교차.

| # | 항목 | 결정 | 채택 이유 (one-liner) |
| --- | --- | --- | --- |
| 1 | Framework | Vite + React 18 + TypeScript | SPA + FastAPI 분리, nginx 정적 호스팅, MSAL.js SPA flow 자연 |
| 2 | CSS | Tailwind CSS | shadcn/ui 기본, utility-first 매핑 |
| 3 | 컴포넌트 | shadcn/ui (Radix + Tailwind) | ADR-010 명시, a11y + 소스 복사 모델 |
| 4 | 상태 | TanStack Query + Zustand | 서버/클라이언트 상태 분리 |
| 5 | 배포 | Multi-stage Docker (node → nginx:alpine) | ~30MB 이미지, non-root, gzip |
| 6 | JSX 자료 | 참조 + 재작성 | shadcn 구조로 새로 작성, ui_reference_1 은 시각 자료 |
| 7 | 테스트 | Vitest + Playwright + MSW | Vite 네이티브, 다중 브라우저, API mock |

# 컨텍스트

Phase 6 종료 시점 (commit 7570444) 에 백엔드 API 24/24 endpoint 가동. ADR-010 자료 검증
결과 (CreditXLSX 디자인 톤 + 5 화면 + 컴포넌트 카탈로그) 와 ui_reference_1/ 의 PNG 5장 +
React 18 (CDN) JSX 3 파일 + styles2.css (1135 줄) 가 시각 자료로 도착. 디자인 의도는 시각 명확
하지만 source 의 React 18 (CDN inline script) 형태가 TypeScript 프로덕션 코드에 부적합.

# 결정 근거

## 1. Framework — Vite + React 18 + TypeScript

대안 비교:

| 대안 | 평가 | 폐기 사유 |
| --- | --- | --- |
| Next.js App Router | SSR/RSC 가능 | 24 endpoint 가 FastAPI 에 있어 BFF 패턴 중복, MSAL 통합 복잡, 영수증 도메인 SSR 이득 적음 |
| Remix | nested route + loader/action | 학습 곡선 + 한국 생태계 자료 적음 |
| **Vite + React** ★ | SPA, 빠른 dev server, 단순 빌드 | nginx 정적 호스팅 자연, MSAL.js SPA flow 표준, 백엔드와 명확 분리 |

근거:
- 영수증 도메인은 사용자 인증 후 SPA 흐름 (대시보드 → 업로드 → 검수 → 다운로드) — SSR 이득 적음
- 24 endpoint FastAPI 와 분리된 SPA 가 의존 방향 단방향 유지 (`ui → /api`)
- nginx 정적 호스팅 = 운영 비용 최소 (Phase 6 docker-compose 와 자연 결합)

## 2. CSS — Tailwind CSS

대안 비교:

| 대안 | 평가 | 폐기 사유 |
| --- | --- | --- |
| styled-components | 런타임 비용 + SSR 복잡 | CSS-in-JS 트렌드 약화, bundle size |
| CSS Modules | 타입 안전 | shadcn 미호환, 디자인 토큰 시스템 직접 구축 부담 |
| Vanilla CSS | 단순 | scope 관리 + utility 명명 부담 |
| **Tailwind CSS** ★ | shadcn 기본, JIT, 토큰 매핑 자연 | utility-first 가 ADR-010 의 `.btn-ghost/.chip/.purpose-tile` 와 1:1 매핑 |

근거:
- shadcn/ui 가 Tailwind 의존
- `tailwind.config.ts` 에 OKLCH 토큰 노출 → 디자인 시스템 일관성 (예: `bg-brand-soft`, `text-text-3`)
- styles2.css 의 1135 줄 토큰 + 컴포넌트 룰을 Tailwind utility 로 재구성 자연

## 3. 컴포넌트 — shadcn/ui

대안 비교:

| 대안 | 평가 | 폐기 사유 |
| --- | --- | --- |
| Radix UI primitives | a11y headless | 스타일 직접 작성 = shadcn 의 ?? 만 가져가는 셈 |
| Chakra UI | Emotion 기반 | Tailwind 와 충돌, theme 커스터마이즈 부담 |
| Custom from scratch | 자유도 | a11y/포커스 트랩/키보드 네비게이션 직접 구현 비용 큼 |
| **shadcn/ui** ★ | Radix + Tailwind, 소스 복사 모델 | ADR-010 명시, CreditXLSX 톤 커스터마이즈 자유 |

근거:
- ADR-010 §"디자인 톤" 이 명시적으로 "shadcn-style — `.btn-ghost`/`.chip`/`.purpose-tile`/`.suggest-chip`/`.status-pill`" 추천
- 소스 복사 모델 → 향후 디자인 변경이 의존성 업그레이드 강제하지 않음
- a11y + 키보드 네비게이션이 기본 (영수증 검수 화면의 빠른 입력 UX 핵심)

## 4. 상태 — TanStack Query + Zustand

대안 비교:

| 대안 | 평가 | 폐기 사유 |
| --- | --- | --- |
| SWR + Zustand | 단순 | TanStack 보다 SSE/optimistic 기능 빈약 |
| Redux Toolkit (RTK Query) | 보일러플레이트 | 영수증 워크플로 규모 대비 과함 |
| **TanStack Query + Zustand** ★ | 서버/클라이언트 분리 | 24 endpoint 캐싱·optimistic·SSE 보조 + 클라이언트 UI 상태 가벼움 |

근거:
- 서버 상태 (24 endpoint) = TanStack Query — 캐싱, retry, optimistic update, mutation rollback (bulk-tag 409 핸들링)
- 클라이언트 상태 (Verify 선택 row, Upload 진행 단계 표시, 모달 open) = Zustand — Redux 보다 가벼움, Context API 보다 selector 효율적
- staleTime 차등 가능 (autocomplete 5분, transactions 0, templates 1분)

## 5. 배포 — Multi-stage Docker

대안 비교:

| 대안 | 평가 | 폐기 사유 |
| --- | --- | --- |
| Single-stage Node Dockerfile | 빠른 작성 | 이미지 200MB+, `vite preview` 는 dev tool, 운영 부적합 |
| Vercel/Cloudflare Pages | 외부 SaaS | 영수증 PII 특성상 외부 호스팅 컴플라이언스 충돌 |
| **Multi-stage (node build → nginx:alpine)** ★ | ~30MB, non-root | 운영 표준, gzip/health check 자연 |

근거:
- Stage 1: `node:22-alpine` 으로 `npm run build` → dist 산출
- Stage 2: `nginx:alpine` 이 dist + nginx.conf 만 가져가 서빙
- non-root user (UID 1001), SPA fallback (`try_files`), gzip, security headers
- HEALTHCHECK + EXPOSE 8080 (root 권한 불필요한 port)

## 6. JSX 자료 — 참조 + 재작성

대안 비교:

| 대안 | 평가 | 폐기 사유 |
| --- | --- | --- |
| JSX 직접 변환 | 빠름 | React 18 CDN inline script → .tsx 1:1 변환 시 컨벤션/타입/테스트 재작업 다수 발생, shadcn 구조와 불일치 |
| **참조 + 재작성** ★ | 일관성 ↑ | ui_reference_1/ 는 디자인 의도 시각 자료로 수렴, shadcn/ui + TanStack 구조로 새로 작성 |

근거:
- ui_reference_1/components.jsx 의 `TaggingForm`/`Toolbar`/`StatusPill`/`SummaryBar` 는 디자인
  의도가 명확하지만 React 18 (CDN) `Object.assign(window, ...)` 패턴 — 모듈 시스템 부재
- styles2.css 의 토큰/룰은 디자인 시스템으로 흡수 (Tailwind config + globals.css)
- 새 작성으로 TypeScript strict + shadcn/Radix a11y + TanStack hook 일관 구조 확보

## 7. 테스트 — Vitest + Playwright + MSW

대안 비교:

| 대안 | 평가 | 폐기 사유 |
| --- | --- | --- |
| Jest + Cypress | 성숙도 | Vite ESM 설정 복잡, Cypress = Chrome-only 기본 |
| **Vitest + Playwright + MSW** ★ | Vite 네이티브, ESM 자연, 다중 브라우저, MSW API mock | 백엔드 pytest TDD 운영 파터널 |

근거:
- Vitest = Vite 빌드 파이프라인 재사용 → CI 속도 ↑
- Playwright = chromium + webkit + firefox 다중 브라우저, trace viewer 강력, 영수증 이미지 표시 시각 회귀에도 활용 가능
- MSW = 서비스 워커 기반 API mock → 동일 handler 가 단위/통합/e2e 모두 사용 (DRY)

# 디자인 토큰 (OKLCH, styles2.css 기반)

| 토큰 | 값 | 용도 |
| --- | --- | --- |
| `--brand` | `oklch(0.55 0.18 35)` | CreditXLSX orange #c96442 톤, 주요 CTA |
| `--brand-2` | `oklch(0.48 0.16 30)` | hover 진해짐 |
| `--brand-soft` | `oklch(0.97 0.04 35)` | 강조 배경 (chip active, selected row) |
| `--brand-border` | `oklch(0.88 0.06 35)` | brand 색 border |
| `--bg` | `oklch(0.97 0.012 80)` | warm gray bg #f0eee9 톤 |
| `--surface` | `#ffffff` | card/modal/sheet |
| `--surface-2` | `oklch(0.965 0.008 80)` | sub-surface (toolbar, footer) |
| `--border` | `oklch(0.92 0.005 80)` | 기본 border |
| `--border-strong` | `oklch(0.85 0.008 80)` | dropdown/dashed |
| `--text` | `oklch(0.25 0.01 80)` | 본문 |
| `--text-2` | `oklch(0.40 0.01 80)` | 보조 |
| `--text-3` | `oklch(0.55 0.01 80)` | placeholder/meta |
| `--text-4` | `oklch(0.70 0.01 80)` | disabled |
| `--success` | `oklch(0.55 0.15 155)` | 입력완료/high confidence |
| `--success-soft` | `oklch(0.96 0.05 155)` | success 배경 |
| `--conf-high` | `var(--success)` | high 신뢰도 |
| `--conf-medium` | `oklch(0.75 0.16 80)` | medium 신뢰도 (warm yellow) |
| `--conf-low` | `oklch(0.65 0.18 25)` | low 신뢰도 (red orange) |
| `--conf-none` | `oklch(0.65 0.18 25)` | none |

폰트:
- `--sans`: Inter (영문) + Pretendard (한글) — Google Fonts CDN 또는 self-host
- `--mono`: JetBrains Mono — 숫자/금액/카드번호 (font-variant-numeric: tabular-nums)

# 영향 (Phase 7 진입 후)

1. `ui/` 신규 디렉토리 — 백엔드 `app/` 과 독립. import 방향 = ui → /api (단방향).
2. `Dockerfile` + `nginx.conf` 신규 — Phase 6 docker-compose 에 ui 서비스 추가 필요 (Phase 7.10).
3. `package.json` 의존성 추가 — Node 22 LTS, npm/pnpm 기본. CI 의 Phase 6 까지 의존성과 무관.
4. TDD 패턴 — TypeScript 단위 (vitest + MSW) + Playwright e2e — 백엔드 pytest 와 분리 실행.
5. ESLint + Prettier 적용 — Python ruff 와 무관. tsc --noEmit 추가.

# 후속

- ADR-013 (Phase 7 실 구현 중 결정) — staleTime 차등, SSE 재연결 정책, Verify 키보드 네비게이션 등
- Templates editor 의 풀 셀 편집은 Phase 8+ deferred (ADR-010 §D-A-3 후보 B 채택: read-only + 매핑 chips PATCH 만 Phase 7)
- 메일 발송은 Phase 7+ (별도 트랙)
