# CreditXLSX UI

Phase 7 frontend — Vite + React 18 + TypeScript + Tailwind + shadcn/ui + TanStack Query + Zustand.

## 개발

```bash
cd /bj-dev/v4/ui
npm install
npm run dev      # http://localhost:5173 (Vite proxy → backend localhost:8000)
```

## 스크립트

| 명령 | 용도 |
| --- | --- |
| `npm run dev` | Vite dev server (HMR) |
| `npm run build` | tsc --noEmit + vite build → dist/ |
| `npm run preview` | dist/ 정적 서빙 (port 4173) |
| `npm test` | Vitest run (단위 + MSW mock) |
| `npm run test:watch` | Vitest watch mode |
| `npm run e2e` | Playwright e2e (build → preview → spec) |
| `npm run lint` | ESLint (max-warnings 0) |
| `npm run format` | Prettier write |
| `npm run typecheck` | tsc --noEmit |

## 환경 변수

`.env.example` 참조. dev 는 `VITE_REQUIRE_AUTH=false`, prod 는 `true` + MSAL claims 설정.

## 디렉토리

`docs/plan/phase-7-plan.md` §"디렉토리 구조" 참조.
