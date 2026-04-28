from typing import Literal
from pydantic import BaseModel


class JobProgress(BaseModel):
    job_id: str
    template_id: str
    status: Literal["pending", "processing", "completed", "failed"]
    total: int
    done: int
    failed_files: list[str] = []
    current_file: str | None = None
    download_url: str | None = None
    pdf_url: str | None = None
    error: str | None = None
