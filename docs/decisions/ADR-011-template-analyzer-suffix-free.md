---
id: ADR-011
title: Template Analyzer 시트명 suffix 가정 제거 + "매핑 필요" flag 도입
date: 2026-05-12
status: accepted
supersedes:
  - ADR-006 의 "시트명 suffix '_법인'/'_개인' 강제" 가정 (Field mode 양식 미지원 결함)
refs:
  - ADR-006 (지출결의서 실 양식 분석)
  - ADR-010 의 자료 검증 결과 B-6, C-6, 추천 4 (시트 분석 휴리스틱 확장)
  - tests/smoke/real_templates/expense_2025_12_a.xlsx (Category mode 양식)
  - v4/ui_reference_1/ Templates 캡처 (Field mode 양식 = "지출결의서/증빙요약/월별집계" 시트)
---

# 결정

`app/services/templates/analyzer.py` 의 `_is_target_sheet` 휴리스틱 갱신:

- 기존: 시트명 suffix 가 `_법인` 또는 `_개인` 일 때만 분석 대상.
- 신규: 시트명 suffix 무관. A2 셀 마커 ("경비 사용 내역서" 등 화이트리스트) + 헤더 row 7 의 한글 keyword 보유 여부로 판정. 차량 시트는 명시적 stop word ("차량/주행/운행일지") 로만 skip.

추가로 SheetConfig 에 신규 필드 `analyzable: bool` 도입 — 자동 분석 성공 / 사용자 수동 매핑 대기 구분. Template entity 의 `mapping_status` 컬럼 (mapped / needs_mapping) 도 이 결과로 결정.

# 컨텍스트 — 두 양식 종류 공존

ADR-006 의 기존 가정 (시트명이 `{YY.MM}_법인` 또는 `{YY.MM}_개인` 형식) 은 회사별 양식 1 유형 (Category mode, 카테고리별 별도 컬럼) 에 한정. ADR-010 자료 검증으로 UI 의 A사 파견용 양식이 다른 유형 (Field mode, 단일 row = 1 거래) 임이 확인됨.

| 양식 유형 | 시트 명 (실 자료) | 컬럼 구조 | mode |
| --- | --- | --- | --- |
| Category | `25.12_법인`, `26.03_개인` (ADR-006 실 3 장) | 식대/접대비/기타비용 별도 컬럼 | category 또는 hybrid |
| Field | `지출결의서`, `증빙요약`, `월별집계` (UI A사 양식) | 연번/거래일/거래처/프로젝트/용도/인원/금액/동석자/비고 | field |

기존 휴리스틱은 Field mode 시트 (suffix 미일치) 를 모두 reject — UI 의 "A사 파견용 양식" 등록 시 분석 결과 0 시트 → TemplateAnalysisError. 사용자 등록 자체가 불가.

# 신규 휴리스틱

## 1. 시트 분석 대상 판정 (`_is_target_sheet` 교체)

```python
_ANALYZABLE_A2_MARKERS = ("경비 사용 내역서", "지출결의서", "지출 결의서")
_STOP_SHEET_KEYWORDS = ("차량", "주행", "운행일지")
_HEADER_KEYWORDS_ROW7 = (
    # Field mode 핵심 컬럼 헤더
    "거래일", "거래처", "프로젝트", "용도", "인원", "금액", "동석자", "비고",
    # Category mode 핵심 컬럼 헤더
    "여비교통비", "차량유지비", "식대", "접대비", "기타비용", "합계",
    "일자",  # Category mode 'A=일자' or '거래일' 양쪽
    "거래처 / 프로젝트명",  # ADR-006 의 B7 텍스트 그대로
)
```

판정 알고리즘:

1. `ws.title` 에 `_STOP_SHEET_KEYWORDS` 중 하나 포함 → 즉시 skip (차량 시트 제외).
2. A2 cell value 가 `_ANALYZABLE_A2_MARKERS` 중 하나 포함 → 후보 시트.
3. row 7 의 cell value 중 `_HEADER_KEYWORDS_ROW7` 매칭 카운트 ≥ 2 → 분석 가능 시트 확정.
4. 위 조건 미충족 시 — A2 마커는 있지만 헤더 패턴 미일치 → `SheetConfig(analyzable=False, sheet_name=ws.title)` 반환 (수동 매핑 필요 placeholder).

## 2. SheetConfig 신규 필드

```python
class SheetConfig(BaseModel):
    # ... 기존 필드 ...
    analyzable: bool = True  # False = 자동 분석 실패, 사용자 수동 매핑 대기.
```

기본값 True 로 회귀 안전. analyzer 가 명시적으로 False 설정한 시트만 수동 매핑 대상.

## 3. Template entity 의 mapping_status 컬럼

Phase 6 alembic 마이그레이션에서 `Template.mapping_status: Literal["mapped", "needs_mapping"]` 신규. analyzer 결과의 모든 시트가 `analyzable=True` 이면 `mapped`, 한 시트라도 `False` 이면 `needs_mapping`.

UI 의 Templates sidebar 가 "매핑 필요" flag 색상으로 표시 (UI 캡처의 코스콤 양식 동작).

## 4. sheet_name 의미 변경 (호환)

기존: `SheetConfig.sheet_name` 이 sheet_kind ("법인" / "개인") 만 저장.
신규: 시트 title 그대로 (UI 의 "지출결의서" / "증빙요약" / ADR-006 의 "법인" 모두 동일 슬롯).

XlsxWriter 와 write_workbook 의 `kind_to_sheet` 매핑이 직접 영향 — Phase 6 시작 시 호환 검토 후 보정 (테스트 회귀 0 보장).

# 보안 분석

- 시트명 / A2 / row 7 모두 사용자 업로드 양식의 내부 data — `UploadGuard` 통과 후 검사이므로 외부 입력 신뢰 문제 없음.
- `_HEADER_KEYWORDS_ROW7` 매칭 카운트 임계 (≥ 2) — 단일 우연 매치로 잘못된 시트가 분석 대상 되지 않게 함.
- "차량/주행/운행일지" stop word — 운행일지 시트 (별도 양식 가정) 가 결의서 매핑 받지 않도록.

# 영향

1. Phase 5 회귀: `tests/integration/test_real_template_round_trip.py` 3 케이스 (Category mode 실 3 장) — 기존 분석 결과 유지 (suffix `_법인`/`_개인` 이 신규 휴리스틱에서도 분석 가능). 회귀 0 기대.
2. UI 양식 (Field mode "지출결의서" 시트) 신규 분석 가능 — 등록 가능.
3. 분석 실패 시트 발견 시 `SheetConfig(analyzable=False, sheet_name=ws.title)` 으로 보존 — UI 가 수동 매핑 UI 노출.
4. `XlsxWriter.write_workbook` 의 `kind_to_sheet` 매핑이 시트 title 그대로 키 사용으로 보정 필요 — `SheetConfig.sheet_name` 이 시트 title 이므로 자연 매핑.

# 단위 테스트 (TDD 추가 예정)

`tests/unit/test_template_analyzer.py` 에 신규 케이스:

- `test_field_mode_sheet_without_suffix_analyzable()` — UI 의 "지출결의서" 시트 모사 (synthetic_xlsx 보강) → analyzable=True
- `test_unrecognized_sheet_marked_needs_mapping()` — A2 마커는 있지만 row 7 헤더 미일치 → analyzable=False
- `test_stop_word_sheet_skipped()` — 시트명에 "차량" 포함 → 결과 dict 에서 제외
- `test_mapping_status_aggregates_to_needs_mapping()` — 1 시트라도 analyzable=False 면 Template.mapping_status = needs_mapping

기존 7 케이스 회귀 0 보장 — `tests/fixtures/synthetic_xlsx.py` 의 `make_template` 이 "법인" / "개인" 시트명 사용하지만 신규 휴리스틱이 A2 + row 7 패턴으로 매칭하므로 영향 없음.

# 대안 폐기

| 대안 | 폐기 사유 |
| --- | --- |
| 양식 유형별 별도 analyzer (FieldAnalyzer / CategoryAnalyzer 분리) | 코드 중복 + 라우팅 복잡 + 사용자 등록 시점 유형 판정 책임이 어느 쪽? 단일 analyzer 가 mode 자동 결정하는 현 구조가 정합. |
| 시트명 정규식 화이트리스트 확장 ("지출결의서" 추가) | UI 등록 시점에 시트명을 사용자가 자유 변경 가능 — 화이트리스트가 영원히 누락 위험. A2 + row 7 패턴 검사가 본질. |
| Template 등록 시 사용자가 시트별 mode 직접 선택 | 단순 등록 UX 손상. 자동 판정 후 실패만 수동 매핑이 자연. |

# 후속

1. Phase 6 진입 시 단위 테스트 신규 4 케이스 추가 + 휴리스틱 교체.
2. `Template.mapping_status` alembic 마이그레이션 (Phase 6 의 일부).
3. UI Templates sidebar 의 "매핑 필요" flag → 본 ADR 의 `mapping_status="needs_mapping"` 직접 매핑.
4. ADR-010 자료 검증 결과의 추천 4번 (시트 분석 휴리스틱 확장) 해소.
