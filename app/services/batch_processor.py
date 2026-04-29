from app.core.job_manager import InMemoryJobManager
from app.services.ollama_client import OllamaClient
from app.services.preprocessor import ProcessedInput
from app.core.config import Config


async def run_job(
    job_id: str,
    inputs: list[ProcessedInput],
    job_manager: InMemoryJobManager,
    ollama: OllamaClient,
    config: Config,
) -> None:
    try:
        for i, processed in enumerate(inputs):
            await job_manager.update(job_id, done=i, current_file=processed.source_name)
            try:
                await ollama.extract_receipt(processed, config.ollama_system_prompt)
            except Exception:
                label = f"{processed.source_name}:p{processed.source_page}"
                await job_manager.fail_file(job_id, label)

        await job_manager.complete(job_id)
    except Exception as e:
        await job_manager.fail(job_id, str(e))
