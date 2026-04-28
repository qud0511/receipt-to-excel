from fastapi import FastAPI

from app.api.routes import jobs

app = FastAPI(title="Receipt to Excel")

app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
