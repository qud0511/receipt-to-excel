---
id: ADR-010
title: UI 예제 (CreditXLSX) 분석 — Phase 6 라우터 시그니처 사전 명세
date: 2026-05-12
status: accepted
refs:
  - /bj-dev/old/receipt-to-execl-ui-example/ (예제 디렉토리)
  - synthesis/04-design.md §"API 표면"
  - synthesis/05-implementation-plan.md §"Phase 6"
  - ADR-006 (지출결의서 양식 분석 — 동일 사전 분석 패턴)
note:
  - "ADR-009 는 OCR LLM 가맹점명 빈 응답 해소용으로 예약 (`docs/limitations/ocr_qwen_vendor_name.md`)."
  - "본 ADR 은 직접 참조가 synthesis 에 없던 UI 예제를 Phase 6 진입 전에 라우터 시그니처에 직접 반영 가능한 수준으로 명세."
---

# 결정

CreditXLSX UI 예제 (`old/receipt-to-execl-ui-example/`) 의 5 화면을 분석해
Phase 6 라우터 시그니처·SSE 메시지 스키마·DTO 매핑을 사전 고정. **Phase 6 본 진입 전에**
백엔드 API 가 UI 요구 데이터를 정확히 제공하도록 라우터 시그니처 + 추가 도메인 entity 확정.

ADR-006 (지출결의서 양식 분석을 Phase 5 전에 작성한 패턴) 과 동일 — 외부 자료를 사전 분석해
구현 시그니처를 안정화.

# 컨텍스트 — 예제의 정체성

`old/receipt-to-execl-ui-example/`:
- `credit-xlsx-v2.html` (4 KB) — 메인 페이지. flow = `dash → upload → verify → result` + `templates` (separate).
- 5 화면 HTML (각 2-8 MB, self-contained bundled exports — code 직접 분석 불가, Korean text grep 으로 inventory 추출).
- `components.jsx`, `data2.jsx`, `variations.jsx` — 공유 component + sample data + 3 layout variants.
- `design-canvas.jsx` — Figma-style pan/zoom wrapper (UI 가 아닌 design tool, Phase 6 무관).

브랜드명: **CreditXLSX**. 한국어 UI. 폰트: Inter (영문) + JetBrains Mono (숫자).
타깃 사용자: 회사 직원 (영수증 사진 + 카드 사용내역 업로드 → AI 추출 → 검수 → XLSX/PDF 다운로드).

# 화면 Inventory (5)

## 1. Dashboard

플로우 진입점. 사용자가 처음 보는 화면.

### 표시 요소
- 인사: "안녕하세요 {employee_name}님 / 이번 달 결제 {N}건 / {M}건이 미입력 상태입니다"
- **CTA**: "지출결의서 작성" (→ Upload 화면)
- KPI 4종:
  - 이번 달 총 지출 (전월 대비)
  - 결제 건수 (미입력 {N}건 강조)
  - 완료된 결의서 (올해 누적 {N}건)
  - 절약된 시간 ({N}시간, 자동 추출 기준)
- 최근 작성한 지출결의서 list (각 row: 양식명·영수증 N장·상태=`작성중`/`미입력`/`제출완료`)

### 백엔드 요구
- `GET /dashboard/summary` — 이번 달 metric + 최근 결의서 N개

## 2. Upload

영수증·전표 일괄 업로드. 드래그 앤 드롭.

### 표시 요소
- 헤더: "매출전표 일괄 업로드"
- 설명: "법인카드 사용내역과 영수증 사진을 한 번에 올려주세요. {N} 항목을 자동 추출합니다."
- Drop zone: "파일을 여기로 드래그하세요 / 또는 클릭해서"
  - 영수증 사진 / 카드 사용내역 — 2 카테고리 동시 업로드
  - 제약: 최대 50 MB, 한 번에 100장까지
- 업로드 후 진행: "업로드된 파일 {N}개 — 모두 추출 완료"
- 파일별 추출 결과 미리보기: 가맹점명 추출 / 거래처 추정 실패 / 거래처·프로젝트 자동 매칭

### 백엔드 요구
- `POST /sessions` (multipart files + template_id) — 업로드 + 잡 큐
- `GET /sessions/{id}/stream` (SSE) — 1 초 간격 진행률
- `GET /sessions/{id}` — 완료 후 추출 결과 list

## 3. Verify (검수, 핵심 화면)

좌 영수증 / 우 그리드 split view + 자동완성 + 컬러 신뢰도 + 일괄 적용.

### 표시 요소
- 좌 panel: 원본 영수증 이미지
  - 추출 details: 가맹점명·일시·사업자번호·대표명·전화·메뉴·합계·카드·승인번호
- 우 panel: 데이터 그리드 + 엑셀 미리보기 토글
  - Filter chips: 전체 / 필수 누락 / 재확인 필요 / 완료
  - 각 row: 일시·가맹점·분류·입력정보(거래처·프로젝트·용도·N인)·금액·상태
  - 상태 pill: `입력완료` / `미입력` (color-coded)
  - **신뢰도** 컬러 (high/medium/low/none) 셀별 표시
- 자동완성: 거래처·프로젝트·참석자 (RECENT_VENDORS, RECENT_PROJECTS dict 기반)
- 입력 form (TaggingForm):
  - 거래처명 (최근 5건 suggest chip)
  - 프로젝트명 (거래처 선택 후만 활성, RECENT_PROJECTS[vendor] suggest)
  - 용도 (중식/석식/회의/택시/간식/출장 — 6 PURPOSE_ICONS)
  - 참석 인원 (counter + 1인당 금액 자동 계산)
  - 영수증 첨부 (drag/click — 1.2 MB · JPG 표시)
- **일괄 적용** (UI 명시): 다중 선택 후 같은 거래처/프로젝트 일괄 입력
- 하단: SummaryBar (총 N건, 입력완료 M/N, 합계 ₩총액, "정산 마감일까지 D-N")
- CTA: "저장하고 다음" / "건너뛰기" / "완료하고 다운로드"

### 백엔드 요구
- `GET /sessions/{id}/transactions` — 거래 list + field_confidence + parser_used
- `PATCH /sessions/{id}/transactions/{tx_id}` — 사용자 수정 저장 (vendor/project/purpose/headcount/attendees/receipt)
- `POST /sessions/{id}/transactions/bulk-tag` — 일괄 적용 (transaction_ids[] + tag payload)
- `GET /sessions/{id}/transactions/{tx_id}/receipt` — 영수증 이미지 (per-user FS)
- `GET /sessions/{id}/preview-xlsx` — 엑셀 미리보기 (cell grid JSON, R13 적용 후)

## 4. Result (다운로드)

지출결의서 완성 화면. 다운로드 + 공유 옵션.

### 표시 요소
- 헤더: "지출결의서 완성"
- 미리보기: 양식 (파견용 등) + 증빙 (영수증 합본)
  - "기준 3페이지 모아찍기 적용" — layout PDF (R11 — 본 ADR Phase 5 layout_pdf 와 일치 ✓)
- 메타: 합계 / 양식명 / 작성자명 / "파견용 양식 적용 / 자동 합계 포함"
- 다운로드 옵션 (4종):
  - XLSX 파일 (지출결의서)
  - 증빙 PDF (영수증 layout)
  - 증빙 PDF (영수증 합본 — merged)
  - ZIP (위 3종 묶음) — "ZIP으로 한 번에 받기"
- 공유: "팀장님께 메일로 보내기" (Phase 7 검토, Phase 6 범위 외)
- 통계: 처리 시간 / 평소 대비 시간 단축 (메트릭)
- Back: "검수 화면으로"

### 백엔드 요구
- `POST /sessions/{id}/generate` — XLSX + merged PDF + layout PDF 생성 (Phase 5 산출 호출)
- `GET /sessions/{id}/download/{kind}` — `kind` ∈ `xlsx`/`merged_pdf`/`layout_pdf`/`zip`
- `GET /sessions/{id}/stats` — 처리 시간 / 평소 대비 (메트릭)

## 5. Templates Management

회사별 양식 파일 미리보기 · 직접 편집.

### 표시 요소
- 헤더: "템플릿 목록" + "템플릿 업로드" CTA
- 카드 list (각 카드):
  - 양식 이름 + 태그 (예: "파견용 양식 / 기본", "신용정보원 지출결의서", "코스콤 외주 양식 / 월정산 / 매핑 필요")
  - 상태: `매핑 완료` / `매핑 필요`
  - Actions: `미리보기` / `편집` / `매핑 설정` / `양식만 받기` (raw xlsx 다운로드)
- 업로드 zone: "양식 파일 끌어다 놓기"
- 편집 mode: 셀 더블클릭으로 직접 수정 + 열·행 경계 드래그 (R13 grid)
- 매핑 설정: "필드 매핑 — 거래일" 등 (Phase 5 Analyzer 결과 + 사용자 override)
- 저장 CTA

### 백엔드 요구
- `GET /templates` — 사용자별 list (Phase 2 template_repo.list_for_user 활용)
- `POST /templates/analyze` — 업로드 .xlsx → AnalyzedTemplate 미리보기 (영속 X) — **Phase 5.4 deferred 항목**
- `POST /templates` — 등록 (TemplateConfig 영속 + FS 저장)
- `GET /templates/{id}/grid` — 셀 grid JSON (편집 UI 용)
- `PATCH /templates/{id}` — 매핑/이름 수정
- `DELETE /templates/{id}` — IDOR 차단 (Phase 2 template_repo.get 활용)
- `GET /templates/{id}/raw` — 원본 .xlsx 다운로드

# Entity 매핑 → 현 백엔드 도메인

## 화면별 entity 의존성

| 화면 | 의존 entity | 신규 entity (없으면 추가) |
| --- | --- | --- |
| Dashboard | Session, Transaction, ExpenseRecord, Template | DashboardSummary (응답 DTO 만, DB X) |
| Upload | Session (생성), Transaction (auto), Card | — |
| Verify | Transaction, ParsedTransaction, ExpenseRecord, Vendor, Project, Attendee, Card | — |
| Result | Session, generated files (XLSX/PDF) | GeneratedArtifact (FS path + kind enum) — 또는 Session 컬럼 4종 추가 |
| Templates | Template, TemplateConfig, SheetConfig | — |

## 현 도메인과의 정합

| 영역 | 현 상태 (Phase 5 종료) | UI 갭 |
| --- | --- | --- |
| ParsedTransaction.field_confidence | 4-label (high/medium/low/none) per 필드 | ✅ UI 의 컬러 코딩과 정확히 일치 (data2.jsx merchantConf/vendorConf 등) |
| Card.card_type (`법인`/`개인`) | ✅ | UI 의 `법인카드 ****3821` chip 과 일치 |
| ExpenseRecord (vendor/project/purpose/attendees/headcount) | ✅ TaggingForm 의 입력 모두 보유 | — |
| Vendor / Project / Attendee | ✅ 도메인 entity 존재 | autocomplete API 추가 필요 |
| TeamGroup | ✅ models.py 에 존재 (확인 필요) | 참석자 선택 시 `개발1팀: [홍길동, ...]` 그룹 단위 선택 UI 지원 |
| Template / SheetConfig | ✅ Phase 5 산출 | API 라우터 + raw .xlsx 다운로드 추가 필요 |
| Session.status | 현재 미정 (Phase 6 정의 예정) | UI 요구: `작성중`/`미입력`/`제출완료` 3 enum |
| GeneratedArtifact | ❌ 미존재 | 4 종 (xlsx/merged_pdf/layout_pdf/zip) FS 경로 + Session FK |

# Phase 6 라우터 시그니처 (사전 고정)

OpenAPI 스타일 명세 — Phase 6 본 구현 시 그대로 채택.

## Dashboard
```
GET /dashboard/summary
  → {
      this_month: { total_amount, txn_count, pending_count, prev_month_diff_pct },
      this_year: { completed_count, time_saved_hours },
      recent_expense_reports: [
        { session_id, template_name, receipt_count, status, updated_at }
      ]
    }
```

## Sessions (Upload + Verify + Result)
```
POST /sessions
  Body: multipart (receipts[], card_statements[], template_id)
  → { session_id, status: "queued" }

GET /sessions/{id}/stream  (SSE, retry: 60000)
  Event: { stage: "ocr"|"llm"|"resolve"|"done", file_idx, total, msg }

GET /sessions/{id}/transactions
  → list[Transaction + ParsedTransaction + ExpenseRecord (optional) + field_confidence]

PATCH /sessions/{id}/transactions/{tx_id}
  Body: { vendor, project, purpose, headcount, attendees[], receipt_attachment_url }
  → { ok: true, updated_record }

POST /sessions/{id}/transactions/bulk-tag
  Body: { transaction_ids[], patch: {vendor, project, purpose, ...} }
  → { updated_count }

GET /sessions/{id}/transactions/{tx_id}/receipt
  → image/jpeg or application/pdf (per-user FS)

GET /sessions/{id}/preview-xlsx
  → { sheets: { "26.05_법인": [[cell, cell, ...], ...] } }

POST /sessions/{id}/generate
  → { artifacts: [{kind, url}, ...] }
  artifacts kind ∈ "xlsx" | "merged_pdf" | "layout_pdf" | "zip"

GET /sessions/{id}/download/{kind}
  → binary stream + Content-Disposition

GET /sessions/{id}/stats
  → { processing_time_s, avg_baseline_s }
```

## Templates
```
GET /templates
  → list[{id, name, tag, status: "mapped"|"needs_mapping", updated_at}]

POST /templates/analyze
  Body: multipart (.xlsx)
  → AnalyzedTemplate (preview only, 영속 X)

POST /templates
  Body: multipart (.xlsx, name, tags[])
  → { template_id }

GET /templates/{id}/grid
  → { sheets: { name: {cells: [[{row, col, value, style}, ...], ...]} } }

PATCH /templates/{id}
  Body: { name?, tags?, sheets?: { name: SheetConfig } }
  → { ok }

DELETE /templates/{id}
  → 204

GET /templates/{id}/raw
  → .xlsx binary
```

## 자동완성 (Verify autocomplete)
```
GET /vendors?q={query}&limit=8
  → list[{vendor_id, name, last_used_at}]

GET /projects?vendor_id={id}&limit=8
  → list[{project_id, name, last_used_at}]

GET /attendees?q={query}  (또는 GET /team-groups → 팀 → 멤버 nested)
  → list[{employee_id, name, team}]
```

# SSE 메시지 스키마

UI 의 Upload 화면 "추출됨"/"완료"/"거래처 추정 실패" 메시지 → SSE stage event.

```python
# 단계 ENUM
SSEStage = Literal[
    "uploaded",      # 업로드 수신
    "ocr",           # Docling OCR 진행 중 (file_idx/total 명시)
    "llm",           # OCR Hybrid LLM 호출 중
    "rule_based",    # rule_based parser 실행 중
    "resolved",      # CardTypeResolver / category 결정 완료
    "vendor_failed", # 거래처 추정 실패 (UI "거래처 추정 실패" 메시지)
    "done",          # 잡 완료
    "error",         # 잡 실패 (file 단위)
]

SSEMessage = {
    "stage": SSEStage,
    "file_idx": int,
    "total": int,
    "filename": str,
    "msg": str,        # UI 표시용 ("법인카드 사용내역 추출됨" 등)
    "tx_id": int | None,  # resolved/vendor_failed 시 추출된 transaction
}
```

CLAUDE.md §"성능": `retry: 60000` + `X-Accel-Buffering: no` + 1 초 간격.

# 갭 분석 — Phase 5 종료 시점 vs UI 요구

## 이미 지원되는 것 ✅

- ParsedTransaction.field_confidence (4-label) — Verify 신뢰도 컬러 코딩 정확 일치
- Card.card_type 법인/개인 → 시트 라우팅 (Phase 5 XLSX Writer)
- ExpenseRecord 의 vendor/project/purpose/attendees/headcount/receipt_attachment_url — TaggingForm 의 모든 입력 보유
- Vendor / Project / Attendee 도메인 entity
- Template / SheetConfig / Analyzer / Injector — 템플릿 미리보기 + 매핑 (Phase 5)
- XLSX Writer R13 + merged_pdf + layout_pdf — Result 화면의 다운로드 4종 중 3종 직접 호출 가능 (zip 만 신규)

## 추가 필요한 것 (Phase 6 범위 추가)

### A. 라우터 (10+ 신규 endpoint)
- 위 §"Phase 6 라우터 시그니처" 의 모든 endpoint
- 특히 `PATCH /sessions/{id}/transactions/{tx_id}` (Verify 핵심) — Phase 6 plan 명시 필요
- `POST /sessions/{id}/transactions/bulk-tag` (일괄 적용) — synthesis 미언급, **신규 작업**

### B. 도메인 entity 신규 (1)
- **GeneratedArtifact**: Session FK + kind enum (xlsx/merged_pdf/layout_pdf/zip) + fs_path + created_at
  - 또는 Session 모델에 4 컬럼 추가 (xlsx_path, merged_pdf_path, layout_pdf_path, zip_path)
  - 권장: 별도 entity (확장성 + Phase 7+ 의 history 추적 용)

### C. Session.status enum 확정
- UI 표시 3종: `작성중` / `미입력` / `제출완료`
- 백엔드 매핑: `parsing` / `awaiting_user` / `submitted` (영문 snake_case, 한↔영 mapper 에서 표시명 변환)

### D. ZIP 생성기 (신규)
- `app/services/generators/zip_bundler.py` — xlsx + merged_pdf + layout_pdf 묶음
- 파일명 패턴: `{YYYY}_{MM}_지출결의서_bundle.zip`
- Phase 5.3 PDF generators 와 동일 위치 (`app/services/generators/`)

### E. 자동완성 endpoint 3종
- vendor (Phase 4 `services/resolvers/vendor_matcher.py` 활용 — autocomplete `DEFAULT_LIMIT=8` 이미 명시)
- project (vendor_id FK 기반)
- attendees (team_groups 또는 employee 검색)

### F. Dashboard summary 집계 endpoint
- this_month aggregation + recent_expense_reports list
- Phase 2 repository 확장 또는 신규 service

### G. Verify 의 일괄 적용 UX (synthesis 미언급)
- 다중 row 선택 + 같은 vendor/project/purpose 일괄 입력
- 비즈니스 결정: 신규 작업이지만 UX 핵심 — Phase 6 plan 포함 권장

### H. 영수증 이미지 매칭 (Verify 좌 panel)
- Verify 화면이 transaction → 원본 영수증 이미지 표시
- 업로드 시점에 (transaction ↔ receipt file) 매핑 결정 필요
  - 현재: ParsedTransaction 은 거래 정보만, 원본 파일 경로 없음
  - 추가 필요: Transaction 모델에 `receipt_file_path` 컬럼 + Resolver/Parser 가 채움
  - **이미 ExpenseRecord.receipt_attachment_url 있음** — Parser 단계에서 채워야

## 사용자 결정 필요한 갭 (큼)

1. **일괄 적용** (Verify) — synthesis 명시 없음, UX 핵심. Phase 6 포함 권장.
2. **ZIP 다운로드** — synthesis 명시 없음, UI 명시. Phase 6 추가.
3. **공유 (메일/팀장에게)** — Phase 7 (외부 서비스 연동) 으로 deferred.
4. **Dashboard 집계** — synthesis 명시 없음 (단순 GET 만 명시). Phase 6 또는 Phase 7.
5. **셀 직접 편집** (Templates) — synthesis 의 "grid 미리보기 (셀 편집은 제외)" 와 UI 의 "셀 더블클릭으로 직접 수정" 충돌. UI 가 더 강한 요구. **사용자 결정 필요**.

## 사용자 결정 필요한 갭 (작음)

1. **시간 단축 메트릭** (Dashboard/Result) — baseline 평균 처리 시간을 어디서 계산? 사용자별 / 전체 평균 / 하드코드?
2. **참석자 자동완성 vs team_group 그룹 선택** — UI 가 둘 다 보이지만 priority 불명.
3. **영수증 첨부 파일명 규약** — `receipt-{timestamp}.jpg` UI 명시, 백엔드는 uuid 권장 (CLAUDE.md §"업로드 3중 검증").

# Phase 6 작업 범위 갱신 권장

phase-6-plan.md 작성 시 본 ADR 의 다음 항목 포함:

1. ✅ synthesis/05 의 Phase 6 원본 (`UploadGuard` + `FileManager` + `JobRunner` + `SessionsAPI` + `SSE`)
2. ➕ Templates API Routes (Phase 5.4 deferred 항목, 본 ADR §"Templates" 시그니처 그대로)
3. ➕ Sessions API 의 `PATCH /transactions/{id}` + `POST /transactions/bulk-tag`
4. ➕ Dashboard summary endpoint
5. ➕ ZIP bundler (`app/services/generators/zip_bundler.py`)
6. ➕ Vendor/Project/Attendees 자동완성 endpoint 3종
7. ➕ GeneratedArtifact entity (또는 Session 4 컬럼 확장)
8. ➕ Session.status enum 3종 확정 + alembic 마이그레이션
9. ➕ Transaction.receipt_file_path 컬럼 (Verify 좌 panel 원본 영수증 표시)

# Phase 7 UI 디자인 톤·레이아웃·인터랙션 기준점

본 예제가 정의하는 디자인 정체성:

| 영역 | 결정 |
| --- | --- |
| 브랜드명 | CreditXLSX |
| 폰트 | Inter (영문) + JetBrains Mono (`.num` class) |
| 색상 톤 | Warm gray bg (`#f0eee9`, design canvas) + accent orange `#c96442` |
| 컴포넌트 라이브러리 | shadcn-style — `.btn-ghost`, `.btn-primary`, `.chip`, `.purpose-tile`, `.suggest-chip`, `.status-pill` (`tagged`/`untagged`) |
| 아이콘 | inline SVG, `Icon.Search`/`Calendar`/`Filter`/`Download`/`Plus`/`Receipt`/`Close`/`Chevron`/`Check`/`Sparkle` |
| Layout 선호도 | 1440 × 900 (Desktop-first), Verify 는 split view (master-detail 또는 inline accordion 또는 bottom drawer 3 variants) |
| 인터랙션 패턴 | 드래그앤드롭 업로드 / 자동완성 chip (최근 5건) / 신뢰도 컬러 코딩 셀 / 다중 선택 → 일괄 적용 / 단계별 progress (Dashboard → Upload → Verify → Result) |
| 표기 | 한국어 (en mix 최소화), 금액 = `₩X,XXX` 또는 `X,XXX원`, 날짜 = `2025.12.02` (점 구분자) |
| 마감일 카운트다운 | "2026년 5월 정산 마감일까지 D-12" — SummaryBar 우측 |

Phase 7 진입 시 `synthesis/04 §"UI"` 의 일반 UX 원칙 + 본 ADR 의 톤·컴포넌트 카탈로그 결합.

# 대안 폐기

| 대안 | 폐기 사유 |
| --- | --- |
| **UI 예제 무시, synthesis API 표면만 따름** | synthesis 가 명시 안 한 일괄 적용·자동완성·ZIP 다운로드 등이 UI 핵심 — 누락 시 Phase 7 UI 가 백엔드 다시 깎아야 함 (v3 회귀 패턴). |
| **HTML self-contained export 파싱** | 2-8 MB 번들 형태, source-level 컴포넌트 추출 불가. JSX 3 파일 + Korean text grep 이 충분. |
| **변형 (variations.jsx) 3종 모두 구현** | A/B/C variants 중 1 채택 결정은 Phase 7 디자인 단계. 백엔드는 변형 무관 (동일 API). |
| **Phase 5.4 Templates API 본 phase 에 backport** | Phase 6 의 `UploadGuard` + `get_or_create_user_by_oid` 인프라 미비. Phase 6 통합이 정합. |

# 후속

1. **phase-6-plan.md 작성 시** 본 ADR §"Phase 6 작업 범위 갱신 권장" 9 항목 반영.
2. **사용자 결정 필요 큰 갭 5건** 본 ADR §"사용자 결정 필요한 갭 (큼)" 사용자 응답 후 plan 확정.
3. **Phase 6 시작 후** — 새 entity (GeneratedArtifact 등) 발생 시 ADR-006 패턴 따라 추가 ADR 작성.
4. **Phase 7 UI 진입 시** — 본 ADR §"디자인 톤·레이아웃·인터랙션 기준점" 을 출발점.

---

# 자료 검증 결과 (2026-05-12 추가)

`v4/ui_reference_1/` 에 PNG 캡처 5장 + 동일 JSX/CSS 도착 (jsx/css/html 은 `old/receipt-to-execl-ui-example/` 과 100% 일치 — `diff -q` 0 결과). 5 PNG 시각 분석으로 본 ADR 초안의 추론을 자료에 대조 검증.

## A. 일치 항목 (초안 추론 정확) ✅

1. 브랜드명 `CreditXLSX` + CX logo + 한국어 UI.
2. 화면 5종 (Dashboard / Upload / Verify / Result / Templates) 정확 일치.
3. 일괄 업로드 (영수증 사진 + 카드 사용내역 동시).
4. 신뢰도 4-label 컬러 코딩 — 본 ADR 추론과 정확 일치 (`field_confidence` 직접 매핑).
5. 자동 매칭 (vendor/project) + "거래처 추정 실패" UX.
6. 모아찍기 layout PDF (R11) + ZIP 한 번에 받기 + 팀장님께 메일.
7. SUM 자동 포함 (XLSX 출력).
8. 5 화면별 백엔드 요구 endpoint 의 큰 범주 (Sessions / Templates / Dashboard / 자동완성).

## B. 보정 항목 (초안과 자료 차이) 🔧

### B-1. 다운로드 파일 4종 → **2종 (+ ZIP action)**

| 초안 | 자료 |
| --- | --- |
| xlsx / merged_pdf / layout_pdf / zip = 4 파일 | **PDF 1 + XLSX 1 + ZIP 묶음 action 1 + 메일 action 1** |

UI Result 캡처:
- PDF: `증빙_영수증_합본_2025_12.pdf` (A4 기준 3페이지 · 모아찍기 적용 · 12장 영수증) — **merged + layout 통합 1 파일** (raw merged 미노출, layout 만)
- XLSX: `2025_12_지출결의서_홍길동.xlsx`
- ZIP 은 "ZIP으로 한 번에 받기" action (위 2 파일 묶음)
- 메일은 별도 action (Phase 7+)

영향: `layout_pdf.py` 결과물이 디폴트 노출. `merged_pdf.py` 는 layout 의 입력 단계 (raw 페이지 합본 → 모아찍기 → layout 최종 PDF) 또는 별도 노출 안 함. **사용자 결정 필요** (§D-A 참조).

### B-2. 파일명 패턴 보정

| 영역 | 초안 (R12) | 자료 |
| --- | --- | --- |
| XLSX | `{YYYY}_{MM}_지출결의서.xlsx` | `{YYYY}_{MM}_지출결의서_{user_name}.xlsx` |
| PDF | `{YYYY}_{MM}_지출증빙자료.pdf` | `증빙_영수증_합본_{YYYY}_{MM}.pdf` |

영향: Phase 5 `generate_output_filename(year, month)` 시그니처에 `user_name: str` 인자 추가 필요. `generate_layout_pdf_filename` 도 패턴 갱신.

### B-3. TopNav step indicator → Session.status 매핑

UI 모든 화면 상단에 step bar: **① 업로드 → ② 검수·수정 → ③ 다운로드**.
완료된 step 은 ✓ 체크 (Verify/Result 캡처에서 ① / ② ✓ 확인).

Session.status 3 enum 매핑 (§D-3 사용자 결정 반영):
- `parsing` → ① 업로드 활성 (OCR/LLM 추출 중) — 진입 시 SSE 진행 표시
- `awaiting_user` → ② 검수·수정 활성 (사용자 입력 대기)
- `submitted` → ③ 다운로드 활성 (사용자 저장 + generate 완료)

`Session.status` 컬럼 + alembic 마이그레이션 + 한↔영 mapper (UI 표시 = "작성중" / "제출완료" / "미입력") 모두 신규.

### B-4. 업로드 파일 형식 확장: + **XLSX, CSV**

Upload 캡처: "PNG, JPG, PDF, XLSX, CSV · 최대 50MB · 한 번에 100장까지".
초안은 영수증 PDF/JPG 만 가정. UI 는 **카드 사용내역 XLSX/CSV** 도 같은 화면에서 업로드 (`법인카드_2025_12.xlsx · ₩1,026,400 · 12건`).

영향: **신규 파서** — `app/services/parsers/card_statement/{xlsx,csv}.py` (Phase 4 의 rule_based 영수증 parser 와 별도). 큰 갭 — §D-B 참조.

### B-5. Verify 그리드 컬럼 = 9개 (초안의 7+α 보다 정확)

UI: `AI신뢰도% | 일시 | 가맹점 | 분류 | 거래처 | 프로젝트 | 용도 | 인원 | 참석자`.
- `AI신뢰도%` 컬럼: row-level 종합 신뢰도 (예: 87% = high/medium/low 가중 평균).
- `분류` 컬럼: 가맹점 카테고리 (한식/교통/카페 등) — 도메인의 `업종` (parser 가 추출) 또는 가맹점명 → category 자동 분류 결과.

영향: `GET /sessions/{id}/transactions` 응답에 row-level confidence 종합 score 추가 권장. 분류 컬럼은 `ParsedTransaction.업종` 직접 매핑.

### B-6. Templates 양식 mode 가 **2 종류 공존**

| 양식 종류 | 시트 명명 | 컬럼 mode | 예시 |
| --- | --- | --- | --- |
| **Category mode** | `{YY.MM}_법인/개인/차량` (ADR-006) | 식대/접대비/기타비용 별도 컬럼 | 실 양식 3장 |
| **Field mode** | `지출결의서/증빙요약/월별집계` (UI 캡처) | 단일 row = 1 거래 (연번/거래일/거래처/프로젝트/용도/인원/금액/동석자/비고) | UI 의 "A사 파견용 양식" |

Phase 5 `SheetConfig.mode` (`field/category/hybrid`) 가 이미 이를 분리하므로 ✓. 단:

- **시트명 suffix 가정 갱신 필요**: ADR-006 의 `_법인/_개인` 만 분석 대상이라는 가정은 **Field mode 양식에 적용 불가**. Template Analyzer 가 시트별 분석 가능 여부를 휴리스틱으로 판정 (A2 마커 + 헤더 row 7 패턴 + 데이터 영역 추정).
- **컬럼 매핑 chips UI**: `A 거래일 · B 거래처명 · C 프로젝트명 · D 용도 · E 인원 · F 금액 · H 동석자 · I 매핑 안됨` — Field mode 양식의 매핑 UI. PATCH /templates/{id} 가 시트별 column_map dict 받음.

### B-7. Templates editor = **풀 Excel-like 셀 편집** (UI 강한 요구)

초안의 "셀 직접 편집 deferred" 결정 ← UI 가 명시적 반대:

UI 캡처 (Templates 편집 view):
- 편집 mode toggle button
- **Toolbar**: 굵게/기울임/밑줄 | 정렬 3종 | 셀 병합 | 테두리 | 배경색 | 줌 100%
- **Formula bar**: `G7 / fx =SUM(G7:G18)`
- 셀 더블클릭 인라인 편집 + 행/열 경계 드래그 리사이즈
- **노란 셀 = data area 표시** (R13 동적 행 삽입 위치 시각화)
- **Sheet tabs**: `지출결의서 | 증빙요약 | 월별집계 | +` (다중 시트 navigation)
- **Status bar**: 행 12 | 합계 574,700 | 평균 95,783 | 개수 6 (Excel 풍 자동 통계, 클라이언트 계산)

영향: 백엔드는 **셀 단위 PATCH endpoint** + **양식 raw download/upload** 양쪽 모두 지원. §D-B 참조.

### B-8. Result "처리 시간" + Dashboard "절약된 시간" → Session 메트릭

- Result Footer: "처리 시간 2분 18초 · 평소 대비 14시간 단축"
- Dashboard KPI: "절약된 시간 14시간 (AI 자동 추출 기준)"

Session 모델에 `processing_started_at`, `processing_completed_at` 컬럼 신규. Baseline (수동 작업 평균 시간) 은 §D-A 사용자 결정.

### B-9. Verify Filter chips — 백엔드 validation 정의 필요

UI: `전체 12 | 필수 누락 N | 재확인 필요 N | 완료 N`

- **필수 누락**: 가맹점/거래일/금액/거래처/용도 중 누락. 백엔드 validation rule 정의 필요.
- **재확인 필요**: `field_confidence` 가 `low` 또는 `none` 인 cell 보유 row.
- **완료**: 모든 필수 필드 채움 + 신뢰도 medium 이상.

영향: `GET /sessions/{id}/transactions?status={all|missing|review|complete}` 쿼리 파라미터 추가.

## C. 신규 발견 항목 (초안 누락) 🆕

### C-1. 카드 사용내역 XLSX/CSV 파서 — **신규 Phase 6 작업**

UI Upload: `법인카드_2025_12.xlsx · ₩1,026,400 · 12건` — 카드사 다운로드 XLSX 가 12 거래 추출됨.

**Phase 4 의 rule_based 영수증 parser 와 별도 파서 신규 필요**:
- `app/services/parsers/card_statement/xlsx_parser.py`
- `app/services/parsers/card_statement/csv_parser.py`
- 도메인 출력: `list[ParsedTransaction]` (영수증 parser 와 동일 계약)
- 카드사별 양식 가변 — Phase 4 rule_based pattern 동일 (provider 감지 → rule_based parser 선택)
- 영수증 사진과 매칭 로직: 거래 시각 + 금액 기반 (`Receipt ↔ CardStatement transaction` 매칭) — **양쪽 다 있을 때 영수증 사진을 transaction.receipt_file_path 로 link**

### C-2. ExpenseRecord "비고" (note) 컬럼 누락

UI Templates 의 A사 양식 마지막 컬럼 = `I 비고`. 도메인의 `ExpenseRecord.auto_note` 와 매핑 자연.
**누락된 entity 컬럼은 없음** — `auto_note` 가 비고 매핑.

### C-3. "연번" 자동 생성

A사 양식 A 컬럼 = 연번 (1, 2, 3, ..., 12). 사용자 입력 X, XLSX writer 가 row index 자동 채움.
`SheetConfig` 에 `auto_index_col: str | None` 추가 또는 XlsxWriter 가 첫 column 자동 인식.

### C-4. "동석자" list → str 변환

ExpenseRecord.attendees: list[str] → XLSX 셀 1개에 `"홍길동, 김지호, 박서연"` 형태. XlsxWriter 변환 로직 필요 (한 줄).

### C-5. 사용자명 in 파일명 + 결의서 헤더

UI: 양식 row 3 "작성자: 홍길동" + Result 파일명 `2025_12_지출결의서_홍길동.xlsx`. Session → User.name 조회 필요.

### C-6. Sheet tabs (Templates editor) — 3+ tab navigation

UI: `지출결의서 | 증빙요약 | 월별집계 | +`. `TemplateConfig.sheets` 가 dict 라 이미 지원하지만 UI 는 시트별 다른 분석 결과 표시.

### C-7. 매핑 chips bar (Templates)

`A 거래일 · B 거래처명 · ... · I 매핑 안됨` — Phase 5 Template Analyzer 의 SheetConfig.{date_col, merchant_col, ...} 매핑을 chip 단위로 표시. PATCH /templates/{id} 가 chip 단위 override 받음.

### C-8. AI 자동 매칭률 통계 표시

Upload footer: "AI가 12건 중 7건의 거래처/프로젝트를 자동으로 매칭했어요" — Verify 진입 전 통계.
`POST /sessions/{id}/parse-complete` 응답 또는 `GET /sessions/{id}` 응답에 `auto_match_count` 필드 신규.

## D. 사용자 결정 답 반영 (5건) + 추가 결정 필요

### D-1 ~ D-5 (이번 세션 사용자 답)

| 결정 | 답 | ADR 영향 |
| --- | --- | --- |
| **D-1. bulk-tag 부분 실패 처리** | **전체 롤백** | `POST /sessions/{id}/transactions/bulk-tag` 가 transactional — 한 row 라도 실패하면 `409 Conflict` + 전체 rollback. error response 에 `failed_tx_ids[]` + 사유. |
| **D-2. 동시 편집 충돌** | **last-write-wins** (Phase 6 단순화) | PATCH /sessions/{id}/transactions/{tx_id} 에 ETag/If-Match 헤더 없음. Phase 7+ 에서 optimistic concurrency 재검토. `updated_at` 만 응답 포함. |
| **D-3. Session.status enum** | **parsing / awaiting_user / submitted 3종** | 본 ADR §B-3 매핑대로. alembic 마이그레이션 + ENUM constraint 추가. 한↔영 mapper 에서 UI 표시 "작성중" / "미입력" / "제출완료" 매핑. |
| **D-4. GeneratedArtifact entity** | **별도 테이블** | `app/db/models.py` 에 신규 모델 추가. 컬럼: `id, session_id (FK), artifact_type (enum: xlsx/pdf/zip), fs_path, created_at`. Session ↔ GeneratedArtifact 1:N relationship. |
| **D-5. 자동완성 응답 캐시** | **클라이언트 캐시 5분** | `GET /vendors`, `GET /projects`, `GET /attendees` 응답에 `Cache-Control: max-age=300` 헤더. 서버측 캐시 X (단순화). |

### D-A. 자료 검증으로 새로 발견된 결정 필요 항목 (사용자 답 대기) 🔔

1. **다운로드 파일 노출 정책**: UI 는 layout PDF (모아찍기) + XLSX 만 노출. merged PDF (raw 페이지 합본) 은 별도 노출 안 함?
   - 후보 A: layout PDF 만 (UI 충실, merged 는 layout 의 내부 단계)
   - 후보 B: layout + merged 양쪽 다 (사용자가 raw 도 원할 수 있음)
   - 후보 C: 사용자 설정 토글 (Templates 또는 사용자 prefs)
2. **카드 사용내역 XLSX/CSV 파서 우선순위**: 본 ADR §C-1 — Phase 6 에 포함? Phase 8+ 로 deferred?
   - 영향: 포함 시 Phase 6 일정 +1-2 주. Deferred 시 Upload UI 의 카드 사용내역 input 비활성화 필요.
3. **Templates editor 셀 직접 편집**: 본 ADR §B-7 — UI 가 명시 요구하지만 구현 비용 큼.
   - 후보 A: Phase 6 에 풀 구현 (cell PATCH + formula bar + status bar 모두)
   - 후보 B: Phase 6 은 read-only grid + 매핑 chips PATCH 만. 셀 편집은 Phase 8+
   - 후보 C: Phase 6 은 셀 값 PATCH 만 (style/border/병합/줌 deferred)
4. **시트 분석 휴리스틱 확장**: ADR-006 의 `_법인/_개인` 가정이 A사 양식 (`지출결의서`)에 안 맞음. Template Analyzer 갱신?
   - 후보 A: ADR-006 후속 ADR 작성 + 휴리스틱 확장 (A2 마커 + row 7 헤더만 검사, 시트명 suffix 무관)
   - 후보 B: Phase 6 진입과 별도로 Template Analyzer 확장 (Phase 5.5)
   - 후보 C: 양식별 분석 가능 여부를 시각화 ("매핑 필요" flag) — UI 의 "코스콤 외주 양식 · 매핑 필요" 동작
5. **Baseline "평소 처리 시간"**: Dashboard / Result 의 "절약된 시간" 계산 base.
   - 후보 A: 하드코드 (예: 거래당 15분 — 수동 입력 평균)
   - 후보 B: 사용자별 누적 평균 (history 누적 → personal baseline)
   - 후보 C: 전체 사용자 평균 (system-wide baseline)
6. **참석자 입력 방식**: TaggingForm 의 input 형식.
   - 후보 A: 자유 텍스트 (autocomplete 8 suggest)
   - 후보 B: team_group 멤버 선택 (그룹 단위 일괄 + 개별)
   - 후보 C: 양쪽 hybrid (autocomplete + team chip)
7. **영수증 파일명 규약**: UI 의 `IMG_2025_12_02_본가설렁탕.jpg` 형태 vs 백엔드의 uuid 권장 (CLAUDE.md §"업로드 3중 검증" — uuid4().hex+suffix).
   - 결정: **uuid 디스크 저장 + 원본명 metadata 컬럼** (보안 우선 — CLAUDE.md 충실). UI 표시는 metadata 의 원본명. **본 결정은 ADR-010 가 가정 — 사용자 확인만**.

## E. Phase 6 작업 범위 갱신 (최종)

본 검증 + 사용자 답 반영 후 phase-6-plan.md 의 작업 범위:

1. **synthesis/05 원본 Phase 6**: UploadGuard + FileManager + JobRunner + SSE
2. **Sessions API** (PATCH transactions, bulk-tag transactional, status enum, 처리 시간 메트릭)
3. **Templates API** (5.4 deferred + chip 매핑 PATCH + grid endpoint)
4. **Dashboard summary**
5. **ZIP bundler** (Phase 5 generators 확장)
6. **자동완성 endpoint 3종** (Cache-Control: max-age=300)
7. **GeneratedArtifact entity** (별도 테이블) + alembic 마이그레이션
8. **Session.status enum 3종** + alembic 마이그레이션
9. **Transaction.receipt_file_path** + Transaction.processing_*_at + Session.processing_*_at
10. **layout_pdf 파일명 보정** + `XlsxWriter` 사용자명 인자 추가
11. **§D-A 사용자 답 따라 추가 (1-2건 예상)**:
    - 카드 사용내역 XLSX/CSV 파서 (포함 시)
    - Templates 셀 편집 깊이 (Phase 6 포함 범위)
    - 시트 분석 휴리스틱 확장 (포함 시)

## F. 자료 일치율 / 보강 통계

- **PNG 5장 전수 시각 검증 완료**.
- 일치 항목: **8건** (§A).
- 보정 항목: **9건** (§B-1 ~ B-9).
- 신규 발견: **8건** (§C-1 ~ C-8).
- 사용자 답 반영: **5건** (§D-1 ~ D-5, 추가 결정 7건 §D-A 대기).
- **총 30 항목 검증** — 본 ADR 의 초안 추론은 핵심 골격 정확 (5 화면 + entity 매핑 + SSE), 세부 보정은 자료 기반으로 정밀.
