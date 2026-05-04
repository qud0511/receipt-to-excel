import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from app.api.deps import get_job_manager, get_ollama_client, get_template_store
from app.core.config import Config, get_config
from app.core.job_manager import InMemoryJobManager
from app.services.batch_processor import preprocess_and_run
from app.services.file_manager import FileSystemManager
from app.services.ollama_client import OllamaClient
from app.services.template_store import TemplateStore

router = APIRouter()

_ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".pdf", ".xlsx", ".pptx"}


@router.post("")
async def create_job(
    files: list[UploadFile] = File(...),
    template_id: str = Form(...),
    user_id: str = Form("default"),
    background_tasks: BackgroundTasks = None,
    job_manager: InMemoryJobManager = Depends(get_job_manager),
    ollama: OllamaClient = Depends(get_ollama_client),
    template_store: TemplateStore = Depends(get_template_store),
    config: Config = Depends(get_config),
):
    try:
        await template_store.get(template_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Template not found")

    file_pairs: list[tuple[bytes, str]] = []
    for f in files:
        suffix = Path(f.filename or "").suffix.lower()
        if suffix not in _ALLOWED_EXTS:
            raise HTTPException(
                status_code=422,
                detail=f"지원하지 않는 파일 형식: {f.filename}",
            )
        content = await f.read()
        file_pairs.append((content, f.filename or "unknown"))

    job_id = uuid.uuid4().hex[:8]
    await job_manager.create(
        job_id, template_id=template_id,
        total=len(file_pairs), user_id=user_id,
    )
    background_tasks.add_task(
        preprocess_and_run, job_id, file_pairs, template_id,
        job_manager, ollama, template_store, config, user_id,
    )

    return {"job_id": job_id, "status": "pending", "total": len(file_pairs)}


@router.get("/{job_id}/stream")
async def stream_job(
    job_id: str,
    job_manager: InMemoryJobManager = Depends(get_job_manager),
):
    async def event_gen():
        yield "retry: 60000\n\n"
        while True:
            try:
                job = await job_manager.get(job_id)
            except KeyError:
                yield 'data: {"error":"job not found"}\n\n'
                break
            yield f"data: {job.model_dump_json()}\n\n"
            if job.status in ("completed", "failed"):
                break
            await asyncio.sleep(1)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{job_id}/result")
async def download_excel(
    job_id: str,
    job_manager: InMemoryJobManager = Depends(get_job_manager),
    config: Config = Depends(get_config),
):
    try:
        job = await job_manager.get(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=404, detail="Job not completed yet")

    fs = FileSystemManager.from_config(config.data_dir, job.user_id)
    excel_path = fs.result_xlsx(job_id)
    if not excel_path.exists():
        raise HTTPException(status_code=404, detail="Excel file not found")

    return FileResponse(
        path=excel_path,
        filename=f"지출결의서_{job_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/{job_id}/result/pdf")
async def download_pdf(
    job_id: str,
    job_manager: InMemoryJobManager = Depends(get_job_manager),
    config: Config = Depends(get_config),
):
    try:
        job = await job_manager.get(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=404, detail="Job not completed yet")

    fs = FileSystemManager.from_config(config.data_dir, job.user_id)
    pdf_path = fs.evidence_pdf(job_id)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not available")

    return FileResponse(
        path=pdf_path,
        filename=f"영수증_{job_id}.pdf",
        media_type="application/pdf",
    )


@router.get("/{job_id}/result/pdf/nup")
async def download_nup_pdf(
    job_id: str,
    job_manager: InMemoryJobManager = Depends(get_job_manager),
    config: Config = Depends(get_config),
):
    try:
        job = await job_manager.get(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=404, detail="Job not completed yet")

    fs = FileSystemManager.from_config(config.data_dir, job.user_id)
    nup_path = fs.evidence_nup_pdf(job_id)
    if not nup_path.exists():
        raise HTTPException(status_code=404, detail="N-up PDF not available")

    return FileResponse(
        path=nup_path,
        filename=f"영수증_모아찍기_{job_id}.pdf",
        media_type="application/pdf",
    )
