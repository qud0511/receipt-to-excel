from typing import Literal
from pydantic import BaseModel, Field


class LogEntry(BaseModel):
    ts: str                                    # HH:MM:SS (UTC)
    level: Literal["info", "warn", "error"]
    msg: str


class JobProgress(BaseModel):
    job_id: str
    template_id: str
    user_id: str = "default"
    status: Literal["pending", "processing", "completed", "failed"]
    total: int
    done: int
    failed_files: list[str] = []
    current_file: str | None = None
    download_url: str | None = None
    pdf_url: str | None = None
    nup_pdf_url: str | None = None
    error: str | None = None
    logs: list[LogEntry] = Field(default_factory=list)
