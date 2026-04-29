from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.deps import get_template_store
from app.api.routes import jobs, templates

_STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = get_template_store()
    await store.init_db()
    yield


app = FastAPI(title="Receipt to Excel", lifespan=lifespan)

app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(templates.router, prefix="/templates", tags=["templates"])


@app.get("/", include_in_schema=False)
async def serve_index():
    return FileResponse(_STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
