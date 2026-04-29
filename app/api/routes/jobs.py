import asyncio
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from app.api.deps import get_job_manager, get_ollama_client, get_template_store
from app.core.config import Config, get_config
from app.core.job_manager import InMemoryJobManager
from app.services.batch_processor import run_job
from app.services.ollama_client import OllamaClient
from app.services.preprocessor import route_file
from app.services.template_store import TemplateStore

router = APIRouter()


@router.post("")
async def create_job(
    files: list[UploadFile] = File(...),
    template_id: str = Form(...),
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

    all_inputs = []
    for f in files:
        content = await f.read()
        try:
            all_inputs.extend(route_file(content, f.filename or "unknown"))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    job_id = uuid.uuid4().hex[:8]
    await job_manager.create(job_id, template_id=template_id, total=len(all_inputs))
    background_tasks.add_task(
        run_job, job_id, all_inputs, template_id,
        job_manager, ollama, template_store, config,
    )

    return {"job_id": job_id, "status": "pending", "total": len(all_inputs)}


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

    excel_path = config.data_dir / "jobs" / job_id / "result.xlsx"
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

    pdf_path = config.data_dir / "jobs" / job_id / "evidence.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not available")

    return FileResponse(
        path=pdf_path,
        filename=f"영수증_{job_id}.pdf",
        media_type="application/pdf",
    )
