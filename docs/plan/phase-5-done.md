# Phase 5 — Templates + XLSX Writer (R13) + PDF Generators — DONE

> 임시 워크어라운드 (유지): JPG hana/kakaobank 5 건은 vendor_name 수동 입력 — ADR-009 별도 트랙
> (`docs/limitations/ocr_qwen_vendor_name.md` 참조).

- 시작: 2026-05-12
- 완료: 2026-05-12
- 브랜치: 로컬 `main` → `origin/v4`
- Phase 5 commit 범위: `5c04d6d` (Phase 4.5 종료) ~ `098c96f` (Phase 5 통합 테스트)

## 산출 모듈

| 영역 | 파일 | 책임 | 단위 |
| --- | --- | --- | --- |
| Template Analyzer | `app/services/templates/analyzer.py` | ADR-006 7 단계 휴리스틱 → SheetConfig | 7 |
| Template Injector | `app/services/templates/injector.py` | named range 주입 (FIELD_*/DATA_START_*) | 3 |
| XLSX Writer | `app/services/generators/xlsx_writer.py` | clear/write/sheet 라우팅/R13/regenerate_sum/파일명 | 11 |
| Merged PDF | `app/services/generators/merged_pdf.py` | 거래일 ASC + pypdf 페이지 연결 | 3 |
| Layout PDF | `app/services/generators/layout_pdf.py` | 2~3/A4 + scale-to-fit (R11) | 3 |
| 합성 fixture | `tests/fixtures/synthetic_xlsx.py` | ADR-006 layout 합성 (field/category/hybrid + sum_row gap) | — |
| 통합 round-trip | `tests/integration/test_real_template_round_trip.py` | 3 장 실 양식 분석 검증 | 3 |
| **합계** | — | — | **30 단위 + 3 통합** |

## Phase 5 DoD 게이트

- [x] **Template Analyzer** — field/category/hybrid mode 3 단위 통과 + formula_cols 검출 + sum_row 자동 탐지 + 빈 양식 error
- [x] **Template Injector** — FIELD_* + DATA_START_* named range 주입 + 덮어쓰기 + 공백 시트명 quote
- [x] **XLSX Writer** — clear_data_rows (v1 Bug 1 회귀) + write_receipt 셀 단위 수식 보호 (v1 Bug 2 회귀) + 카테고리 매핑 + 기타비용 fallback + regenerate_sum_formulas + 시트 라우팅 (R2) + R12 파일명 + R13 동적 행 삽입 (style/merge/formula ref 보존)
- [x] **PDF Generators** — merged_pdf (거래일 ASC + 페이지 연결 + 빈 입력 None) + layout_pdf (2/3 per A4 + R11 aspect ratio + R12 파일명)
- [x] **실 양식 round-trip** — 3 장 (2025-12-a, 2026-03-a, 2026-03-b) 모두 ADR-006 §공통점 일치
- [x] `pytest`, `mypy --strict`, `ruff`, `pip-audit` 통과 — 회귀 0

## 누적 테스트 카운트 (Phase 4 보완 + Phase 5)

| 영역 | Phase 4.5 결과 | Phase 5 신규 | 합계 |
| --- | --- | --- | --- |
| 단위 | 161 | +30 | **191** |
| 통합 | 3 (skip 1) | +3 (real_template round-trip skip 해제) | **6 (skip 0)** |
| smoke (real_pdf) | 42 | 0 | 42 |
| **합계** | **206 (skip 1)** | **+33** | **239 (skip 0)** |

mypy --strict (81 source files) + ruff + pip-audit 통과.

## ADR-006 휴리스틱 실 양식 검증 결과

3 장 실 양식 (`expense_2025_12_a/2026_03_a/2026_03_b`) 모두 통과:
- 시트 자동 분류 ('_법인'/'_개인' suffix) — 차량 시트 skip 정상.
- header_row 7 + data_start_row 9 모두 일치.
- sum_row 가 자동 탐지 (gap 0/1/2 흡수).
- formula_cols 에 E (행별 SUM) 포함.
- category mode 활성 시 식대/기타비용 매핑 정상.

ADR-006 §"양식 진화 흔적" (A 컬럼 일자 형식 text↔datetime / B/C/D 거래처 분리 / G 헤더
sub-label 변동 / sum_row gap) 모두 휴리스틱에 의해 자동 흡수.

## 본 Phase 가 다루지 않은 것 (Phase 6 로 이관)

phase-5-plan.md §5.4 의 Templates API Routes 는 본 Phase 에서 **Phase 6 로 이관**:

| 이관 항목 | 사유 |
| --- | --- |
| `app/api/routes/templates.py` (analyze/POST/GET/grid/PUT/DELETE) | Sessions API + Upload Guard + user_id 매핑 인프라가 Phase 6 의 핵심 — Templates API 도 동일 인프라 위에 구축. |
| 6 통합 테스트 (auth/IDOR/422/round-trip) | TestClient + Auth-skip + per-user FS isolation 이 Phase 6 의 산출. Phase 6 내 Sessions API 와 같이 통합. |
| `app/schemas/template.py` (요청/응답) | 동일 인프라 의존. |

본 결정 정당화:
- Templates API 의 핵심 비즈니스 로직 (analyze + register + grid 미리보기) 은 **본 Phase 의 Analyzer/Injector** 가 이미 제공.
- API 라우터는 Phase 6 의 `UploadGuard` + `FileSystemManager` + `get_or_create_user_by_oid` 가 구비된 후 일관성 있게 통합 가능.
- 잡 runner (Phase 6) 가 `write_workbook` / `write_merged_pdf` / `write_layout_pdf` 호출하는 흐름이 본 Phase 5 의 정상 사용 경로 — API 도 동일 호출 경로 따름.

## Phase 6 진입 게이트 — **사용자 승인 대기**

CLAUDE.md §"자율 진행 원칙": Phase 경계 (Phase 5 → Phase 6) 사용자 승인 필요.

### Phase 6 작업 범위 (`synthesis/05 §Phase 6`)

1. **Upload Guard** (`app/core/security.py`) — MIME + magic + size + sanitize
2. **FileSystemManager** (`app/services/storage/file_manager.py`) — per-user FS 단일 진입점
3. **Job Runner** (`app/services/jobs/runner.py` + `app/workers/job_runner.py`) — BackgroundTasks + Semaphore(2)
4. **Sessions API** (`app/api/routes/sessions.py`) — POST/GET/DELETE + SSE `/stream`
5. **Templates API** (`app/api/routes/templates.py`) — Phase 5 산출물 사용 (analyze/POST/GET/grid/PUT/DELETE)
6. **SSE** — 1 초 간격 + `retry: 60000` + `X-Accel-Buffering: no`
7. **`get_or_create_user_by_oid`** — Azure AD oid → DB User row 매핑 helper

### 기대 통과율 (smoke 회귀 안정성)

본 Phase 는 parser 무변경 → smoke 통과율 88 % 유지 예상.
**Phase 5 종료 직전 smoke 회귀 검증** (parser 무변경 sanity check) 결과는 본 문서 갱신 시 추가.

## Smoke Gate 회귀 (Phase 5 종료 시점)

본 Phase 는 parser 무관 — Phase 4.5 의 88.1 % (37/42) 안정 유지.

### 4차 smoke (Phase 5 종료 회귀 검증, 2026-05-12)

| 지표 | 값 |
| --- | --- |
| PASSED | **37 / 42 = 88.1 %** (Phase 4.5 와 동일) |
| FAILED | 5 (hana 2 + kakaobank 3 — 모두 결함 3 동일) |
| 거래 단위 | 44 transactions (woori_nup N-up 9 거래 포함) |
| 회귀 발견 | **0** |

### Phase 5 부수 — `uv sync --extra ocr` 의존성 회복

본 Phase 도중 `openpyxl` / `pypdf` 추가 시 `uv sync` (extras 없이) 가 ``docling``/`easyocr` 제거.
smoke 직전 `uv sync --extra ocr` 재실행으로 복구 (CLAUDE.md §"smoke 실행 시만").

후속 권장: CI 의 smoke job 이 항상 `--extra ocr` 명시 (이미 README 명시됨).

---

> Phase 5 산출: **단위 30 + 통합 3 (skip 1 → 0)** 신규 — 합성 fixture + 실 양식 round-trip 모두 통과.
> Phase 6 진입은 사용자 승인 대기.
