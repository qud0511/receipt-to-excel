# 설계 — templates 라우터의 openpyxl 의존을 services 뒤로 이동

> 작성: 2026-05-15 · 유형: 구조 부채 청산 (동작 보존 리팩터, 신기능 아님)
> 근거: CLAUDE.md "코드 구조" — 외부 의존성은 services/* 인터페이스 뒤에만,
> api/domain 에서 openpyxl/httpx 직접 import 금지. P8.12 에서 발견·보류된 부채.

## 1. 문제

`app/api/routes/templates.py` 가 openpyxl 을 직접 import·사용 (2 엔드포인트):

- `get_template_grid` (GET /templates/{id}/grid) L221: `load_workbook(..., data_only=False)` → 시트 순회하며 GridCell/GridSheetView 구성.
- `patch_template_cells` (PATCH /templates/{id}/cells) L275: `load_workbook(...)` → 시트별 셀 값 갱신 → `wb.save` → 파일 덮어쓰기.

이는 CLAUDE.md 구조 규칙 위반. P8.12 에서 import-linter 도입 시 openpyxl/httpx 금지 contract 를 게이트 약화 없이 보류하고, 별도 리팩터 후 활성화하기로 함.

기존 올바른 패턴은 이미 존재: `app/services/templates/analyzer.py`, `injector.py` 가 services 내부에서 openpyxl 사용.

## 2. 목표 / 비목표

- 목표: openpyxl 호출을 `app/services/templates/` 뒤로 이동. **HTTP 응답·동작 완전 동일**. import-linter openpyxl/httpx 금지 contract 활성화.
- 비목표: 기능 추가/변경, 정식 인터페이스 추상화(8.4/8.5 에서), 다른 라우터 리팩터, 셀 편집 UX 개선.

## 3. 설계 (A1 — 동작 보존 최소 이동)

신규 모듈 `app/services/templates/grid_io.py` (analyzer.py/injector.py 와 동일 위치·관례). openpyxl 은 이 파일 안에만 존재.

services 가 `app.schemas` 에 의존하지 않도록(CLAUDE.md 도메인-스키마 분리) 평범한 typed 구조만 반환, 라우터가 스키마로 매핑:

```
@dataclass(frozen=True, slots=True)
class RawCell:   row: int; col: int; value: str | int | float | None; is_formula: bool
@dataclass(frozen=True, slots=True)
class RawSheet:  cells: list[RawCell]; max_row: int; max_col: int

class TemplateSheetNotFoundError(Exception):
    # analyzer.TemplateAnalysisError 와 동일한 services 예외 패턴.
    def __init__(self, sheet: str) -> None: ...

def read_grid(content: bytes) -> dict[str, RawSheet]
def apply_cell_patches(
    content: bytes,
    patches: Sequence[tuple[str, int, int, str | int | float | None]],
) -> tuple[bytes, int]
```

- `read_grid`: 현 L221~250 의 openpyxl 추출 로직을 그대로 이동. is_formula 판정·값 형변환 규칙 동일.
- `apply_cell_patches`: 현 L275~289 로직 이동. patches 는 `(sheet, row, col, value)` 튜플 시퀀스(스키마 비의존). 시트 부재 시 `TemplateSheetNotFoundError(sheet)` raise. 반환 `(new_bytes, updated_count)`.

### 라우터 변경 (`templates.py`)

- L31 `from openpyxl import load_workbook` + 부채 주석 제거 → `from app.services.templates.grid_io import RawSheet, TemplateSheetNotFoundError, apply_cell_patches, read_grid`.
- `get_template_grid`: 파일 존재 검사(404) 유지 → `read_grid(p.read_bytes())` 호출 → RawSheet→GridSheetView/GridCell 매핑하여 GridResponse 반환. HTTP 관심사(auth/DB/404)는 라우터 잔류.
- `patch_template_cells`: 404 검사 유지 → body.cells 를 `(sheet,row,col,value)` 튜플로 변환 → `apply_cell_patches` 호출 → `TemplateSheetNotFoundError` catch 시 기존과 동일 `HTTP 422` + 동일 detail 문자열(`f"sheet '{sheet}' not found"`) → 반환 bytes 를 파일에 write, `{"ok": True, "updated_count": n}` 동일.

io / Path / load_workbook 등 미사용 import 정리. 동작·응답 스키마·상태코드·detail 문자열 불변.

## 4. 에러 처리 (행위 보존 핵심)

| 상황 | 현재 | 변경 후 |
|---|---|---|
| 템플릿 파일 부재 | 라우터 404 "template file missing" | 동일 (라우터 잔류) |
| PATCH 시트 부재 | 라우터 루프 내 422 `sheet '{x}' not found` | 서비스가 `TemplateSheetNotFoundError` → 라우터가 동일 422·동일 detail |
| 정상 grid/patch | 200 + 동일 바디 | 동일 |

services 는 fastapi 의존 안 함(HTTPException 라우터 전담). 422 의 부분 적용 방지: 현재 코드는 잘못된 시트 만나면 그 전까지 메모리 wb 만 수정하고 파일 저장 안 함(save 는 루프 후) → 디스크 무변경. 신설계도 동일 — 검증을 저장 이전 일괄 수행하므로 부분 기록 없음.

## 5. 테스트 (3중 안전망 — 실데이터 포함)

1. **회귀 오라클(합성, 무변경 통과)**: 기존 `tests/integration/test_templates_api.py` (grid/cells 엔드포인트) + 관련 unit 전부 그대로 GREEN. 동작 변하면 즉시 적발.
2. **신규 단위** `tests/unit/test_grid_io.py`: 합성 xlsx(`tests/fixtures/synthetic_xlsx.py` 패턴)로 `read_grid`(셀/수식/max_row·col), `apply_cell_patches`(값 갱신·updated_count·round-trip 후 재읽기 일치), `TemplateSheetNotFoundError`(미존재 시트) 직접 검증.
3. **실데이터 회귀** `tests/integration/test_real_template_round_trip.py` 확장 (기존 파일·skip-if-absent 관례 그대로): `tests/smoke/real_templates/{expense_2025_12_a,expense_2026_03_a,expense_2026_03_b}.xlsx` 3장을 `read_grid` → 시트별 cells 비어있지 않음·max_row/col>0 확인 → 안전한 no-op 성격 patch(기존 셀에 동일 값 재기록) `apply_cell_patches` → 반환 bytes 재-`read_grid` → 셀 값/is_formula/시트 집합 보존 단언. 실파일 부재 시 skip.

> PII 보호: 실 xlsx 내용은 사람이 열지 않음. 테스트는 구조 불변식만 단언(가맹점명·금액 값 자체를 로그/단언하지 않음). CLAUDE.md fixture 분리·PII 로깅 금지 준수.

## 6. 검증 게이트 (이 세션 내 완료)

`uv run` 으로: ruff check·format / mypy --strict / **import-linter(openpyxl·httpx 금지 contract 신규 활성화 포함)** / pytest -m "not real_pdf"(합성 전체) / 실데이터 round-trip 로컬 실행 / pip-audit. 전부 GREEN 확인 후 커밋. 커밋 태그 `[P8.12]` (8.12 의 import-linter 풀 게이트 완성).

## 7. 영향 / 롤백

- 단일 라우터 + 신규 services 1파일 + 테스트. 스키마·DB·마이그레이션·UI 무변경(6요소 스키마 진화 아님).
- import-linter contract 추가는 `pyproject.toml` [tool.importlinter] 에 forbidden contract 1개 추가.
- 롤백: 커밋 revert 로 완전 가역(외부 상태 변경 없음).
