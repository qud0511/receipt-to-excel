# Phase 6 — Sessions + Templates API + Upload + Jobs + SSE + 카드 사용내역 파서

> 임시 워크어라운드 (유지): JPG hana/kakaobank 5 건은 vendor_name 수동 입력 — ADR-009 별도 트랙
> (`docs/limitations/ocr_qwen_vendor_name.md`).

- 시작 예정: 2026-05-12
- 의존: Phase 5 (Templates Analyzer/Injector + XlsxWriter R13 + PDF Generators), Phase 2 (Repositories), Phase 1 (Auth)
- 참조: synthesis/05 Phase 6 원본, ADR-010 (UI 자료 검증), ADR-011 (시트 분석 휴리스틱 확장)
- 본 plan 은 ADR-010 자료 검증 + 사용자 추천 7 건 동의 + synthesis/05 원본 통합

## 목표

영수증 + 카드 사용내역 업로드 → 잡 파싱 → SSE 진행 표시 → 검수 (PATCH/bulk-tag) → 생성 (XLSX + layout PDF + ZIP) → 다운로드 까지 e2e 작동. UI 5 화면 (Dashboard / Upload / Verify / Result / Templates) 의 백엔드 요구 endpoint 11+ 모두 구현.

## 사용자 추천 7 건 (ADR-010 동의)

| 번호 | 결정 | Phase 6 반영 |
| --- | --- | --- |
| 1 | 다운로드 파일 = layout PDF + XLSX 2종, ZIP 별도 action (raw merged 미노출) | `generate_session_artifacts()` 가 2 파일 + ZIP 묶음 1 파일 = 총 3 GeneratedArtifact 영속. `merged_pdf` 는 layout 내부 단계로 흡수 (Phase 5 의 `write_merged_pdf` 는 layout 입력 전 단계로 호출). |
| 2 | 카드 사용내역 XLSX/CSV 파서 — Phase 6 포함 | `app/services/parsers/card_statement/{xlsx_parser,csv_parser}.py` 신규. provider 감지 + rule_based 정규식 패턴 (Phase 4 영수증 parser 와 동일 계약 = `list[ParsedTransaction]`). 영수증 사진과 매칭 (거래 시각 + 금액) |
| 3 | Templates 셀 편집 — 셀 값 PATCH + 매핑 chips PATCH 만 (Phase 6). style/병합/줌/formula bar deferred to Phase 8+ | `PATCH /templates/{id}/cells` 가 (sheet, row, col, value) tuple list 받음. style 변경은 무시. |
| 4 | 시트 분석 휴리스틱 확장 — ADR-011 작성 + suffix 가정 제거 | ADR-011 의 새 휴리스틱 적용 + `Template.mapping_status` 컬럼 + `SheetConfig.analyzable` 신규 |
| 5 | Baseline 평소 처리 시간 — 하드코드 15분/거래 (Phase 6), Phase 8+ 에서 사용자별 누적 평균 진화 | `app/core/metrics.py` 에 `BASELINE_MIN_PER_TRANSACTION = 15` 상수 + Session.processing_time_s 비교 |
| 6 | 참석자 입력 hybrid — autocomplete + team_group chip | 백엔드 API 는 `attendees: list[str]` 단일 형태. UI 는 hybrid input 으로 같은 list 채움. team_group endpoint 1 개 추가 |
| 7 | 영수증 파일명 uuid 디스크 + 원본명 metadata | CLAUDE.md 보안 규정 그대로. `UploadGuard` 가 `uuid4().hex+suffix` 디스크명 생성 + `Transaction.original_filename` 컬럼 metadata 보존 |

## 작업 범위 — 총 23 항목

### 카테고리 1: 인프라 (synthesis/05 Phase 6 원본 + 보안)

1. **`UploadGuard`** (`app/core/security.py`) — MIME + magic bytes + size + sanitize. CLAUDE.md "업로드 3중 검증" 강제.
2. **`FileSystemManager.from_config(...).session_upload(...)`** (`app/services/storage/file_manager.py`) — per-user FS 단일 진입점. 한국어 원본명은 metadata, 디스크는 uuid.hex+suffix.
3. **`JobRunner`** (`app/services/jobs/runner.py` + `app/workers/job_runner.py`) — BackgroundTasks + Semaphore(2) (Ollama). 영수증 + 카드 사용내역 동시 잡 큐.
4. **`get_or_create_user_by_oid`** (`app/db/repositories/user_repo.py` 확장) — Azure AD oid → DB User row 매핑 helper.
5. **`Session.status`** enum 마이그레이션 — `parsing` / `awaiting_user` / `submitted` (ADR-010 D-3).
6. **`Session.processing_started_at` / `processing_completed_at`** 컬럼 — Result 처리 시간 메트릭 (ADR-010 B-8).
7. **`Transaction.original_filename` / `receipt_file_path`** 컬럼 — uuid 디스크 + 원본명 metadata + Verify 좌 panel 영수증 표시 (ADR-010 H, 추천 7).
8. **`GeneratedArtifact`** 신규 테이블 (id, session_id FK, artifact_type enum: xlsx/pdf/zip, fs_path, created_at) — ADR-010 D-4.
9. **`Template.mapping_status`** 컬럼 — mapped / needs_mapping (ADR-011).
10. **`SheetConfig.analyzable: bool = True`** — ADR-011.

### 카테고리 2: Sessions API

11. **`POST /sessions`** — multipart (receipts[], card_statements[], template_id). 사용자 oid → user_id 매핑 → 잡 큐.
12. **`GET /sessions/{id}/stream`** (SSE) — 1 초 간격 + `retry: 60000` + `X-Accel-Buffering: no`. 8 stage enum (uploaded / ocr / llm / rule_based / resolved / vendor_failed / done / error).
13. **`GET /sessions/{id}/transactions?status={all|missing|review|complete}`** — Verify 그리드 + Filter chips 백엔드 (ADR-010 B-9).
14. **`PATCH /sessions/{id}/transactions/{tx_id}`** — 사용자 수정 (vendor/project/purpose/headcount/attendees/note). last-write-wins (ADR-010 D-2, 추천 동의).
15. **`POST /sessions/{id}/transactions/bulk-tag`** — 다중 row 일괄 적용. **transactional rollback** (ADR-010 D-1) — 한 row 실패 시 전체 rollback + 409 + failed_tx_ids[].
16. **`GET /sessions/{id}/transactions/{tx_id}/receipt`** — Transaction.receipt_file_path → FileResponse (per-user FS 차단 IDOR).
17. **`GET /sessions/{id}/preview-xlsx`** — Phase 5 XlsxWriter 결과의 cell grid JSON.
18. **`POST /sessions/{id}/generate`** — Phase 5 generators 호출 + GeneratedArtifact 3 row 영속.
19. **`GET /sessions/{id}/download/{kind}`** — kind ∈ xlsx / pdf / zip. Content-Disposition 한글 파일명 (RFC 5987 인코딩).
20. **`GET /sessions/{id}/stats`** — Session.processing_*_at 차이 + baseline 15 분 × 거래 수 비교.

### 카테고리 3: Templates API (Phase 5.4 deferred 항목 포함)

21. **`GET /templates`** — Phase 2 template_repo.list_for_user 활용.
22. **`POST /templates/analyze`** — 업로드 .xlsx → AnalyzedTemplate (영속 X).
23. **`POST /templates`** — 등록 (TemplateConfig + Template.mapping_status 영속).
24. **`GET /templates/{id}/grid`** — 셀 값 + 좌표 JSON (Templates editor 기본).
25. **`PATCH /templates/{id}/cells`** — 셀 값 다중 수정 (style/병합 deferred).
26. **`PATCH /templates/{id}/mapping`** — 매핑 chips 단위 column_map override.
27. **`PATCH /templates/{id}`** — 메타 (name / tags).
28. **`DELETE /templates/{id}`** — IDOR 차단.
29. **`GET /templates/{id}/raw`** — 원본 xlsx 다운로드.

### 카테고리 4: 자동완성 + Dashboard + 카드 사용내역 파서

30. **`GET /vendors?q={q}&limit=8`** — Phase 4 vendor_matcher 활용 + Cache-Control: max-age=300 (ADR-010 D-5).
31. **`GET /projects?vendor_id={id}&limit=8`** — 동일 캐시 정책.
32. **`GET /attendees?q={q}`** + **`GET /team-groups`** — hybrid 입력 (추천 6).
33. **`GET /dashboard/summary`** — 이번 달 metric + 최근 결의서 N 개 (ADR-010 의 4 KPI + recent list).
34. **`app/services/parsers/card_statement/{xlsx_parser,csv_parser}.py`** — 신규 파서, provider 감지 (`shinhan_xlsx`/`samsung_xlsx`/...). list[ParsedTransaction] 반환.
35. **`Transaction ↔ ParsedTransaction (영수증) ↔ ParsedTransaction (카드)`** 매칭 로직 — 거래 시각 + 금액 ± 허용 오차 (5 분 / 0 원).

> 23 항목 + Templates API 9 endpoint + 자동완성 5 endpoint + 카드 파서 2 + 매칭 로직 = 실제 단위 작업 35 + 통합 + e2e.

## 작성할 테스트 명세

### 단위 (예상 50+)

`tests/unit/test_upload_guard.py` (6):
- accepts_pdf_with_correct_magic_bytes
- rejects_pdf_with_wrong_extension_or_magic_mismatch
- rejects_oversized_file
- rejects_oversized_batch
- sanitizes_filename_to_ascii_safe (uuid.hex+suffix)
- preserves_korean_filename_in_metadata_not_disk

`tests/unit/test_file_manager.py` (4):
- per_user_directory_isolation
- template_path_uses_user_dir
- session_uploads_dir_creates_on_demand
- outputs_dir_creates_on_demand

`tests/unit/test_card_statement_parser.py` (10+):
- detects_shinhan_xlsx_card_statement
- parses_shinhan_xlsx_to_12_transactions
- detects_samsung_csv_card_statement
- handles_missing_columns_gracefully
- raises_on_unsupported_provider
- transaction_amounts_are_positive_int (AD-4)
- card_number_canonical_format (AD-2)
- ... 등

`tests/unit/test_transaction_matcher.py` (5):
- matches_receipt_to_card_transaction_by_time_and_amount
- handles_no_matching_card_transaction (영수증 단독)
- handles_no_matching_receipt (카드 단독)
- 5_min_tolerance_window
- different_amounts_no_match

`tests/unit/test_template_analyzer.py` 보강 (+4 = 11):
- field_mode_sheet_without_suffix_analyzable
- unrecognized_sheet_marked_needs_mapping
- stop_word_sheet_skipped (차량)
- mapping_status_aggregates_to_needs_mapping

`tests/unit/test_session_status.py` (3):
- enum_transitions_parsing_to_awaiting_user
- enum_transitions_awaiting_user_to_submitted
- invalid_status_raises

`tests/unit/test_validation_rules.py` (4):
- missing_required_fields_flagged_as_missing
- low_confidence_field_flagged_as_review
- all_fields_filled_high_confidence_complete
- filter_query_returns_correct_subset

### 통합 (예상 20+)

`tests/integration/test_sessions_api.py` (8):
- post_sessions_requires_auth (401)
- post_sessions_creates_db_row_and_enqueues_job
- post_sessions_writes_files_to_per_user_dir
- post_sessions_rejects_oversized_or_wrong_magic_bytes (422)
- post_sessions_rejects_other_users_template_id (IDOR 403)
- get_sessions_filters_by_user (IDOR)
- patch_transaction_last_write_wins
- bulk_tag_transactional_rollback_on_partial_failure

`tests/integration/test_sse_stream.py` (5):
- emits_progress_per_file
- emits_completed_after_all_files
- includes_retry_60000_header
- breaks_on_failed_status
- recovers_on_reconnect_with_last_event_id

`tests/integration/test_templates_api.py` (6):
- analyze_then_register_then_get_then_delete
- register_requires_auth
- register_validates_xlsx_magic_bytes (422)
- get_template_filters_by_user (IDOR)
- patch_cells_updates_values_only_no_style
- patch_mapping_updates_column_map

`tests/integration/test_generate_and_download.py` (5):
- generate_creates_3_artifacts (xlsx + pdf + zip)
- download_xlsx_returns_correct_content_disposition
- download_zip_contains_xlsx_and_pdf
- download_other_users_artifact_returns_403 (IDOR)
- stats_endpoint_reports_baseline_diff

`tests/integration/test_dashboard.py` (2):
- summary_aggregates_this_month_metrics
- recent_expense_reports_filtered_by_user

`tests/integration/test_autocomplete.py` (3):
- vendors_q_returns_top_8_by_last_used
- projects_filters_by_vendor_id
- cache_control_max_age_300_header

### e2e (예상 3)

`tests/integration/test_e2e_session_lifecycle.py` (3):
- upload_parse_verify_generate_download_full_flow
- card_statement_xlsx_matches_receipt_jpg_into_transaction
- session_status_transitions_visible_in_topnav_data

## DoD

- [ ] UploadGuard 6 케이스 통과 (3 중 검증 + 한글 metadata 보존)
- [ ] 카드 사용내역 XLSX 파서 — 합성 fixture 통과 + 실 자료 1 종 round-trip (synthesis/05 Smoke Gate 패턴, smoke marker)
- [ ] Sessions API 통합 8 케이스 (auth/IDOR/422/bulk-tag rollback/patch last-write-wins)
- [ ] SSE 5 케이스 (1 초 간격 / retry:60000 / X-Accel-Buffering 검증)
- [ ] Templates API 통합 6 케이스 (셀 PATCH + 매핑 PATCH + IDOR + 422)
- [ ] Generate + Download 5 케이스 (3 artifacts + ZIP 묶음 + IDOR + Content-Disposition 한글 파일명 RFC 5987)
- [ ] Template Analyzer 단위 +4 (ADR-011 신규)
- [ ] e2e 3 케이스
- [ ] mypy --strict + ruff + pip-audit clean
- [ ] alembic 마이그레이션 upgrade → downgrade → upgrade 3 단계 통과 (CLAUDE.md 양방향 강제)
- [ ] smoke 88.1 % 유지 (parser 무변경 sanity check)

## 자율 진행 / 멈춤 조건

### 자율 진행 단위

- Phase 6.1: UploadGuard + FileManager (인프라 1)
- Phase 6.2: alembic 마이그레이션 5 종 (Session.status, processing_*_at, Transaction.original_filename / receipt_file_path, GeneratedArtifact, Template.mapping_status, SheetConfig.analyzable) — 양방향 강제
- Phase 6.3: 카드 사용내역 XLSX/CSV 파서 (신규 영역, TDD)
- Phase 6.4: Transaction Matcher
- Phase 6.5: Template Analyzer ADR-011 휴리스틱 교체
- Phase 6.6: JobRunner + SSE
- Phase 6.7: Sessions API (PATCH + bulk-tag transactional)
- Phase 6.8: Templates API (chip PATCH + cells PATCH 셀 값만)
- Phase 6.9: 자동완성 endpoint 3 + Dashboard
- Phase 6.10: Generate + Download + ZIP + 한글 파일명 Content-Disposition
- Phase 6.11: e2e 통합 3 케이스 + smoke 회귀 검증

각 sub-phase 끝에서 commit + push.

### 멈춤 조건 (사용자 보고 후 대기)

- alembic downgrade 가 데이터 손실 발생 시 (data 손실은 PR 단위 사용자 결정)
- 카드 사용내역 실 자료 입수 불가 (합성 fixture 만으로 진행 가능한지 사용자 확인)
- Templates 셀 PATCH 가 R13 dynamic row 와 충돌 (Phase 5 의 insert_row_at 동작과 conflict)
- IDOR 차단 통합 테스트 통과 안 함
- Smoke 통과율이 88 % 아래로 회귀
- mypy/ruff/pip-audit 실패
- ADR-010 의 추가 결정 필요 7 건 외 새 결정 발견 시 보고

## 의존성 검토

이미 설치:
- pypdf>=4.0 (Phase 5 추가)
- openpyxl>=3.1 (Phase 5 추가)
- structlog (logs)
- aiosqlite + sqlalchemy[asyncio] (DB)
- jose (JWT)

신규 추가 가능성:
- `python-multipart` — 업로드 form (이미 fastapi transitive 가능, 확인 필요)
- `aiofiles` — async 파일 IO (FileSystemManager)
- `sse-starlette` — SSE (FastAPI 표준 + retry/heartbeat)

## ADR-010 보강 추가 결정 7 건 — Phase 6 plan 적용

| 추가 결정 (ADR-010 자료 검증 결과) | Phase 6 반영 |
| --- | --- |
| 다운로드 노출 = layout PDF + XLSX | 본 plan 카테고리 1.8 (GeneratedArtifact 3 row: xlsx + pdf + zip) |
| 카드 사용내역 파서 Phase 6 포함 | 본 plan 카테고리 4.34, 35 |
| Templates 셀 편집 = 셀 값 + 매핑 chips 만 | 본 plan 25, 26 (style/병합 deferred) |
| ADR-011 (시트 휴리스틱 확장) | 본 plan 10, 보강 단위 4 케이스 |
| Baseline 하드코드 15 분/거래 | 본 plan 인프라 5 + Session.processing_time + `app/core/metrics.py` |
| 참석자 hybrid | 본 plan 자동완성 32 (`GET /attendees` + `GET /team-groups`) |
| 영수증 파일명 uuid + metadata | 본 plan 인프라 1, 2, 7 |

## 본 Phase 가 다루지 않은 것 (Phase 7+)

- 메일 발송 (UI Result 의 "팀장님께 메일로 보내기") — Phase 7 외부 서비스 연동
- Templates editor 의 style/병합/줌/formula bar 풀 구현 — Phase 8+
- Baseline 사용자별 누적 평균 — Phase 8+ (Phase 6 은 하드코드)
- ADR-009 (qwen2.5vl 가맹점명 빈 응답 retry/prompt 강화) — 별도 트랙

## Phase 6 완료 후 Phase 7 진입 게이트

- 모든 DoD 통과 + smoke 88 % 유지 + e2e 3 케이스 GREEN
- phase-6-done.md 작성 + 사용자 승인 대기 (Phase 7 UI 본격 구현 진입)
