import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.batch_processor import run_job
from app.core.job_manager import InMemoryJobManager
from app.services.preprocessor import ProcessedInput
from app.schemas.receipt import ReceiptData


def make_input(name: str, page: int = 0) -> ProcessedInput:
    return ProcessedInput(
        source_name=name,
        source_page=page,
        docling_text="업체명: 테스트\n금액: 1000",
        pil_image=None,
    )


def make_receipt() -> ReceiptData:
    return ReceiptData(
        날짜="2024-01-15", 업체명="스타벅스", 품목="아메리카노",
        금액=5500, 부가세=500, 결제수단="카드",
    )


async def test_run_job_completes(tmp_data_dir):
    mgr = InMemoryJobManager()
    await mgr.create("j1", template_id="", total=2)

    ollama = MagicMock()
    ollama.extract_receipt = AsyncMock(return_value=make_receipt())

    config = MagicMock()
    config.ollama_system_prompt = "prompt"
    config.data_dir = tmp_data_dir

    inputs = [make_input("a.jpg"), make_input("b.jpg")]
    await run_job("j1", inputs, mgr, ollama, config)

    job = await mgr.get("j1")
    assert job.status == "completed"
    assert job.done == 2


async def test_run_job_records_failed_file(tmp_data_dir):
    mgr = InMemoryJobManager()
    await mgr.create("j1", template_id="", total=2)

    ollama = MagicMock()
    ollama.extract_receipt = AsyncMock(side_effect=Exception("timeout"))

    config = MagicMock()
    config.ollama_system_prompt = "prompt"
    config.data_dir = tmp_data_dir

    inputs = [make_input("a.jpg"), make_input("b.jpg")]
    await run_job("j1", inputs, mgr, ollama, config)

    job = await mgr.get("j1")
    assert job.status == "completed"
    assert len(job.failed_files) == 2
