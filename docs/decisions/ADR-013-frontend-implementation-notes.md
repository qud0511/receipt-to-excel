---
id: ADR-013
title: Phase 7 Frontend 구현 중 결정 정리
date: 2026-05-15
status: accepted
refs:
  - ADR-010 (UI 예제 분석)
  - ADR-012 (Frontend stack + 디자인 토큰)
  - docs/plan/phase-7-done.md
---

# 결정

Phase 7 (Frontend UI) 본 구현 중 발생한 ADR-010/012 외 결정·트레이드오프 14건 정리.
ADR-012 가 7건 stack 결정이라면 본 ADR 은 그 위에서 구체 구현 패턴 명세.

# 결정 사항

## 1. CellInput Enter commit / Escape rollback / Blur diff-only

Verify 그리드의 셀 인라인 편집 (`VerifyGrid.CellInput`) 패턴:
- 로컬 state `v` 와 prop `value` 분리 → 사용자 입력 중에는 v 만 변경
- **Enter**: blur 발생 → 부모 onCommit
- **Escape**: `v = value` 복원 후 blur
- **Blur**: `v !== value` 일 때만 onCommit (diff-only) → 불필요한 PATCH 차단
- prop value 변경 시 v 동기화 (useEffect)

근거: 옵티미스틱 업데이트가 부모 row 객체를 변경하면 그 row 의 다른 필드 PATCH 직후에도 같은 셀이 즉시 다시 invalidate 호출되는 루프 방지.

## 2. TanStack optimistic patch + 전체 rollback

`usePatchTransaction` (sessions/{id}/transactions/{tx_id}):
- onMutate: 모든 `["sessions", id, "transactions", *]` query 의 snapshot 백업 + 즉시 row 갱신
- onError: snapshot 전체 복원
- onSettled: invalidateQueries — 서버 진실로 재동기화

`useBulkTag` 는 옵티미스틱 X — 백엔드 ADR-010 §D-1 "전체 롤백 trans" 보장하므로 invalidate 만.

## 3. useMemo 의존성: rows = `list.data?.transactions ?? []`

빈 fallback `[]` 는 매 렌더마다 새 array 라 dependent useMemo 가 매번 재계산. 해결:
```ts
const rows = useMemo(() => list.data?.transactions ?? [], [list.data]);
```
ESLint `react-hooks/exhaustive-deps` 가 catch. 같은 패턴이 Phase 8+ 다른 화면에서도 재발 가능 — list 기반 hook 응답 가공 시 `useMemo([data])` 일관.

## 4. SSE 자동 close on done/error

`subscribeSession(sessionId, { onEvent })` 가 EventSource 의 `done` 또는 `error` stage 수신 시 자동 `es.close()`. 호출자는 cleanup 함수만 보관 (useEffect unmount). 재연결 retry 는 EventSource 기본 동작 + 백엔드 `retry: 60000` 헤더.

## 5. Verify 화면 셀 autocomplete 는 free-text input (Phase 8 보류)

Plan 7.7 의 "autocomplete dropdown" 은 셀별 popover (`useVendors` 응답 list) 명시했으나 본 phase 에서는 free-text input 으로 단순화. `lib/api/autocomplete.ts` 와 `useVendors` hook 은 작성 완료 — Phase 8 에서 셀 popover UI 만 추가하면 됨.

근거: row inline editing + popover 가 키보드 트랩/포커스 관리가 복잡, 단위 테스트 비용도 큼. Free-text + 추후 autocomplete 가 점진적 향상.

## 6. Result 화면 generate 자동 호출

`ResultPage` 진입 시 useEffect 로 `useGenerate.mutate()` 자동 호출. 백엔드가 idempotent 응답 (이미 생성된 artifact 면 재사용) 가정. Phase 8+ 백엔드가 status 체크 후 conditional regenerate 정밀화 가능.

## 7. dev MSW worker 미적용

옵션이지만 본 phase 범위 외. `npx msw init public` 으로 `mockServiceWorker.js` 는 이미 commit (Phase 7.1) — `main.tsx` 에서 `VITE_USE_MOCK=true` 시 worker.start() 추가만 하면 됨. Phase 8 후보.

## 8. e2e 로컬 실행: libnspr4 시스템 deps 부재

Playwright headless chromium 이 `libnspr4`/`libnss3` 요구. 본 환경 (sudo 없는 dev 컨테이너) 에서 미설치 → e2e spec 작성·typecheck·lint 만 통과, 실행 GREEN 검증 보류.

해결: `sudo npx playwright install-deps chromium` 후 `npm run e2e`. CI 환경 (Playwright 공식 Docker image) 에서는 자동 동작.

## 9. nginx /api/ proxy 의 SSE 무버퍼링

`proxy_buffering off` + `proxy_cache off` + `proxy_read_timeout 3600s` + `chunked_transfer_encoding off`. SSE 1 초 폴링 응답이 nginx 버퍼에 묶이지 않도록 강제. 백엔드도 `X-Accel-Buffering: no` 헤더 발급 (Phase 6).

## 10. Multi-stage Docker port 8080 (non-root nginx)

nginx alpine 기본은 :80 (root 필요). `sed -i 's/listen 80/listen 8080/'` + `USER nginx` (UID 101) 로 non-root. docker-compose 등에서 publish 시 `8080:8080` 매핑.

## 11. Content-Security-Policy 명시

nginx.conf 에서 `script-src 'self'` + `style-src 'self' 'unsafe-inline'` + `connect-src 'self' https://login.microsoftonline.com` + `frame-ancestors 'none'`. MSAL 의 popup 사용 안 함 (redirect flow) → frame-ancestors none 가능.

`'unsafe-inline'` style 은 Tailwind utility 동적 클래스 + Google Fonts CSS import 때문에 불가피. nonce-based 는 Phase 8+ 검토.

## 12. Templates 화면 셀 read-only 채택 (ADR-010 §D-A-3 후보 B)

UI 자료 검증에서 발견된 풀 Excel-like 편집 (formula bar + 셀 더블클릭 + border/병합/줌) 은 본 phase 범위 외. **read-only grid + 매핑 chips PATCH** 만 구현. 양식 자체 수정은 사용자가 raw download 후 외부 Excel 에서 편집 → 재업로드.

## 13. StatusPill — Transaction tagged vs Session.status 한 컴포넌트

`<StatusPill tagged>` (Transaction 검수 완료) 와 `<StatusPill sessionStatus>` (Session 4 enum 한↔영 매핑) 가 한 컴포넌트. props 중 하나만 제공해도 동작. 색 톤 + 라벨 매핑 표는 컴포넌트 내부 record.

## 14. SummaryBar D-N today 인자 주입

`<SummaryBar dueDate today={...}>` — today 가 optional, 미주입 시 `new Date()`. 테스트는 `freezegun` 패턴 (today 명시 주입) 사용 → flaky 차단. CLAUDE.md §"Flaky 방지" 준수.

# 후속

- Phase 8 후보:
  - 셀별 autocomplete dropdown (vendor/project) — useVendors/useProjects 활용
  - 참석자 team_group hybrid modal (자유 텍스트 + 팀 chip)
  - dev MSW worker (백엔드 없이 UI 풀 사용)
  - Templates 셀 직접 편집 + formula bar
  - 시각 회귀 (Chromatic / Percy)
  - Lighthouse production metric
  - 메일 발송 (외부 SMTP/Graph API)
