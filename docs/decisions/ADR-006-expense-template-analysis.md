---
id: ADR-006
title: 지출결의서 실 양식 분석 — Phase 5 TemplateAnalyzer 사전 자료
date: 2026-05-12
status: accepted
refs:
  - ADR-003 (real_templates fixture)
  - synthesis/04-design.md §"TemplateConfig"
  - synthesis/05 §"Phase 5"
note:
  - "원 사용자 명세의 ADR-005-expense-template-analysis 는 ADR-005 가 parser-returns-list 로
     점유되어 ADR-006 으로 시프트."
---

# 결정

Phase 5 진입 전 실 지출결의서 양식 3 장 분석 결과를 본 ADR 에 결정 사항으로 고정.
Phase 5 `TemplateAnalyzer` 가 자동 추출해야 할 항목 명세 + 양식 진화 흔적 + 한계 명시.

# 분석 대상

`tests/smoke/real_templates/` 의 3 장 (ADR-003 매핑):

| 영문명                       | 연/월   | 사용자  | 시트 수 | 데이터 row 수 | 합계 row |
| ---------------------------- | ------- | ------- | ------- | ------------- | -------- |
| `expense_2025_12_a.xlsx`     | 2025-12 | user-α  | 3       | 0~2 (빈 양식)  | 11       |
| `expense_2026_03_a.xlsx`     | 2026-03 | user-β  | 3       | ~25 (full)    | 36       |
| `expense_2026_03_b.xlsx`     | 2026-03 | user-γ  | ~25      |               | 27       |

> 본 ADR 본문에는 PII (실명·실 가맹점·실 금액·실 프로젝트) 일체 미기재.
> `<MERCHANT>`, `<PROJECT>`, `<EMPLOYEE>`, `<AMOUNT>` placeholder 만.

# 시트 구조

## 시트명 규약 (3 장 공통)

| 시트          | 패턴                            | 비고                                                      |
| ------------- | ------------------------------- | --------------------------------------------------------- |
| 법인          | `{YY.MM}_법인`                  | 법인카드 거래                                             |
| 개인          | `{YY.MM}_개인`                  | 개인카드 & 현금 거래                                      |
| 차량          | `{YY.MM}_차량`                  | 차량운행일지 — Phase 4 범위 외 (별도 양식)                |

`YY.MM` = 2 자리 연도 + 점 + 2 자리 월 (예: `25.12`, `26.03`).
Phase 4 의 `Transaction → ExpenseRecord` 매핑은 **법인 / 개인** 시트만 대상. 차량은 Phase 6+.

## 법인 / 개인 시트 — 공통 layout (3 장 모두 동일)

### 헤더 영역 (row 1~8)

| Row | 셀                  | 내용                                              |
| --- | ------------------- | ------------------------------------------------- |
| 2   | A2                  | "경비 사용 내역서" (제목)                         |
| 4   | A4                  | 회사명 (예: "주식회사 테라시스")                  |
| 4   | C4                  | "직원명 : <EMPLOYEE>"                             |
| 4   | I4 / J4             | "청구기간 :" / "YYYY/MM/DD~YYYY/MM/DD"            |
| 4   | M4 / N4             | "승인자:" / 승인자 명                              |
| 6   | A6                  | 법인 시트 = "사용카드 : 법인카드" / 개인 시트 = "사용카드 : 개인카드&현금" |
| 6   | C6                  | "카드번호 : <CARD>"                               |
| 7   | A7~N7               | 1차 헤더 (그룹) — 아래 매핑 참조                  |
| 8   | F8~N8               | 2차 헤더 (서브카테고리)                           |

### 1차 헤더 (row 7) — 컬럼 그룹

| 컬럼 letter | 헤더            | 카테고리 그룹             |
| ----------- | --------------- | ------------------------- |
| A           | 일    자        | 거래일                    |
| B           | 거래처 / 프로젝트명 | 가맹점·프로젝트         |
| E           | 합    계        | 행별 SUM                  |
| F~H         | 여비교통비       | (sub: 항공료·버스택시·숙박비) |
| I~J         | 차량유지비       | (sub: 유류대·주차통행료)  |
| L           | 식대            | 식대                      |
| M           | 접대비          | 접대비                    |
| N           | 기타비용        | 기타                      |

### 2차 헤더 (row 8) — 서브 카테고리

| 컬럼 letter | 헤더             | 매핑 대상                     |
| ----------- | ---------------- | ----------------------------- |
| F           | 항공료            | meal_type=N/A, 여비교통비-항공 |
| G           | 버스,택시 (또는 "버스,택시,대리") | 여비교통비-육상   |
| H           | 숙박비            | 여비교통비-숙박                |
| I           | 유류대            | 차량유지비-주유                |
| J           | 주차,통행료       | 차량유지비-주차/통행           |
| K           | (공백)            | 차량유지비 spacer (예약)       |

### 데이터 영역 (row 9 ~ data_end_row)

| 컬럼 | 셀 형식                  | 비고                                          |
| ---- | ------------------------ | --------------------------------------------- |
| A    | 일자 (string `YYYY.MM.DD` 또는 datetime `YYYY-MM-DD HH:MM:SS`) | **양식 진화 흔적** — 25.12 는 text, 26.03 는 datetime |
| B    | "<MERCHANT> / <PROJECT>" 또는 "<MERCHANT>" 단독 | 한 셀에 슬래시 구분 또는 B+C+D 분리           |
| C/D  | "/" + 프로젝트명          | B 가 단독일 때 C 는 "/", D 는 프로젝트명      |
| E    | `=SUM(Fn:Nn)`             | 행별 합계 수식 (보호 대상)                    |
| F~N  | 정수 금액 (해당 카테고리 1 셀에만 입력) | 카테고리 1 컬럼에만 입력, 나머지 빈 셀 |

### 합계 영역 (sum_row)

| 셀                | 수식                            | 비고                            |
| ----------------- | ------------------------------- | ------------------------------- |
| A{sum_row}        | "합    계"                      | 라벨                            |
| E{sum_row}        | `=SUM(F{sum_row}:O{sum_row})`   | **O 컬럼 포함** — 미래 확장 대비 |
| F{sum_row}        | `=SUM(F9:F{data_end})`          | 세로 SUM                        |
| G{sum_row}        | `=SUM(G9:G{data_end})`          | 세로 SUM                        |
| ... N{sum_row}    | 동일 패턴                        | 모든 카테고리 컬럼               |

### sum_row 위치 휴리스틱

- `data_end_row + 1` (gap 없음, 26.03_b)
- `data_end_row + 2` (gap 1 row, 26.03_a)
- 빈 양식: data row 0 → sum_row=11 (헤더 끝 직후 row 1)

# 3 장 간 공통점 vs 차이점

## 공통점 (양식 안정 영역)

- 시트 명명 규약 `{YY.MM}_{법인|개인|차량}`
- 헤더 row 2/4/6/7/8 위치 고정
- 데이터 시작 row 9 고정
- 컬럼 매핑 A·B·E·F·G·H·I·J·L·M·N 고정
- 행별 SUM 수식 형태 `=SUM(F:N)` (또는 SUM(F:O))
- sum_row 의 세로 SUM 수식 형태 `=SUM(F9:F{data_end})`

## 차이점 (양식 진화 흔적 — TemplateAnalyzer 가 동적 추출 필수)

| 영역                  | 25.12             | 26.03_a            | 26.03_b            | 비고                          |
| --------------------- | ----------------- | ------------------ | ------------------ | ----------------------------- |
| A 컬럼 일자 형식      | text `YYYY.MM.DD` | datetime           | datetime           | row 단위 type 검사로 자동화   |
| B/C/D 거래처 분리     | B 단독            | B 단독             | B + C("/") + D     | 셀 병합 유무 검사 필요        |
| G 헤더 sub-label      | "버스,택시"        | "버스,택시,대리"    | "버스,택시"         | 카테고리 분류 시 fuzzy match  |
| sum_row gap          | 0                 | 1                  | 0                  | 합계 라벨 검색으로 자동 탐지   |
| data_end_row          | 가변               | 가변                | 가변                | sum_row - 1 또는 sum_row - 2  |
| 청구기간 (J4)         | 명시               | 명시                | **누락 가능**       | optional 처리                  |

# Phase 5 TemplateAnalyzer 명세

`services/templates/template_analyzer.py` (신규) 가 다음을 자동 추출:

```python
@dataclass(frozen=True)
class AnalyzedTemplate:
    sheets: dict[str, AnalyzedSheet]              # 시트명 → 메타

@dataclass(frozen=True)
class AnalyzedSheet:
    sheet_kind: Literal["법인", "개인", "차량"]   # 시트명 suffix 로 결정
    header_rows: tuple[int, int]                  # (1차, 2차)
    data_start_row: int                           # 항상 9
    data_end_row: int                             # 합계 라벨 row - 1 또는 -2
    sum_row: int                                  # A 컬럼에 "합" 포함된 마지막 row
    column_map: dict[str, str]                    # "일자"→"A", "합계"→"E", "식대"→"L", ...
    formula_cells: dict[str, str]                 # "E11"→"=SUM(F11:O11)" 식 영속 수식
    formula_cols: tuple[str, ...]                 # ("E", "F", ..., "N") — 보호 대상 letter
```

추출 알고리즘 (휴리스틱):
1. `sheet.title.split("_")[-1]` 로 sheet_kind 결정.
2. A2 가 "경비 사용 내역서" 인 시트만 분석 대상 (차량은 제외 — Phase 6+).
3. row 7 의 각 셀 텍스트 → column_map. row 8 의 sub-header 도 병합 매핑.
4. A 컬럼을 row 9 부터 스캔 — 첫 "합" 포함 셀 = sum_row.
5. data_end_row = sum_row - 1 (값 없으면 - 2 시도, 그 후 - 3...).
6. formula_cells = sum_row 의 모든 셀 + (E9..E{sum_row-1}) 의 모든 셀에서 `=` 시작 값 모두 수집.
7. formula_cols = formula_cells 가 한 번이라도 등장한 column letter 집합.

# 영향

- Phase 5 진입 시 `TemplateAnalyzer` 가 본 결정에 맞춰 구현.
- 04-design.md §"TemplateConfig" 의 정적 정의는 본 ADR 의 동적 추출 명세로 대체.
  (TemplateAnalyzer 가 `TemplateConfig` 인스턴스 생성 → 등록 시 1 회 영속.)
- 양식 변경 흔적이 5 건 이상 누적되면 휴리스틱 정확도가 흔들림 → 본 ADR 갱신 + 등록 단계
  사용자 확인 UI 추가 검토.

# 통합 테스트 스켈레톤

`tests/integration/test_real_template_round_trip.py` 에 `@pytest.mark.skip` 로 1 케이스
예약 (Phase 5 TemplateAnalyzer 구현 후 활성화).

# 한계

1. **차량 시트 미지원** — Phase 4/5 범위 외. 별도 양식이라 본 ADR 의 column_map 적용 불가.
2. **항공료 (F 컬럼) 실 데이터 0 건** — Phase 5 후 첫 실 항공료 사례 확보 시 대조 검증 필수.
3. **3 장 표본만 분석** — 더 많은 user 양식 확보 시 휴리스틱 정밀화 필요 (특히 row 4 의 셀
   병합 패턴 다양성).
