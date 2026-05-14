# Architecture Docs — planned vs current

본 디렉토리는 v4 의 전체 계획 (`planned.md`) 과 현재 구현 (`current.md`) 비교 문서.

## 파일

| 파일 | 내용 | 시점 |
| --- | --- | --- |
| [planned.md](planned.md) | Phase 1~7 완료 시점의 최종 아키텍처 | 미래 (전체) |
| [current.md](current.md) | Phase 6.7 완료 시점의 실제 동작 | 2026-05-12 (현재) |

## Mermaid 다이어그램 — 렌더 환경

본 문서들의 시각화는 모두 [Mermaid](https://mermaid.js.org/) 코드 블록으로 작성. 다음 환경에서 자동 렌더:

- **GitHub**: 원격 push 후 web 에서 자동 렌더 (✓)
- **VSCode**: "Markdown Preview Mermaid Support" extension 설치 후 preview 시 (✓)
- **GitLab / Bitbucket**: 동일 자동 렌더
- **로컬 CLI**: `npx -p @mermaid-js/mermaid-cli mmdc -i input.md -o output.svg`

PNG/SVG 정적 이미지 필요 시 (추가 의존성):

```bash
# Option A — Node.js 의 mermaid-cli (단발 사용)
npx -p @mermaid-js/mermaid-cli mmdc \
  -i /bj-dev/v4/docs/architecture/planned.md \
  -o /bj-dev/v4/docs/architecture/planned.svg

# Option B — Python graphviz (구조 다이어그램만 — Mermaid 미지원)
uv add graphviz
sudo apt install graphviz   # 시스템 의존성
```

## 다이어그램 종류 (Mermaid)

| 종류 | 사용처 |
| --- | --- |
| `flowchart` | 시스템 컴포넌트 (Backend / Parser / Generator / Storage) |
| `sequenceDiagram` | 사용자 흐름 (Dashboard → Upload → Verify → Result) |
| `erDiagram` | DB 스키마 (12 tables) |
| `stateDiagram-v2` | Session.status 상태 전이 |
| `gitGraph` | commit 흐름 (Phase 5 → 6.7) |

## ASCII 보조

각 화면 mockup 은 ASCII art (`planned.md` §6). UI 가 미구현 (Phase 7 대기) 인 현재 상태에서 ADR-010 자료 검증 결과를 시각화.

## 비교 빠른 표

| 영역 | 계획 (planned.md) | 현재 (current.md) | 진척 |
| --- | --- | --- | --- |
| 백엔드 인프라 | UploadGuard / FS / JobRunner / SSE | 동일 | 100% |
| 영수증 파서 | 7 rule_based + OCR + LLM | 동일 + Smoke 88.1% | 100% |
| 카드 사용내역 파서 | 다중 카드사 | shinhan MVP | ~30% |
| Transaction Matcher | ±5분/금액 | 동일 | 100% |
| Templates Analyzer | ADR-006/011 휴리스틱 | 동일 | 100% |
| XLSX Writer R13 | v1 Bug 1·2 차단 | 동일 | 100% |
| Sessions API | 10 endpoint | **10 endpoint** | 100% |
| Templates API | 9 endpoint | 0 endpoint | 0% |
| Dashboard summary | 1 endpoint | 0 endpoint | 0% |
| 자동완성 | 4 endpoint | 0 endpoint | 0% |
| Frontend UI | 5 화면 (CreditXLSX) | 0 화면 | 0% |
| 메일 발송 | Phase 7+ | 미구현 | (deferred) |

전체 진척: 백엔드 **~65%**, UI **0%**.

## Phase 매핑

| Phase | 영역 | 상태 |
| --- | --- | --- |
| 1 | Bootstrap + Auth | done |
| 2 | DB Repositories + alembic 0001 | done |
| 3 | Confidence + Domain | done |
| 4 | Parsers + Resolvers | done |
| 4.5 | Smoke Gate (88.1%) | done |
| 5 | Templates Analyzer + Generators | done |
| 6.1 | UploadGuard + FileSystemManager | done |
| 6.2 | alembic 0002 (status/columns/GeneratedArtifact) | done |
| 6.3 | Card Statement Parser (shinhan MVP) | done |
| 6.4 | Transaction Matcher | done |
| 6.5 | Template Analyzer ADR-011 | done |
| 6.6 | JobRunner + JobEventBus | done |
| 6.7 | Sessions API (10/10) | **done — 현재 시점** |
| 6.8 | Templates API (9/9) | 다음 |
| 6.9 | 자동완성 + Dashboard | |
| 6.10 | e2e 통합 + 검증 | |
| 6.11 | smoke 회귀 | |
| 7 | Frontend React UI | |
| 8+ | Excel-like 편집 + 메일 + 누적 baseline | |

## ADR 매핑

| ADR | 영향 영역 | planned.md | current.md |
| --- | --- | --- | --- |
| 001~005 | Phase 1~4 기반 | ✓ | ✓ |
| 006 | 양식 분석 휴리스틱 | ✓ | ✓ (ADR-011 로 확장) |
| 007 | text-aware provider | ✓ | ✓ |
| 008 | rule_based regex 보강 | ✓ | ✓ (Smoke 88%) |
| 009 (예약) | OCR LLM 가맹점명 빈 응답 해소 | Phase 7 트랙 | limitations doc |
| 010 | UI 예제 분석 + 추천 7건 | ✓ | ✓ (7건 모두 반영) |
| 011 | Analyzer suffix-free | ✓ | ✓ |

---

## 보는 순서 추천

1. **`current.md` §1 한 줄 요약** — 진척 한 줄 파악
2. **`current.md` §2 컴포넌트** — 가동 중 / 미구현 시각
3. **`planned.md` §6 UI mockup** — 최종 사용자 흐름 시각
4. **`current.md` §7 curl 검증 가능 흐름** — 직접 시도
5. **`planned.md` §11 ADR 매핑** — 결정 근거 추적
