"""Phase 5.1 — 사용자 .xlsx 양식 자동 분석 → SheetConfig 매핑.

ADR-006 §"Phase 5 TemplateAnalyzer 명세" 7 단계 휴리스틱:
1. 시트명 suffix 로 sheet_kind 결정 (`{YY.MM}_법인`, `{YY.MM}_개인`).
2. A2 == "경비 사용 내역서" 시트만 분석 (차량 시트 skip).
3. row 7 keyword 헤더 → category_cols 매핑 (식대/접대비/기타비용/여비교통비 등).
4. Named range (FIELD_*, DATA_START_*) → field-mode 슬롯 채움.
5. A 컬럼 row 9 부터 "합" 포함 셀 스캔 → sum_row.
6. data_end_row = sum_row - 1 (gap 1~2 자동 흡수).
7. formula_cols = data 영역 + sum_row 의 `=` 시작 셀 column letter 집합.

field/category/hybrid 3 modes 는 `SheetConfig.mode` computed_field 가 자동 결정.
"""

from __future__ import annotations

import io
import re

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from app.domain.template_map import SheetConfig

_SHEET_KIND_PATTERN = re.compile(r"_(법인|개인|차량)$")
_TITLE_MARKER = "경비 사용 내역서"
_SUM_LABEL_PATTERN = re.compile(r"^\s*합")  # "합", "합계", "합    계" 모두 매칭.
_FIELD_NAMED_RANGE_RE = re.compile(
    r"^(FIELD_(DATE|MERCHANT|TOTAL|PROJECT|NOTE)|DATA_START)_(법인|개인)$"
)

# row 7 / row 8 keyword 헤더 — substring 매칭 (G "버스,택시,대리" vs "버스,택시" 변동 흡수).
_CATEGORY_KEYWORDS = (
    "여비교통비",
    "차량유지비",
    "식대",
    "접대비",
    "기타비용",
    # row 8 sub-headers
    "항공료",
    "버스",  # "버스,택시" / "버스,택시,대리" 양쪽 매칭
    "숙박비",
    "유류대",
    "주차",  # "주차,통행료"
)


class TemplateAnalysisError(ValueError):
    """양식 분석 실패 — 헤더·named range 둘 다 부재 시 raise."""


def analyze_workbook(content: bytes) -> dict[str, SheetConfig]:
    """ADR-006 휴리스틱으로 .xlsx bytes → 시트별 SheetConfig."""
    wb = load_workbook(io.BytesIO(content), data_only=False)  # 수식 텍스트 보존.

    result: dict[str, SheetConfig] = {}
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        if not _is_target_sheet(ws):
            continue
        cfg = _analyze_sheet(wb, ws)
        if cfg is None:
            continue
        result[sheet_name] = cfg

    if not result:
        raise TemplateAnalysisError(
            "분석 가능한 시트 부재 — '경비 사용 내역서' 마커 + 법인/개인 시트 명명 규약 필요"
        )
    return result


def _is_target_sheet(ws: Worksheet) -> bool:
    """ADR-006: A2='경비 사용 내역서' + 시트명 suffix 가 법인/개인."""
    if ws.title is None:
        return False
    match = _SHEET_KIND_PATTERN.search(ws.title)
    if not match or match.group(1) == "차량":
        return False
    a2 = ws["A2"].value
    return isinstance(a2, str) and _TITLE_MARKER in a2


def _analyze_sheet(wb: Workbook, ws: Worksheet) -> SheetConfig | None:
    """단일 시트 분석 → SheetConfig.

    field + category 둘 다 부재면 None 반환 — analyze_workbook 에서 error 처리.
    """
    sheet_kind = _extract_sheet_kind(ws.title)
    assert sheet_kind in ("법인", "개인")  # _is_target_sheet 통과 후 보장.

    # ── named range 기반 field 슬롯 (시트 scope) ──────────────────────────
    field_slots = _extract_field_slots(wb, sheet_kind)

    # ── row 7 + row 8 keyword 헤더 기반 category_cols ─────────────────────
    category_cols = _extract_category_cols(ws)

    # 헤더·named range 둘 다 부재 → 분석 실패.
    if not field_slots and not category_cols:
        return None

    # ── sum_row 탐지 (A 컬럼 "합" 라벨 스캔) ───────────────────────────────
    sum_row = _find_sum_row(ws)
    # ADR-006: data_start_row 는 항상 9 (헤더 row 8 의 다음).
    data_start_row = 9
    data_end_row = (sum_row - 1) if sum_row else ws.max_row

    # ── formula_cols 수집 (행별 SUM + sum_row 세로 SUM) ────────────────────
    formula_cols = _extract_formula_cols(ws, data_start_row, sum_row or data_end_row)

    return SheetConfig(
        sheet_name=sheet_kind,
        date_col=field_slots.get("DATE"),
        merchant_col=field_slots.get("MERCHANT"),
        project_col=field_slots.get("PROJECT"),
        total_col=field_slots.get("TOTAL"),
        note_col=field_slots.get("NOTE"),
        category_cols=category_cols,
        formula_cols=formula_cols,
        data_start_row=data_start_row,
        data_end_row=data_end_row,
        sum_row=sum_row,
        header_row=7,
    )


def _extract_sheet_kind(title: str) -> str:
    match = _SHEET_KIND_PATTERN.search(title)
    assert match is not None
    return match.group(1)


def _extract_field_slots(wb: Workbook, sheet_kind: str) -> dict[str, str]:
    """named range FIELD_*_{sheet_kind} → 슬롯 → column letter.

    예: FIELD_DATE_법인 = 'sheet'!$A$9 → {"DATE": "A"}.
    """
    slots: dict[str, str] = {}
    for name, defn in wb.defined_names.items():
        match = _FIELD_NAMED_RANGE_RE.match(name)
        if not match or match.group(3) != sheet_kind:
            continue
        slot = match.group(2) or "DATA_START"
        # defn.value 형식: "'시트명'!$A$9" 또는 "시트명!$A$9"
        addr = defn.value or ""
        col_letter = _extract_col_letter(addr)
        if col_letter is None:
            continue
        # FIELD_DATE → "DATE", DATA_START → 슬롯 등록 안함 (data_start_row 결정만).
        if name.startswith("FIELD_"):
            slots[slot] = col_letter
    return slots


def _extract_col_letter(address: str) -> str | None:
    """`'시트명'!$A$9` 또는 `시트명!$A$9` → "A". 파싱 실패 시 None."""
    # `!` 이후 첫 `$` 그룹의 column letter 추출.
    match = re.search(r"!\$?([A-Z]+)\$?\d+", address)
    return match.group(1) if match else None


def _extract_category_cols(ws: Worksheet) -> dict[str, str]:
    """row 7 + row 8 keyword 헤더 → category_cols (substring 매칭).

    G "버스,택시" vs "버스,택시,대리" 변동 흡수: keyword 가 cell text 의 substring 이면 매칭.
    """
    cols: dict[str, str] = {}
    for row in (7, 8):
        for col_idx in range(1, ws.max_column + 1):
            cell_val = ws.cell(row=row, column=col_idx).value
            if not isinstance(cell_val, str):
                continue
            for kw in _CATEGORY_KEYWORDS:
                if kw in cell_val and kw not in cols:
                    cols[kw] = get_column_letter(col_idx)
                    break
    return cols


def _find_sum_row(ws: Worksheet) -> int | None:
    """A 컬럼 row 9 부터 스캔 — 첫 "합" 포함 셀 row."""
    for row in range(9, ws.max_row + 1):
        val = ws.cell(row=row, column=1).value
        if isinstance(val, str) and _SUM_LABEL_PATTERN.match(val):
            return row
    return None


def _extract_formula_cols(ws: Worksheet, data_start_row: int, scan_end_row: int) -> set[str]:
    """data_start_row ~ scan_end_row 의 `=` 시작 셀 column letter 집합."""
    cols: set[str] = set()
    for row in range(data_start_row, scan_end_row + 1):
        for col_idx in range(1, ws.max_column + 1):
            val = ws.cell(row=row, column=col_idx).value
            if isinstance(val, str) and val.startswith("="):
                cols.add(get_column_letter(col_idx))
    return cols
