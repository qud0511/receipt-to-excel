import asyncio

from app.schemas.job import JobProgress


class InMemoryJobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobProgress] = {}
        self._lock = asyncio.Lock()

    async def create(self, job_id: str, template_id: str, total: int, user_id: str = "default") -> None:
        async with self._lock:
            self._jobs[job_id] = JobProgress(
                job_id=job_id,
                template_id=template_id,
                user_id=user_id,
                status="pending",
                total=total,
                done=0,
            )

    async def update(self, job_id: str, done: int, current_file: str) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            self._jobs[job_id] = job.model_copy(update={
                "status": "processing",
                "done": done,
                "current_file": current_file,
            })

    async def fail_file(self, job_id: str, filename: str) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            self._jobs[job_id] = job.model_copy(update={
                "failed_files": job.failed_files + [filename],
            })

    async def complete(
        self,
        job_id: str,
        download_url: str | None = None,
        pdf_url: str | None = None,
        nup_pdf_url: str | None = None,
    ) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            self._jobs[job_id] = job.model_copy(update={
                "status": "completed",
                "done": job.total,
                "current_file": None,
                "download_url": download_url,
                "pdf_url": pdf_url,
                "nup_pdf_url": nup_pdf_url,
            })

    async def fail(self, job_id: str, error: str) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            self._jobs[job_id] = job.model_copy(update={
                "status": "failed",
                "error": error,
            })

    async def add_log(self, job_id: str, msg: str, level: str = "info") -> None:
        from datetime import datetime, timezone
        from app.schemas.job import LogEntry
        async with self._lock:
            job = self._jobs[job_id]
            entry = LogEntry(
                ts=datetime.now(timezone.utc).strftime("%H:%M:%S"),
                level=level,
                msg=msg,
            )
            self._jobs[job_id] = job.model_copy(update={
                "logs": job.logs + [entry],
            })

    async def update_total(self, job_id: str, total: int) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            self._jobs[job_id] = job.model_copy(update={"total": total})

    async def get(self, job_id: str) -> JobProgress:
        async with self._lock:
            if job_id not in self._jobs:
                raise KeyError(f"Job {job_id!r} not found")
            return self._jobs[job_id]
