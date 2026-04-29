from app.core.config import Config
from app.core.job_manager import InMemoryJobManager
from app.schemas.receipt import ReceiptData
from app.services.excel_mapper import build_excel
from app.services.ollama_client import OllamaClient
from app.services.preprocessor import ProcessedInput
from app.services.template_store import TemplateStore


async def run_job(
    job_id: str,
    inputs: list[ProcessedInput],
    template_id: str,
    job_manager: InMemoryJobManager,
    ollama: OllamaClient,
    template_store: TemplateStore,
    config: Config,
) -> None:
    try:
        template = await template_store.get(template_id)
        system_prompt = template.custom_prompt or config.ollama_system_prompt
        receipts: list[ReceiptData] = []

        for i, processed in enumerate(inputs):
            await job_manager.update(job_id, done=i, current_file=processed.source_name)
            try:
                receipt = await ollama.extract_receipt(processed, system_prompt)
                receipts.append(receipt)
            except Exception:
                label = f"{processed.source_name}:p{processed.source_page}"
                await job_manager.fail_file(job_id, label)

        jobs_dir = config.data_dir / "jobs" / job_id
        jobs_dir.mkdir(parents=True, exist_ok=True)
        excel_path = jobs_dir / "result.xlsx"

        build_excel(template_store.template_path(template_id), excel_path, receipts)

        await job_manager.complete(job_id, download_url=f"/jobs/{job_id}/result")
    except Exception as e:
        await job_manager.fail(job_id, str(e))
