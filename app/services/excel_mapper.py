import io
import re
import shutil
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string

from app.schemas.receipt import ReceiptData


def validate_template(xlsx_bytes: bytes) -> list[str]:
    """FIELD_* Named Range 목록을 반환. 없으면 ValueError."""
    wb = load_workbook(io.BytesIO(xlsx_bytes))
    fields = _field_mapping(wb)
    wb.close()
    if not fields:
        raise ValueError("템플릿에 FIELD_* Named Range가 없습니다.")
    return list(fields.keys())


def build_excel(
    template_path: Path,
    output_path: Path,
    receipts: list[ReceiptData],
) -> None:
    shutil.copy2(template_path, output_path)
    wb = load_workbook(output_path)
    ws = wb.active
    mapping = _field_mapping(wb)
    start_row = _data_start_row(wb)

    for i, receipt in enumerate(receipts):
        row = start_row + i
        row_data = receipt.model_dump()
        for field, col in mapping.items():
            ws.cell(row=row, column=col, value=row_data.get(field))

    wb.save(output_path)
    wb.close()


def _field_mapping(wb) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for name in wb.defined_names:
        if name.startswith("FIELD_"):
            field = name[6:]
            _, cell_ref = list(wb.defined_names[name].destinations)[0]
            col_letter = re.sub(r"[\$\d]", "", cell_ref)
            mapping[field] = column_index_from_string(col_letter)
    return mapping


def _data_start_row(wb) -> int:
    defined = wb.defined_names
    if "DATA_START" in defined:
        _, cell_ref = list(defined["DATA_START"].destinations)[0]
        return int(re.sub(r"[^\d]", "", cell_ref))

    max_row = 0
    for name in defined:
        if name.startswith("FIELD_"):
            _, cell_ref = list(defined[name].destinations)[0]
            row = int(re.sub(r"[^\d]", "", cell_ref))
            max_row = max(max_row, row)

    if max_row == 0:
        raise ValueError("템플릿에 FIELD_* Named Range가 없습니다.")
    return max_row + 1
