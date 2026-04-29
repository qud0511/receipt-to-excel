import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from openpyxl import Workbook
from openpyxl.workbook.defined_name import DefinedName

from app.services.batch_processor import run_job
from app.core.job_manager import InMemoryJobManager
from app.services.preprocessor import ProcessedInput
from app.schemas.receipt import ReceiptData
from app.schemas.template import Template


def make_input(name: str, page: int = 0) -> ProcessedInput:
    return ProcessedInput(
        source_name=name,
        source_page=page,
        docling_text="업체명: 테스트\n금액: 1000",
        pil_image=None,
    )


def make_receipt(name: str = "스타벅스") -> ReceiptData:
    return ReceiptData(
        날짜="2024-01-15", 업체명=name, 품목="아메리카노",
        금액=5500, 부가세=500, 결제수단="카드",
    )


def _make_template_xlsx(tmp_path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws["B2"] = "날짜"
    ws["C2"] = "업체명"
    wb.defined_names.add(DefinedName("FIELD_날짜",   attr_text="Sheet1!$B$2"))
    wb.defined_names.add(DefinedName("FIELD_업체명", attr_text="Sheet1!$C$2"))
    (tmp_path / "templates").mkdir(exist_ok=True)
    wb.save(tmp_path / "templates" / "tpl_test.xlsx")


def _make_mock_store(tmp_data_dir) -> MagicMock:
    _make_template_xlsx(tmp_data_dir)
    store = MagicMock()
    store.get = AsyncMock(return_value=Template(
        template_id="tpl_test", name="A",
        fields=["날짜", "업체명"], custom_prompt=None,
        created_at=datetime.utcnow(),
    ))
    store.template_path = MagicMock(
        return_value=tmp_data_dir / "templates" / "tpl_test.xlsx"
    )
    return store


async def test_run_job_completes(tmp_data_dir):
    mgr = InMemoryJobManager()
    await mgr.create("j1", template_id="tpl_test", total=2)

    ollama = MagicMock()
    ollama.extract_receipt = AsyncMock(return_value=make_receipt())

    config = MagicMock()
    config.ollama_system_prompt = "prompt"
    config.data_dir = tmp_data_dir

    inputs = [make_input("a.jpg"), make_input("b.jpg")]
    await run_job("j1", inputs, "tpl_test", mgr, ollama, _make_mock_store(tmp_data_dir), config)

    job = await mgr.get("j1")
    assert job.status == "completed"
    assert job.download_url == "/jobs/j1/result"


async def test_run_job_partial_failure(tmp_data_dir):
    mgr = InMemoryJobManager()
    await mgr.create("j1", template_id="tpl_test", total=2)

    ollama = MagicMock()
    ollama.extract_receipt = AsyncMock(side_effect=Exception("timeout"))

    config = MagicMock()
    config.ollama_system_prompt = "prompt"
    config.data_dir = tmp_data_dir

    inputs = [make_input("a.jpg"), make_input("b.jpg")]
    await run_job("j1", inputs, "tpl_test", mgr, ollama, _make_mock_store(tmp_data_dir), config)

    job = await mgr.get("j1")
    assert job.status == "completed"
    assert len(job.failed_files) == 2
