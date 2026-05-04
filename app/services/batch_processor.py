from PIL.Image import Image

from app.core.config import Config
from app.core.job_manager import InMemoryJobManager
from app.schemas.receipt import ReceiptData
from app.services.excel_mapper import build_excel
from app.services.file_manager import FileSystemManager
from app.services.nup_pdf import make_nup_pdf
from app.services.ollama_client import ExtractError, OllamaClient
from app.services.pdf_merger import merge_to_pdf
from app.services.preprocessor import ProcessedInput
from app.services.template_analyzer import analyze
from app.services.template_store import TemplateStore


async def preprocess_and_run(
    job_id: str,
    file_pairs: list[tuple[bytes, str]],
    template_id: str,
    job_manager: InMemoryJobManager,
    ollama: OllamaClient,
    template_store: TemplateStore,
    config: Config,
    user_id: str = "default",
) -> None:
    """파일별 OCR(Docling) 전처리 → LLM 추출 파이프라인 전체를 백그라운드에서 실행."""
    from app.services.preprocessor import route_file

    all_inputs: list[ProcessedInput] = []
    for content, filename in file_pairs:
        await job_manager.add_log(job_id, f"[{filename}] OCR 추출 중...", "info")
        try:
            inputs = route_file(content, filename)
            all_inputs.extend(inputs)
            await job_manager.add_log(
                job_id,
                f"[{filename}] OCR 완료 ({len(inputs)}페이지)",
                "info",
            )
        except Exception as e:
            await job_manager.add_log(job_id, f"[{filename}] OCR 실패 — {e}", "error")
            await job_manager.fail_file(job_id, f"{filename} (OCR 실패)")

    await job_manager.update_total(job_id, len(all_inputs))
    await run_job(
        job_id, all_inputs, template_id,
        job_manager, ollama, template_store, config, user_id,
    )


async def run_job(
    job_id: str,
    inputs: list[ProcessedInput],
    template_id: str,
    job_manager: InMemoryJobManager,
    ollama: OllamaClient,
    template_store: TemplateStore,
    config: Config,
    user_id: str = "default",
) -> None:
    try:
        template = await template_store.get(template_id)
        system_prompt = template.custom_prompt or None
        receipts: list[ReceiptData] = []
        pdf_pages: list[Image] = []
        total = len(inputs)

        for i, processed in enumerate(inputs):
            await job_manager.update(job_id, done=i, current_file=processed.source_name)
            await job_manager.add_log(
                job_id,
                f"[{processed.source_name}] LLM 분석 중... ({i + 1}/{total})",
                "info",
            )
            if processed.pil_image is not None:
                pdf_pages.append(processed.pil_image)
            try:
                receipt = await ollama.extract_receipt(processed, system_prompt)
                receipts.append(receipt)
                await job_manager.add_log(
                    job_id,
                    f"[{processed.source_name}] 추출 완료",
                    "info",
                )
            except ExtractError as e:
                label = f"{processed.source_name}:p{processed.source_page} ({e})"
                await job_manager.fail_file(job_id, label)
                await job_manager.add_log(
                    job_id,
                    f"[{processed.source_name}] 추출 실패 — {e}",
                    "error",
                )
            except Exception as e:
                label = f"{processed.source_name}:p{processed.source_page}"
                await job_manager.fail_file(job_id, label)
                await job_manager.add_log(
                    job_id,
                    f"[{processed.source_name}] 처리 오류 — {e}",
                    "error",
                )

        success_count = len(receipts)
        fail_count = total - success_count
        await job_manager.add_log(
            job_id,
            f"처리 완료 — 성공 {success_count}건, 실패 {fail_count}건",
            "info" if fail_count == 0 else "warn",
        )

        fs = FileSystemManager.from_config(config.data_dir, user_id)

        tpl_path  = template_store.template_path(template_id)
        xlsx_path = fs.result_xlsx(job_id)
        if receipts:
            tpl_config = analyze(tpl_path.read_bytes())
            build_excel(tpl_path, xlsx_path, receipts, tpl_config)

        evidence_path = fs.evidence_pdf(job_id)
        merge_to_pdf(pdf_pages, evidence_path)

        nup_path = fs.evidence_nup_pdf(job_id)
        make_nup_pdf(pdf_pages, nup_path, cols=2, rows=2)

        base = f"/jobs/{job_id}"
        pdf_url     = f"{base}/result/pdf"     if evidence_path.exists() else None
        nup_pdf_url = f"{base}/result/pdf/nup" if nup_path.exists()      else None

        await job_manager.complete(
            job_id,
            download_url=f"{base}/result",
            pdf_url=pdf_url,
            nup_pdf_url=nup_pdf_url,
        )
    except Exception as e:
        await job_manager.fail(job_id, str(e))
