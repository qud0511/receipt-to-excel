from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.deps import get_template_store
from app.api.routes import jobs, templates


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = get_template_store()
    await store.init_db()
    yield


app = FastAPI(title="Receipt to Excel", lifespan=lifespan)

app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(templates.router, prefix="/templates", tags=["templates"])
