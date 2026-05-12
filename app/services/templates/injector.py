"""Phase 5.1c — Named range 주입 (FIELD_*_{kind}, DATA_START_{kind}).

XLSX writer 가 잡 실행 시 슬롯 좌표 재계산 불필요하게 함. 양식 등록 단계에서 1 회 영속.
CLAUDE.md §"성능": TemplateConfig 는 등록 시 영속 — 잡 시 재분석 안 함.

ADR-006: 시트 scope 가 시트별 (`{quoted_sheet}!$A$9`). openpyxl 의 `DefinedName.value`
는 절대 좌표 ($) + 시트명 quote 처리 필수.
"""

from __future__ import annotations

import io
import re

from openpyxl import load_workbook
from openpyxl.workbook.defined_name import DefinedName

from app.domain.template_map import SheetConfig

# 시트명 quote 필요 조건: 공백, 한글, 특수문자 등 — 안전하게 항상 quote.
_SAFE_SHEET_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def inject_named_ranges(
    content: bytes,
    *,
    sheet_name: str,
    config: SheetConfig,
) -> bytes:
    """SheetConfig 의 슬롯·data_start_row 를 named range 로 주입 → 갱신된 .xlsx bytes 반환.

    주입 named range (sheet_name 의 sheet_kind suffix 사용):
    - FIELD_DATE_{kind}     ← config.date_col
    - FIELD_MERCHANT_{kind} ← config.merchant_col
    - FIELD_TOTAL_{kind}    ← config.total_col
    - FIELD_PROJECT_{kind}  ← config.project_col (있을 때만)
    - FIELD_NOTE_{kind}     ← config.note_col (있을 때만)
    - DATA_START_{kind}     ← {date_col 또는 'A'}{data_start_row}

    기존 동명 named range 가 있으면 덮어쓰기.
    """
    wb = load_workbook(io.BytesIO(content))
    quoted_sheet = _quote_sheet_name(sheet_name)
    kind = config.sheet_name  # SheetConfig.sheet_name 은 "법인" / "개인"

    # 각 슬롯별 좌표 결정.
    slots: dict[str, str | None] = {
        f"FIELD_DATE_{kind}": config.date_col,
        f"FIELD_MERCHANT_{kind}": config.merchant_col,
        f"FIELD_TOTAL_{kind}": config.total_col,
        f"FIELD_PROJECT_{kind}": config.project_col,
        f"FIELD_NOTE_{kind}": config.note_col,
    }
    data_anchor_col = config.date_col or "A"
    slots[f"DATA_START_{kind}"] = data_anchor_col

    for name, col in slots.items():
        if col is None:
            continue
        addr = f"{quoted_sheet}!${col}${config.data_start_row}"
        # 기존 동명 named range 제거 후 재등록 (openpyxl DefinedNameDict 는 키 중복 시 덮어쓰기).
        wb.defined_names[name] = DefinedName(name, attr_text=addr)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _quote_sheet_name(sheet_name: str) -> str:
    """openpyxl 명세: 공백·한글·특수문자 시트명은 single-quote 로 감싸야 함."""
    if _SAFE_SHEET_NAME.match(sheet_name):
        return sheet_name
    # quote 내부 single-quote 는 이중 quote 로 escape.
    escaped = sheet_name.replace("'", "''")
    return f"'{escaped}'"
