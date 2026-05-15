# openpyxl→services 리팩터 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** templates 라우터의 openpyxl 직접 의존을 `app/services/templates/grid_io.py` 뒤로 이동(동작 보존)하고 import-linter openpyxl/httpx 금지 contract 를 활성화한다.

**Architecture:** 신규 services 모듈이 openpyxl 호출을 전담하고 평범한 dataclass(`RawCell`/`RawSheet`)·서비스 예외(`TemplateSheetNotFoundError`)만 노출. 라우터는 HTTP 관심사(auth/DB/404/422)만 유지하며 Raw* ↔ pydantic 스키마 매핑. 응답·상태코드·detail 문자열 불변.

**Tech Stack:** Python 3.12, FastAPI, openpyxl(services 한정, mypy `openpyxl.*` ignore_missing_imports), pytest, import-linter, uv.

---

## File Structure

- Create: `app/services/templates/grid_io.py` — openpyxl 워크북 grid 읽기 + 셀 패치 적용. 책임 1개(템플릿 워크북 IO). `analyzer.py`/`injector.py` 와 동일 패키지·관례.
- Create: `tests/unit/test_grid_io.py` — grid_io 단위 테스트(합성 인메모리 xlsx).
- Modify: `app/api/routes/templates.py` — openpyxl import 제거, grid_io 사용으로 `get_template_grid`/`patch_template_cells` 재작성.
- Modify: `tests/integration/test_real_template_round_trip.py` — 실 양식 3장 grid_io round-trip 테스트 추가.
- Modify: `pyproject.toml` — `[tool.importlinter]` 에 openpyxl/httpx forbidden contract 추가 + 보류 주석 제거.
- 회귀 오라클(무변경): `tests/integration/test_templates_api.py` — 기존 grid/cells 테스트가 그대로 통과해야 함.

---

## Task 1: grid_io 모듈 — read_grid

**Files:**
- Create: `app/services/templates/grid_io.py`
- Test: `tests/unit/test_grid_io.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/unit/test_grid_io.py`:

```python
"""grid_io 단위 테스트 — openpyxl 워크북 IO (P8.12 리팩터)."""

from __future__ import annotations

import io

import pytest
from openpyxl import Workbook

from app.services.templates.grid_io import (
    RawCell,
    RawSheet,
    TemplateSheetNotFoundError,
    apply_cell_patches,
    read_grid,
)


def _wb_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws["A1"] = "name"
    ws["B1"] = 10
    ws["C1"] = "=B1+1"  # 수식
    ws2 = wb.create_sheet("Sheet2")
    ws2["A1"] = 3.5
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_read_grid_extracts_cells_and_detects_formula() -> None:
    sheets = read_grid(_wb_bytes())

    assert set(sheets) == {"Sheet1", "Sheet2"}
    s1 = sheets["Sheet1"]
    assert isinstance(s1, RawSheet)
    by_pos = {(c.row, c.col): c for c in s1.cells}
    assert by_pos[(1, 1)] == RawCell(row=1, col=1, value="name", is_formula=False)
    assert by_pos[(1, 2)] == RawCell(row=1, col=2, value=10, is_formula=False)
    assert by_pos[(1, 3)].value == "=B1+1"
    assert by_pos[(1, 3)].is_formula is True
    assert s1.max_row == 1
    assert s1.max_col == 3
    assert sheets["Sheet2"].cells[0] == RawCell(row=1, col=1, value=3.5, is_formula=False)


def test_read_grid_skips_none_cells() -> None:
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "x"
    ws["C1"] = "y"  # B1 은 None — 건너뜀
    buf = io.BytesIO()
    wb.save(buf)
    sheets = read_grid(buf.getvalue())
    positions = {(c.row, c.col) for c in next(iter(sheets.values())).cells}
    assert (1, 2) not in positions
    assert positions == {(1, 1), (1, 3)}
```

- [ ] **Step 2: 실패 확인**

Run: `cd /bj-dev/v4 && uv run pytest tests/unit/test_grid_io.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.templates.grid_io'`

- [ ] **Step 3: 최소 구현**

`app/services/templates/grid_io.py`:

```python
"""템플릿 워크북 IO — openpyxl 전담(P8.12: api 에서 openpyxl 직접 import 금지).

라우터는 RawCell/RawSheet 와 TemplateSheetNotFoundError 만 사용 — openpyxl·
pydantic 스키마는 본 모듈 경계를 넘지 않음(CLAUDE.md 코드 구조/도메인-스키마 분리).
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from dataclasses import dataclass

from openpyxl import load_workbook


@dataclass(frozen=True, slots=True)
class RawCell:
    row: int
    col: int  # 1-based
    value: str | int | float | None
    is_formula: bool


@dataclass(frozen=True, slots=True)
class RawSheet:
    cells: list[RawCell]
    max_row: int
    max_col: int


class TemplateSheetNotFoundError(ValueError):
    """패치 대상 시트가 워크북에 없음. analyzer.TemplateAnalysisError 와 동일 패턴."""

    def __init__(self, sheet: str) -> None:
        self.sheet = sheet
        super().__init__(f"sheet '{sheet}' not found")


def read_grid(content: bytes) -> dict[str, RawSheet]:
    """워크북 bytes → 시트별 비어있지 않은 셀 grid. 수식은 data_only=False 로 보존."""
    wb = load_workbook(io.BytesIO(content), data_only=False)
    sheets: dict[str, RawSheet] = {}
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        cells: list[RawCell] = []
        for row_idx in range(1, ws.max_row + 1):
            for col_idx in range(1, ws.max_column + 1):
                val = ws.cell(row=row_idx, column=col_idx).value
                if val is None:
                    continue
                is_formula = isinstance(val, str) and val.startswith("=")
                if isinstance(val, int | float | str):
                    cell_val: str | int | float | None = val
                else:
                    cell_val = str(val)
                cells.append(
                    RawCell(
                        row=row_idx,
                        col=col_idx,
                        value=cell_val,
                        is_formula=is_formula,
                    )
                )
        sheets[sheet_name] = RawSheet(
            cells=cells,
            max_row=ws.max_row,
            max_col=ws.max_column,
        )
    return sheets
```

- [ ] **Step 4: 통과 확인**

Run: `cd /bj-dev/v4 && uv run pytest tests/unit/test_grid_io.py -q`
Expected: 2 passed (apply_cell_patches import 는 Task 2 전까지 미사용이나 동일 모듈에 정의 예정 — Step 1 테스트의 import 가 실패하면 Task 2 의 함수도 같은 커밋 범위. 본 Task 는 read_grid 2 테스트만 실행: `-k read_grid`)

Run (정확): `cd /bj-dev/v4 && uv run pytest tests/unit/test_grid_io.py -k read_grid -q`
Expected: 2 passed

- [ ] **Step 5: 커밋**

```bash
cd /bj-dev/v4 && git add app/services/templates/grid_io.py tests/unit/test_grid_io.py && git commit -m "$(cat <<'EOF'
[P8.12] feat: grid_io.read_grid — 템플릿 워크북 grid 읽기 services 이동

openpyxl 워크북 → RawSheet/RawCell. templates.py 의 동작 보존 이동 1/2.

Refs: docs/superpowers/specs/2026-05-15-openpyxl-services-refactor-design.md
EOF
)"
```

---

## Task 2: grid_io 모듈 — apply_cell_patches

**Files:**
- Modify: `app/services/templates/grid_io.py`
- Test: `tests/unit/test_grid_io.py` (Task 1 에서 이미 import 선언됨)

- [ ] **Step 1: 실패 테스트 추가**

`tests/unit/test_grid_io.py` 끝에 추가:

```python
def test_apply_cell_patches_updates_and_roundtrips() -> None:
    new_bytes, count = apply_cell_patches(
        _wb_bytes(),
        [("Sheet1", 1, 1, "renamed"), ("Sheet2", 1, 1, 9.0)],
    )
    assert count == 2
    sheets = read_grid(new_bytes)
    s1 = {(c.row, c.col): c.value for c in sheets["Sheet1"].cells}
    assert s1[(1, 1)] == "renamed"
    assert s1[(1, 3)] == "=B1+1"  # 미패치 셀·수식 보존
    s2 = {(c.row, c.col): c.value for c in sheets["Sheet2"].cells}
    assert s2[(1, 1)] == 9.0


def test_apply_cell_patches_unknown_sheet_raises() -> None:
    with pytest.raises(TemplateSheetNotFoundError) as ei:
        apply_cell_patches(_wb_bytes(), [("NoSuch", 1, 1, "x")])
    assert ei.value.sheet == "NoSuch"
    assert str(ei.value) == "sheet 'NoSuch' not found"
```

- [ ] **Step 2: 실패 확인**

Run: `cd /bj-dev/v4 && uv run pytest tests/unit/test_grid_io.py -k apply_cell_patches -q`
Expected: FAIL — `ImportError: cannot import name 'apply_cell_patches'` 또는 AttributeError

- [ ] **Step 3: 최소 구현**

`app/services/templates/grid_io.py` 끝(read_grid 아래)에 추가:

```python
def apply_cell_patches(
    content: bytes,
    patches: Sequence[tuple[str, int, int, str | int | float | None]],
) -> tuple[bytes, int]:
    """(sheet,row,col,value) 패치 일괄 적용 → (새 워크북 bytes, 갱신 수).

    시트 부재 시 TemplateSheetNotFoundError. 저장은 전체 검증 통과 후 1회 —
    부분 기록 없음(기존 라우터 동작과 동일: 실패 시 디스크 무변경).
    """
    wb = load_workbook(io.BytesIO(content))
    updated = 0
    for sheet, row, col, value in patches:
        if sheet not in wb.sheetnames:
            raise TemplateSheetNotFoundError(sheet)
        ws = wb[sheet]
        ws.cell(row=row, column=col).value = value
        updated += 1
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), updated
```

- [ ] **Step 4: 통과 확인**

Run: `cd /bj-dev/v4 && uv run pytest tests/unit/test_grid_io.py -q`
Expected: 4 passed

- [ ] **Step 5: 타입·린트 확인**

Run: `cd /bj-dev/v4 && uv run mypy --strict app/services/templates/grid_io.py && uv run ruff check app/services/templates/grid_io.py tests/unit/test_grid_io.py && uv run ruff format --check app/services/templates/grid_io.py tests/unit/test_grid_io.py`
Expected: mypy Success / ruff All checks passed / format already formatted (불일치 시 `uv run ruff format <file>` 후 재확인)

- [ ] **Step 6: 커밋**

```bash
cd /bj-dev/v4 && git add app/services/templates/grid_io.py tests/unit/test_grid_io.py && git commit -m "$(cat <<'EOF'
[P8.12] feat: grid_io.apply_cell_patches — 셀 패치 적용 services 이동

(sheet,row,col,value) → 새 워크북 bytes. 시트 부재 시
TemplateSheetNotFoundError. 동작 보존 이동 2/2.

Refs: docs/superpowers/specs/2026-05-15-openpyxl-services-refactor-design.md
EOF
)"
```

---

## Task 3: templates.py 라우터 — grid_io 사용으로 재작성 (동작 보존)

**Files:**
- Modify: `app/api/routes/templates.py` (import 영역 + `get_template_grid` L201-250 + `patch_template_cells` L253-290)
- 회귀 오라클(무변경): `tests/integration/test_templates_api.py`

- [ ] **Step 1: 회귀 오라클 사전 GREEN 확인 (변경 전 기준선)**

Run: `cd /bj-dev/v4 && uv run pytest tests/integration/test_templates_api.py -q`
Expected: all passed (변경 전 통과 카운트 기록 — 변경 후 동일해야 함)

- [ ] **Step 2: import 영역 수정**

`app/api/routes/templates.py`:

제거 — 현재 L26-31 의 다음 블록(빈 줄·부채 주석 3줄·openpyxl import):

```python
from fastapi.responses import FileResponse

# 부채(P8.12 발견): CLAUDE.md "외부 의존성은 services/* 뒤에만 — api 에서 openpyxl
# 직접 import 금지" 위반. import-linter openpyxl-forbidden contract 는 본 라인을
# services 인터페이스 뒤로 옮기는 별도 sub-phase 리팩터 후 활성화 예정.
from openpyxl import load_workbook
from sqlalchemy.ext.asyncio import AsyncSession
```

→ 다음으로 치환:

```python
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
```

`import io` (현 L11) 제거 — 본 리팩터 후 templates.py 에서 io 미사용. (`Path` 는 파일 존재 검사에 계속 사용 — 유지.)

`app.services.templates.analyzer` import 줄 아래에 추가:

```python
from app.services.templates.grid_io import (
    RawSheet,
    TemplateSheetNotFoundError,
    apply_cell_patches,
    read_grid,
)
```

- [ ] **Step 3: get_template_grid 본문 교체**

현 L221-250 (`wb = load_workbook(...)` 부터 `return GridResponse(sheets=sheets)` 까지) 를 아래로 치환(파일 존재 404 검사 L215-220 은 유지):

```python
    raw: dict[str, RawSheet] = read_grid(p.read_bytes())
    sheets: dict[str, GridSheetView] = {
        name: GridSheetView(
            sheet_name=name,
            cells=[
                GridCell(
                    row=c.row,
                    col=c.col,
                    value=c.value,
                    is_formula=c.is_formula,
                )
                for c in rs.cells
            ],
            max_row=rs.max_row,
            max_col=rs.max_col,
        )
        for name, rs in raw.items()
    }
    return GridResponse(sheets=sheets)
```

- [ ] **Step 4: patch_template_cells 본문 교체**

현 L275-290 (`wb = load_workbook(...)` 부터 `return {"ok": True, "updated_count": updated}` 까지) 를 아래로 치환(404 검사 L268-273 유지):

```python
    try:
        new_bytes, updated = apply_cell_patches(
            p.read_bytes(),
            [(c.sheet, c.row, c.col, c.value) for c in body.cells],
        )
    except TemplateSheetNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        ) from e
    p.write_bytes(new_bytes)
    return {"ok": True, "updated_count": updated}
```

> 동작 보존 주의: 기존 detail 은 `f"sheet '{cell_patch.sheet}' not found"`. `TemplateSheetNotFoundError.__str__` 가 동일 문자열 → 422 응답 바이트 동일. 저장은 검증 후 1회 → 부분 기록 없음(기존과 동일).

- [ ] **Step 5: 회귀 오라클 + 단위 GREEN 확인**

Run: `cd /bj-dev/v4 && uv run pytest tests/integration/test_templates_api.py tests/unit/test_grid_io.py -q`
Expected: Step 1 과 동일한 test_templates_api 통과 카운트 + grid_io 4 passed. 0 failed.

- [ ] **Step 6: 미사용 import·타입·린트 확인**

Run: `cd /bj-dev/v4 && uv run ruff check app/api/routes/templates.py && uv run ruff format --check app/api/routes/templates.py && uv run mypy --strict app/`
Expected: ruff All checks passed (F401 미사용 import 0 — io/load_workbook 잔존 시 여기서 적발) / format already formatted / mypy Success in (count) files. 불일치 시 `uv run ruff format app/api/routes/templates.py`.

- [ ] **Step 7: 커밋**

```bash
cd /bj-dev/v4 && git add app/api/routes/templates.py && git commit -m "$(cat <<'EOF'
[P8.12] refactor: templates 라우터 openpyxl→grid_io (동작 보존)

get_template_grid/patch_template_cells 가 services.templates.grid_io
사용. HTTP 관심사(auth/DB/404/422)·응답·detail 문자열 불변.
test_templates_api 회귀 오라클 무변경 통과 확인.

Refs: docs/superpowers/specs/2026-05-15-openpyxl-services-refactor-design.md
EOF
)"
```

---

## Task 4: 실 양식 round-trip 테스트 추가 (실데이터 안전망)

**Files:**
- Modify: `tests/integration/test_real_template_round_trip.py` (기존 파일 — 함수 1개 추가, 기존 함수·skip-if-absent 관례 유지)

- [ ] **Step 1: 실패(또는 skip) 테스트 추가**

`tests/integration/test_real_template_round_trip.py` 끝에 추가:

```python
def test_real_xlsx_grid_io_round_trip() -> None:
    """실 양식 3장 → grid_io read_grid/apply_cell_patches round-trip 보존.

    PII 보호: 셀 값 자체를 단언/로그하지 않고 구조 불변식만 검증.
    """
    from app.services.templates.grid_io import apply_cell_patches, read_grid

    present = [p for p in _REAL_TEMPLATE_FILES if p.exists()]
    if not present:
        pytest.skip("real_templates 미존재 (gitignore)")

    for path in present:
        content = path.read_bytes()
        sheets = read_grid(content)
        assert sheets, f"{path.name}: 시트 0"
        assert any(s.cells for s in sheets.values()), f"{path.name}: 모든 시트 빈 셀"
        for s in sheets.values():
            assert s.max_row >= 1 and s.max_col >= 1

        # no-op 성격 패치: 기존 셀에 동일 값 재기록 → 구조 보존 확인.
        first_sheet, rs = next(iter(sheets.items()))
        assert rs.cells, f"{path.name}: {first_sheet} 빈 셀"
        c0 = rs.cells[0]
        new_bytes, count = apply_cell_patches(
            content, [(first_sheet, c0.row, c0.col, c0.value)]
        )
        assert count == 1
        after = read_grid(new_bytes)
        # 시트 집합·각 시트 셀 좌표/수식여부 보존.
        assert set(after) == set(sheets)
        for name in sheets:
            before_idx = {(c.row, c.col, c.is_formula) for c in sheets[name].cells}
            after_idx = {(c.row, c.col, c.is_formula) for c in after[name].cells}
            assert after_idx == before_idx, f"{path.name}/{name}: grid 구조 변경됨"
```

- [ ] **Step 2: 실행 (실파일 있으면 PASS, 없으면 SKIP)**

Run: `cd /bj-dev/v4 && uv run pytest tests/integration/test_real_template_round_trip.py -q`
Expected: 실 양식 3장 존재 시 기존 3 + 신규 1 = 통과. 부재 시 해당 항목 skip(에러 아님).

- [ ] **Step 3: 린트·타입 확인**

Run: `cd /bj-dev/v4 && uv run ruff check tests/integration/test_real_template_round_trip.py && uv run ruff format --check tests/integration/test_real_template_round_trip.py`
Expected: All checks passed / already formatted (불일치 시 `uv run ruff format <file>`)

- [ ] **Step 4: 커밋**

```bash
cd /bj-dev/v4 && git add tests/integration/test_real_template_round_trip.py && git commit -m "$(cat <<'EOF'
[P8.12] test: 실 양식 3장 grid_io round-trip (PII 미열람, 구조 불변식)

read_grid/apply_cell_patches 를 실 expense_* xlsx 로 검증. skip-if-absent.

Refs: docs/superpowers/specs/2026-05-15-openpyxl-services-refactor-design.md
EOF
)"
```

---

## Task 5: import-linter openpyxl/httpx 금지 contract 활성화

**Files:**
- Modify: `pyproject.toml` (`[tool.importlinter]` 섹션 — 보류 주석 제거 + forbidden contract 추가)

- [ ] **Step 1: 보류 주석 제거**

`pyproject.toml` 의 `[tool.importlinter]` 직전 주석에서 다음 2줄 삭제:

```
# 보류: api/domain 의 openpyxl/httpx 금지 contract — templates.py:27 선재 위반
#       (P7~8.8 유입). 게이트 약화 불가하므로 별도 sub-phase 리팩터 후 추가.
```

- [ ] **Step 2: forbidden contract 추가**

`pyproject.toml` 맨 끝(레이어 contract 의 `layers = [...]` 블록 뒤)에 추가:

```toml
[[tool.importlinter.contracts]]
name = "외부 IO 라이브러리 격리 — api/domain 은 openpyxl/httpx 직접 import 금지"
type = "forbidden"
source_modules = [
    "app.api",
    "app.domain",
]
forbidden_modules = [
    "openpyxl",
    "httpx",
]
```

- [ ] **Step 3: contract 통과 확인**

Run: `cd /bj-dev/v4 && uv run lint-imports`
Expected: `Contracts: 3 kept, 0 broken.` (도메인 순수성 + 레이어 + 신규 외부 IO 격리)
실패(broken) 시: 위반 모듈 출력 확인. templates.py 외 잔존 openpyxl/httpx api/domain import 가 있다는 뜻 → 해당 파일도 services 뒤로 이동 필요(범위 확장 — 사용자 보고 후 결정).

- [ ] **Step 4: 커밋**

```bash
cd /bj-dev/v4 && git add pyproject.toml && git commit -m "$(cat <<'EOF'
[P8.12] feat: import-linter openpyxl/httpx 금지 contract 활성화

P8.12 에서 보류했던 외부 IO 격리 게이트. templates 리팩터 완료로
api/domain 위반 0 — 3 kept 0 broken.

Refs: docs/superpowers/specs/2026-05-15-openpyxl-services-refactor-design.md
EOF
)"
```

---

## Task 6: 전체 검증 게이트 (이 세션 내 완료)

**Files:** 없음(검증만)

- [ ] **Step 1: 백엔드 전체 게이트 (CI backend 잡과 동일)**

Run:
```bash
cd /bj-dev/v4 && uv run ruff check app/ tests/ && uv run ruff format --check app/ tests/ && uv run mypy --strict app/ && uv run lint-imports && uv run pytest -m "not real_pdf" && uv run pip-audit --strict
```
Expected: ruff All checks passed / format already formatted / mypy Success / lint-imports 3 kept 0 broken / pytest all passed 0 failed / pip-audit No known vulnerabilities

- [ ] **Step 2: 실데이터 round-trip 로컬 실행 (smoke 안전망)**

Run: `cd /bj-dev/v4 && uv run pytest tests/integration/test_real_template_round_trip.py -q`
Expected: 실파일 존재 시 전부 passed, 부재 시 skip(에러 아님). 어느 경우든 0 failed.

- [ ] **Step 3: UI 무영향 확인 (백엔드 응답 스키마 불변 — 회귀 0)**

Run: `cd /bj-dev/v4/ui && npm run test`
Expected: 133 passed (변경 전과 동일 — 백엔드 스키마 불변이므로 UI 테스트 영향 없음). 0 failed.

- [ ] **Step 4: 최종 상태 보고**

`git log --oneline -7` 로 Task 1-5 커밋 5개 확인. 사용자에게 검증 결과 요약 보고(게이트 GREEN 카운트 + 실데이터 통과/skip 여부 명시). push 는 사용자 명시 요청 시(CLAUDE.md main 보호).

---

## Self-Review (작성자 점검 결과)

- **Spec 커버리지**: 설계 §3(grid_io 신설·라우터 매핑)=Task1-3, §4(에러 보존)=Task3 Step4 주석+Task2, §5(3중 안전망)=Task1-2(단위)·Task3 Step1/5(합성 오라클)·Task4(실데이터), §6(검증 게이트)=Task6, import-linter 활성화=Task5. 누락 없음.
- **Placeholder 스캔**: 모든 코드 스텝 실제 코드 포함. "적절히 처리" 류 없음.
- **타입 일관성**: `RawCell`/`RawSheet`/`TemplateSheetNotFoundError`/`read_grid`/`apply_cell_patches` 시그니처가 Task1·2 정의와 Task3·4 사용처에서 일치. `CellPatchItem`(.sheet/.row/.col/.value)·`GridCell`/`GridSheetView`/`GridResponse` 실제 스키마 확인 반영.
- 비고: Task5 broken 시 범위 확장 가능성(다른 api 파일 위반) — 사전 grep 결과 api 내 openpyxl 은 templates.py 단독, httpx 직접 import 0 이므로 3 kept 예상. 어긋나면 Step3 지침대로 보고.
