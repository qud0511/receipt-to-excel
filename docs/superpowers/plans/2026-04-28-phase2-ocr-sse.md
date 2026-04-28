# Phase 2 — Ollama OCR, Job Manager, SSE Progress Stream

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ollama OCR 파이프라인 + InMemoryJobManager + SSE 진행률 스트림 구현. 파일 업로드 → 백그라운드 OCR → SSE로 실시간 진행률 확인 가능한 상태.

**Architecture:** `InMemoryJobManager` 가 잡 상태를 들고, `BatchProcessor` 가 asyncio 백그라운드 태스크로 `OllamaClient` 를 순차 호출한다. `GET /jobs/{id}/stream` 은 1초 간격으로 잡 상태를 SSE로 push한다. Phase 2에서는 엑셀/PDF 생성 없이 OCR 결과 수집까지만 한다.

**Tech Stack:** Python 3.11+, FastAPI, httpx (Ollama HTTP), asyncio, pytest-asyncio

**전제:** Phase 1 완료 (스키마, 전처리기, POST /jobs 기본 버전)

---

**Definition of Done:**
```bash
# 터미널 1: 서버 기동
source .venv/bin/activate && uvicorn app.main:app --reload

# 터미널 2: 파일 업로드 → job_id 획득
JOB=$(curl -s -X POST http://localhost:8000/jobs \
  -F "files=@tests/fixtures/sample.jpg" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
echo "job_id: $JOB"

# 터미널 3: SSE 구독
curl -N http://localhost:8000/jobs/$JOB/stream
# 기대: data: {"status":"processing",...} 이후 data: {"status":"completed",...}
```
> Ollama + gemma4 미설치 시 status: "failed", error: "Ollama connection refused" 가 정상

---

## 파일 구조

```
app/
  core/
    job_manager.py                   (NEW)
  api/
    deps.py                          (MODIFY — JobManager, OllamaClient 추가)
    routes/
      jobs.py                        (MODIFY — 백그라운드 태스크 + SSE 추가)
  services/
    ollama_client.py                 (NEW)
    batch_processor.py               (NEW)

tests/
  test_job_manager.py                (NEW)
  test_ollama_client.py              (NEW)
  test_batch_processor.py            (NEW)
```

---

## Task 1: InMemoryJobManager

**Files:**
- Create: `app/core/job_manager.py`
- Create: `tests/test_job_manager.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_job_manager.py`:
```python
import pytest
from app.core.job_manager import InMemoryJobManager


@pytest.fixture
def mgr():
    return InMemoryJobManager()


async def test_create_and_get(mgr):
    await mgr.create("j1", template_id="t1", total=5)
    job = await mgr.get("j1")
    assert job.job_id == "j1"
    assert job.status == "pending"
    assert job.total == 5
    assert job.done == 0


async def test_update_progress(mgr):
    await mgr.create("j1", template_id="t1", total=3)
    await mgr.update("j1", done=1, current_file="a.jpg")
    job = await mgr.get("j1")
    assert job.status == "processing"
    assert job.done == 1
    assert job.current_file == "a.jpg"


async def test_fail_file_accumulates(mgr):
    await mgr.create("j1", template_id="t1", total=3)
    await mgr.fail_file("j1", "bad.jpg")
    await mgr.fail_file("j1", "bad2.jpg")
    job = await mgr.get("j1")
    assert "bad.jpg" in job.failed_files
    assert "bad2.jpg" in job.failed_files


async def test_complete(mgr):
    await mgr.create("j1", template_id="t1", total=2)
    await mgr.complete("j1", download_url="/jobs/j1/result")
    job = await mgr.get("j1")
    assert job.status == "completed"
    assert job.download_url == "/jobs/j1/result"


async def test_fail_job(mgr):
    await mgr.create("j1", template_id="t1", total=1)
    await mgr.fail("j1", error="Ollama timeout")
    job = await mgr.get("j1")
    assert job.status == "failed"
    assert job.error == "Ollama timeout"


async def test_get_nonexistent_raises(mgr):
    with pytest.raises(KeyError):
        await mgr.get("nonexistent")
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
source .venv/bin/activate && pytest tests/test_job_manager.py -v
```
Expected: `ImportError`

- [ ] **Step 3: `app/core/job_manager.py` 작성**

```python
import asyncio

from app.schemas.job import JobProgress


class InMemoryJobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobProgress] = {}
        self._lock = asyncio.Lock()

    async def create(self, job_id: str, template_id: str, total: int) -> None:
        async with self._lock:
            self._jobs[job_id] = JobProgress(
                job_id=job_id,
                template_id=template_id,
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
    ) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            self._jobs[job_id] = job.model_copy(update={
                "status": "completed",
                "done": job.total,
                "current_file": None,
                "download_url": download_url,
                "pdf_url": pdf_url,
            })

    async def fail(self, job_id: str, error: str) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            self._jobs[job_id] = job.model_copy(update={
                "status": "failed",
                "error": error,
            })

    async def get(self, job_id: str) -> JobProgress:
        async with self._lock:
            if job_id not in self._jobs:
                raise KeyError(f"Job {job_id!r} not found")
            return self._jobs[job_id]
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
source .venv/bin/activate && pytest tests/test_job_manager.py -v
```
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add app/core/job_manager.py tests/test_job_manager.py
git commit -m "feat: InMemoryJobManager — async job state management"
```

---

## Task 2: OllamaClient

**Files:**
- Create: `app/services/ollama_client.py`
- Create: `tests/test_ollama_client.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_ollama_client.py`:
```python
import json
import pytest
import respx
import httpx
from app.services.ollama_client import OllamaClient
from app.services.preprocessor import ProcessedInput


MOCK_BASE = "http://localhost:11434"


@pytest.fixture
def client():
    return OllamaClient(base_url=MOCK_BASE, model="gemma4")


@pytest.fixture
def image_input():
    return ProcessedInput(
        source_name="test.jpg",
        source_page=0,
        image_b64="aGVsbG8=",
        text=None,
        pil_image=None,
    )


@pytest.fixture
def text_input():
    return ProcessedInput(
        source_name="data.xlsx",
        source_page=0,
        image_b64=None,
        text="날짜\t금액\n2024-01-15\t5500",
        pil_image=None,
    )


VALID_RECEIPT_JSON = json.dumps({
    "날짜": "2024-01-15",
    "업체명": "스타벅스",
    "품목": "아메리카노",
    "금액": 5500,
    "부가세": 500,
    "결제수단": "카드",
    "비고": None,
})


@respx.mock
async def test_extract_receipt_image_path(client, image_input):
    respx.post(f"{MOCK_BASE}/api/generate").mock(
        return_value=httpx.Response(200, json={"response": VALID_RECEIPT_JSON})
    )
    receipt = await client.extract_receipt(image_input, "당신은 전문가입니다.")
    assert receipt.업체명 == "스타벅스"
    assert receipt.금액 == 5500


@respx.mock
async def test_extract_receipt_text_path(client, text_input):
    respx.post(f"{MOCK_BASE}/api/generate").mock(
        return_value=httpx.Response(200, json={"response": VALID_RECEIPT_JSON})
    )
    receipt = await client.extract_receipt(text_input, "당신은 전문가입니다.")
    assert receipt.결제수단 == "카드"


@respx.mock
async def test_health_check_ok(client):
    respx.get(f"{MOCK_BASE}/api/tags").mock(
        return_value=httpx.Response(200, json={"models": []})
    )
    assert await client.health_check() is True


@respx.mock
async def test_health_check_fail(client):
    respx.get(f"{MOCK_BASE}/api/tags").mock(side_effect=httpx.ConnectError("refused"))
    assert await client.health_check() is False
```

> `respx` 패키지 필요: `pip install respx` 후 `requirements.txt` 에 추가

- [ ] **Step 2: respx 설치 및 requirements.txt 업데이트**

```bash
source .venv/bin/activate && pip install respx
```

`requirements.txt` 하단에 추가:
```
respx
```

- [ ] **Step 3: 테스트 실행 — 실패 확인**

```bash
source .venv/bin/activate && pytest tests/test_ollama_client.py -v
```
Expected: `ImportError`

- [ ] **Step 4: `app/services/ollama_client.py` 작성**

```python
import httpx

from app.schemas.receipt import ReceiptData
from app.services.preprocessor import ProcessedInput


class OllamaClient:
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url
        self.model = model

    async def extract_receipt(
        self,
        input: ProcessedInput,
        system_prompt: str,
    ) -> ReceiptData:
        payload: dict = {
            "model": self.model,
            "system": system_prompt,
            "stream": False,
            "format": "json",
        }
        if input.image_b64:
            payload["prompt"] = "이 영수증에서 데이터를 추출하세요."
            payload["images"] = [input.image_b64]
        else:
            payload["prompt"] = input.text or ""

        async with httpx.AsyncClient(timeout=120.0) as http:
            resp = await http.post(f"{self.base_url}/api/generate", json=payload)
            resp.raise_for_status()
            raw = resp.json()["response"]
            return ReceiptData.model_validate_json(raw)

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as http:
                resp = await http.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False
```

- [ ] **Step 5: 테스트 실행 — 통과 확인**

```bash
source .venv/bin/activate && pytest tests/test_ollama_client.py -v
```
Expected: `4 passed`

- [ ] **Step 6: Commit**

```bash
git add app/services/ollama_client.py tests/test_ollama_client.py requirements.txt
git commit -m "feat: OllamaClient — Gemma4 VLM image/text extraction via Ollama REST"
```

---

## Task 3: BatchProcessor (OCR 파이프라인)

**Files:**
- Create: `app/services/batch_processor.py`
- Create: `tests/test_batch_processor.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_batch_processor.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.batch_processor import run_job
from app.core.job_manager import InMemoryJobManager
from app.services.preprocessor import ProcessedInput
from app.schemas.receipt import ReceiptData


def make_input(name: str, page: int = 0) -> ProcessedInput:
    return ProcessedInput(
        source_name=name, source_page=page,
        image_b64="aGVsbG8=", text=None, pil_image=None,
    )


def make_receipt() -> ReceiptData:
    return ReceiptData(
        날짜="2024-01-15", 업체명="스타벅스", 품목="아메리카노",
        금액=5500, 부가세=500, 결제수단="카드",
    )


async def test_run_job_completes(tmp_data_dir):
    mgr = InMemoryJobManager()
    await mgr.create("j1", template_id="", total=2)

    ollama = MagicMock()
    ollama.extract_receipt = AsyncMock(return_value=make_receipt())

    config = MagicMock()
    config.ollama_system_prompt = "prompt"
    config.data_dir = tmp_data_dir

    inputs = [make_input("a.jpg"), make_input("b.jpg")]
    await run_job("j1", inputs, mgr, ollama, config)

    job = await mgr.get("j1")
    assert job.status == "completed"
    assert job.done == 2


async def test_run_job_records_failed_file(tmp_data_dir):
    mgr = InMemoryJobManager()
    await mgr.create("j1", template_id="", total=2)

    ollama = MagicMock()
    ollama.extract_receipt = AsyncMock(side_effect=Exception("timeout"))

    config = MagicMock()
    config.ollama_system_prompt = "prompt"
    config.data_dir = tmp_data_dir

    inputs = [make_input("a.jpg"), make_input("b.jpg")]
    await run_job("j1", inputs, mgr, ollama, config)

    job = await mgr.get("j1")
    assert job.status == "completed"
    assert len(job.failed_files) == 2
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
source .venv/bin/activate && pytest tests/test_batch_processor.py -v
```
Expected: `ImportError`

- [ ] **Step 3: `app/services/batch_processor.py` 작성**

```python
from app.core.job_manager import InMemoryJobManager
from app.services.ollama_client import OllamaClient
from app.services.preprocessor import ProcessedInput
from app.core.config import Config


async def run_job(
    job_id: str,
    inputs: list[ProcessedInput],
    job_manager: InMemoryJobManager,
    ollama: OllamaClient,
    config: Config,
) -> None:
    try:
        for i, processed in enumerate(inputs):
            await job_manager.update(job_id, done=i, current_file=processed.source_name)
            try:
                await ollama.extract_receipt(processed, config.ollama_system_prompt)
            except Exception:
                label = f"{processed.source_name}:p{processed.source_page}"
                await job_manager.fail_file(job_id, label)

        await job_manager.complete(job_id)
    except Exception as e:
        await job_manager.fail(job_id, str(e))
```

> Phase 3에서 엑셀 쓰기를 추가할 때 이 파일을 수정한다.

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
source .venv/bin/activate && pytest tests/test_batch_processor.py -v
```
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add app/services/batch_processor.py tests/test_batch_processor.py
git commit -m "feat: BatchProcessor — sequential OCR pipeline with per-file error handling"
```

---

## Task 4: deps.py 업데이트 + POST /jobs 백그라운드 태스크 + SSE

**Files:**
- Modify: `app/api/deps.py`
- Modify: `app/api/routes/jobs.py`

- [ ] **Step 1: `app/api/deps.py` 수정**

```python
from app.core.config import get_config
from app.core.job_manager import InMemoryJobManager
from app.services.ollama_client import OllamaClient

_job_manager: InMemoryJobManager | None = None


def get_job_manager() -> InMemoryJobManager:
    global _job_manager
    if _job_manager is None:
        _job_manager = InMemoryJobManager()
    return _job_manager


def get_ollama_client() -> OllamaClient:
    config = get_config()
    return OllamaClient(base_url=config.ollama_base_url, model=config.ollama_model)
```

- [ ] **Step 2: `app/api/routes/jobs.py` 전체 교체**

```python
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

    background_tasks.add_task(
        run_job, job_id, all_inputs, job_manager, ollama, config,
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
```

- [ ] **Step 3: 업로드 테스트 여전히 통과 확인**

```bash
source .venv/bin/activate && pytest tests/test_upload.py -v
```
Expected: `3 passed`

- [ ] **Step 4: 전체 테스트 통과 확인**

```bash
source .venv/bin/activate && pytest -v
```
Expected: `모든 테스트 passed` (job_manager 6 + ollama_client 4 + batch_processor 2 + 기존)

- [ ] **Step 5: 수동 SSE 확인**

```bash
source .venv/bin/activate && uvicorn app.main:app --reload
```

새 터미널:
```bash
JOB=$(curl -s -X POST http://localhost:8000/jobs \
  -F "files=@tests/fixtures/sample.jpg" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
curl -N "http://localhost:8000/jobs/${JOB}/stream"
```
Expected (Ollama 미설치 시):
```
retry: 60000

data: {"job_id":"...","status":"processing",...}

data: {"job_id":"...","status":"failed","error":"..."}
```

Expected (Ollama 설치 + gemma4 실행 중):
```
retry: 60000

data: {"job_id":"...","status":"processing","done":0,...}

data: {"job_id":"...","status":"completed","done":1,...}
```

- [ ] **Step 6: Commit**

```bash
git add app/api/deps.py app/api/routes/jobs.py
git commit -m "feat: POST /jobs launches background OCR task; GET /jobs/{id}/stream SSE"
```

---

## Self-Review

| 스펙 요구사항 | 구현 태스크 |
|--------------|------------|
| asyncio 기반 순차 처리 (CPU 과부하 방지) | Task 3 — for 루프 순차 실행 |
| SSE retry: 60000 | Task 4 — event_gen 첫 줄 |
| 부분 실패 허용 — 실패 파일만 기록 | Task 3 — fail_file per item |
| Ollama model 하드코딩 금지 | Task 2 — OllamaClient 생성자 주입 |
| system_prompt 계층 (template > env) | Task 3 — config.ollama_system_prompt (Phase 3에서 template prompt 오버라이드 추가) |
| 영수증 1장당 최대 120초 타임아웃 | Task 2 — httpx timeout=120.0 |

**플레이스홀더 없음.**  
**타입 일관성** — `run_job(job_id, inputs, job_manager, ollama, config)` 시그니처가 Task 3 구현과 Task 4 호출에서 동일.
