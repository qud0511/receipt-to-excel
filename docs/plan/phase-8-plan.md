# Phase 8 — UX 깊이 + 운영 인프라

> 진입 게이트: Phase 7 (Frontend UI) 완료 (commit e34d0ff + fix 7fbe703).
> 시작: 2026-05-15
> 참조: ADR-013 §"후속", phase-7-done.md §"미진행 / Phase 8+ 후속"

## 의도

Phase 7 은 **5 화면 골격 + 24 endpoint 통합** 까지. Phase 8 은 그 위에서 사용자
편의 깊이 + 운영 인프라 보강. 한 sub-phase = 한 user-visible 향상 단위.

## Sub-phase 후보 (우선순위순)

### 8.1 — Verify 셀 autocomplete dropdown (선택됨)

- vendor / project free-text 입력을 popover dropdown 으로 교체
- 입력 1자 이상 시 useVendors / useProjects 호출 → 응답 list 제안
- '최근' 뱃지 (vendor.last_used_at desc 상위 N건)
- 키보드 navigation (↑↓ 선택, Enter commit, Escape close)
- 신규: `useProjects` hook (vendor_id 의존 enabled)
- 신규: `components/Autocomplete.tsx` (vendor/project 공용 — Radix Popover + Command pattern 또는 직접 구현)
- VerifyGrid 의 vendor/project 셀 교체

테스트: 5+ unit (typing trigger / dropdown 표시 / 클릭 select / recent badge / vendor 변경 시 project reset)

### 8.2 — 참석자 team_group hybrid modal

- TaggingForm 의 참석자 입력 = 자유 텍스트 chip + 팀 그룹 선택 modal (useTeamGroups 활용)
- 멤버 grid (선택/해제) + 팀 전체 선택 + 일괄 적용
- 신규: `features/verify/AttendeesModal.tsx` + `attendees-store.ts`

### 8.3 — dev MSW worker

- `VITE_USE_MOCK=true` 시 `main.tsx` 에서 worker.start() 후 render
- 백엔드 없이 mock 데이터로 UI 풀 사용 → 데모/설명/시각 프레젠 유용
- e2e mock 과 핸들러 통일 (`test/handlers.ts` 또는 `mocks/browser.ts`)

### 8.4 — Templates 셀 편집 (formula bar + 셀 PATCH)

- ADR-010 §"Templates editor" 풀 구현 후보 — Phase 7 read-only 에서 확장
- 셀 더블클릭 → formula bar + inline input → PATCH /templates/{id}/cells
- 신규: `features/templates/FormulaBar.tsx`, `useCellEditor` (selection + range)
- style/border/병합/줌 은 별도 sub-phase (8.5)

### 8.5 — Templates 풀 편집 (border/병합/줌/status bar)

- Excel-like toolbar (굵게/기울임/정렬/병합/배경)
- 줌 + status bar (행 12 | 합계 ... | 평균 ... | 개수 6)
- ADR-010 §B-7 풀 매핑 — UI 강한 요구

### 8.6 — 메일 발송 ("팀장님께 메일로 보내기")

- 외부 SMTP 또는 Microsoft Graph API
- 백엔드 신규 endpoint: POST /sessions/{id}/send-mail (recipient, subject, body, attachments)
- ADR-009 별도 트랙과 분리 검토
- ResultPage 의 disabled 메일 button 활성화

### 8.7 — Baseline 사용자별 누적 평균

- 현재 baseline 15분/거래 하드코드 (`get_session_stats`)
- history 누적 → User.baseline_s_per_tx 갱신 (지수 이동 평균 또는 단순 평균)
- Dashboard "절약된 시간" 더 정확

### 8.8 — PDF 생성 오류 조사 (검증 라운드 발견)

- 합성 PDF fixture 입력 시 layout_pdf/merged_pdf 422
- 운영 실 영수증 JPG/PNG 입력에서는 정상 동작 가능성
- ZIP 에는 PDF 포함되지 않으므로 정확한 원인 + fix 또는 명시적 입력 형식 제약

### 8.9 — 시각 회귀 (Chromatic / Percy)

- 5 화면 + 공통 컴포넌트 시각 snapshot
- design token 변경 시 회귀 감지

### 8.10 — Lighthouse / Bundle 분석

- production build metric (LCP / CLS / INP / bundle size)
- 필요 시 code-split 추가

### 8.11 — docker-compose (UI + backend 통합)

- `docker-compose.yml`: ui (nginx:8080) + backend (uvicorn:8000) + ollama (선택)
- 운영 배포 단일 명령
- 환경 변수 합치기 (REQUIRE_AUTH, DATABASE_URL, AAD_* 등)

### 8.12 — CI 자동화 (GitHub Actions)

- pytest + vitest + playwright + ruff + mypy + import-linter
- multi-stage docker build 검증
- pip-audit 차단 gate

## 진행 원칙

- 한 sub-phase = 1 user-visible 향상 + commit + push
- 8.1 부터 순차 진행 (단, 사용자 결정으로 우선순위 변경 가능)
- Phase 8 끝 = phase-8-done.md + ADR-014 (실 구현 결정) + architecture/current.md 갱신
