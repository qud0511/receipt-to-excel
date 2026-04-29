import asyncio
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import get_job_manager, get_ollama_client
from app.core.config import Config, get_config
from app.core.job_manager import InMemoryJobManager
from app.services.batch_processor import run_job
from app.services.ollama_client import OllamaClient
from app.services.preprocessor import route_file

router = APIRouter()


@router.post("")
async def create_job(
    files: list[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None,
    job_manager: InMemoryJobManager = Depends(get_job_manager),
    ollama: OllamaClient = Depends(get_ollama_client),
    config: Config = Depends(get_config),
):
    all_inputs = []
    for f in files:
        content = await f.read()
        try:
            all_inputs.extend(route_file(content, f.filename or "unknown"))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    job_id = uuid.uuid4().hex[:8]
    await job_manager.create(job_id, template_id="", total=len(all_inputs))
    background_tasks.add_task(run_job, job_id, all_inputs, job_manager, ollama, config)

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
