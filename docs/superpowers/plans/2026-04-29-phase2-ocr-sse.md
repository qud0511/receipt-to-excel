# Phase 2 — OllamaClient (텍스트 전용) + JobManager + SSE

> ✅ **[2026-04-29 현재 권위 문서]** `2026-04-28-phase2-ocr-sse.md`를 대체하는 최신 버전.  
> **업데이트 내역:**
> - `ReceiptData` 스키마: `가맹점명`, `카테고리: ExpenseCategory`, `프로젝트명` (구 `업체명`·`품목` 제거)
> - `InMemoryJobManager.create()`: `user_id: str = "default"` 파라미터 추가
> - `InMemoryJobManager.complete()`: `nup_pdf_url: str | None = None` 파라미터 추가
> - `JobProgress`: `user_id`, `nup_pdf_url` 필드 추가
> - **`validate_and_fix()`** (Phase 3에서 추가 예정): LLM JSON 응답 검증 + `ExtractError` — `2026-04-29-master-refactor.md` 참조

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `InMemoryJobManager` + `OllamaClient`(Docling 텍스트 전용 모드) + `BatchProcessor` + SSE 스트림 구현.
파일 업로드 → 백그라운드 OCR → SSE 실시간 진행률 확인 가능한 상태.

**Architecture:**
- `OllamaClient.extract_receipt()`: Phase 1에서 Docling이 모든 파싱/OCR을 담당하므로, 항상 `docling_text` → Ollama 텍스트 모드 단일 경로. VLM 분기 없음.
- `BatchProcessor`가 asyncio 백그라운드 태스크로 `OllamaClient`를 순차 호출.
- `GET /jobs/{id}/stream`이 1초 간격으로 잡 상태를 SSE로 push.
- 이 Phase에서는 엑셀/PDF 생성 없이 OCR 결과 수집까지만.

**Tech Stack:** Python 3.11+, FastAPI, httpx, asyncio, respx, pytest-asyncio

**전제:** Phase 1 완료 (`ProcessedInput.docling_text`, `DoclingService`, 전처리기 4개)

---

## 파일 맵

| 파일 | 작업 |
|------|------|
| `app/core/job_manager.py` | 신규 — InMemoryJobManager |
| `app/services/ollama_client.py` | 신규 — 텍스트 전용 Ollama 호출 |
| `app/services/batch_processor.py` | 신규 — 순차 OCR 오케스트레이션 |
| `app/api/deps.py` | 수정 — JobManager·OllamaClient 싱글턴 추가 |
| `app/api/routes/jobs.py` | 수정 — BackgroundTask + SSE 엔드포인트 |
| `requirements.txt` | `respx` 추가 (테스트용 HTTP mock) |
| `tests/test_job_manager.py` | 신규 |
| `tests/test_ollama_client.py` | 신규 |
| `tests/test_batch_processor.py` | 신규 |

---

## Task 1: InMemoryJobManager

**Files:**
- Create: `app/core/job_manager.py`
- Create: `tests/test_job_manager.py`

- [ ] **Step 1: 테스트 작성**

```python
# tests/test_job_manager.py
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

- [ ] **Step 2: 테스트 실패 확인**

```bash
.venv/bin/python -m pytest tests/test_job_manager.py -v
```
Expected: `ImportError` (job_manager.py 없음)

- [ ] **Step 3: `app/core/job_manager.py` 작성**

```python
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

    async def get(self, job_id: str) -> JobProgress:
        async with self._lock:
            if job_id not in self._jobs:
                raise KeyError(f"Job {job_id!r} not found")
            return self._jobs[job_id]
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
.venv/bin/python -m pytest tests/test_job_manager.py -v
```
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add app/core/job_manager.py tests/test_job_manager.py
git commit -m "feat: InMemoryJobManager — async job state management"
```

---

## Task 2: OllamaClient (텍스트 전용)

**Files:**
- Create: `app/services/ollama_client.py`
- Create: `tests/test_ollama_client.py`
- Modify: `requirements.txt`

- [ ] **Step 1: respx 설치 및 requirements.txt 추가**

```bash
.venv/bin/pip install respx
```

`requirements.txt` 하단에 추가:
```
respx
```

- [ ] **Step 2: 테스트 작성**

```python
# tests/test_ollama_client.py
import json
import pytest
import respx
import httpx
from app.services.ollama_client import OllamaClient
from app.services.preprocessor import ProcessedInput


MOCK_BASE = "http://localhost:11434"

VALID_RECEIPT_JSON = json.dumps({
    "날짜": "2024-01-15",
    "가맹점명": "스타벅스",
    "카테고리": "기타비용",
    "프로젝트명": None,
    "금액": 5500,
    "부가세": 500,
    "결제수단": "카드",
    "비고": None,
})


@pytest.fixture
def client():
    return OllamaClient(base_url=MOCK_BASE, model="gemma4")


@pytest.fixture
def text_input():
    return ProcessedInput(
        source_name="receipt.jpg",
        source_page=0,
        docling_text="업체명: 스타벅스\n금액: 5500\n결제수단: 카드",
        pil_image=None,
    )


@respx.mock
async def test_extract_receipt_sends_docling_text(client, text_input):
    route = respx.post(f"{MOCK_BASE}/api/generate").mock(
        return_value=httpx.Response(200, json={"response": VALID_RECEIPT_JSON})
    )
    receipt = await client.extract_receipt(text_input, "당신은 전문가입니다.")
    assert receipt.가맹점명 == "스타벅스"
    assert receipt.금액 == 5500
    # 요청 바디에 docling_text가 prompt로 들어갔는지 확인
    sent = json.loads(route.calls[0].request.content)
    assert sent["prompt"] == text_input.docling_text
    assert "images" not in sent  # VLM 이미지 전송 없음


@respx.mock
async def test_extract_receipt_returns_receipt_data(client, text_input):
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

- [ ] **Step 3: 테스트 실패 확인**

```bash
.venv/bin/python -m pytest tests/test_ollama_client.py -v
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
        payload = {
            "model": self.model,
            "system": system_prompt,
            "prompt": input.docling_text,  # Docling이 이미 파싱 완료 — 항상 텍스트 모드
            "stream": False,
            "format": "json",
        }
        async with httpx.AsyncClient(timeout=120.0) as http:
            resp = await http.post(f"{self.base_url}/api/generate", json=payload)
            resp.raise_for_status()
            return ReceiptData.model_validate_json(resp.json()["response"])

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as http:
                resp = await http.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
.venv/bin/python -m pytest tests/test_ollama_client.py -v
```
Expected: `4 passed`

- [ ] **Step 6: Commit**

```bash
git add app/services/ollama_client.py tests/test_ollama_client.py requirements.txt
git commit -m "feat: OllamaClient — docling_text 텍스트 전용 모드 (VLM 분기 없음)"
```

---

## Task 3: BatchProcessor

**Files:**
- Create: `app/services/batch_processor.py`
- Create: `tests/test_batch_processor.py`

- [ ] **Step 1: 테스트 작성**

```python
# tests/test_batch_processor.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.batch_processor import run_job
from app.core.job_manager import InMemoryJobManager
from app.services.preprocessor import ProcessedInput
from app.schemas.receipt import ReceiptData


def make_input(name: str, page: int = 0) -> ProcessedInput:
    return ProcessedInput(
        source_name=name,
        source_page=page,
        docling_text=f"업체명: 테스트\n금액: 1000",
        pil_image=None,
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

- [ ] **Step 2: 테스트 실패 확인**

```bash
.venv/bin/python -m pytest tests/test_batch_processor.py -v
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

> Phase 3에서 엑셀 쓰기·PDF 수집을 이 파일에 추가한다.

- [ ] **Step 4: 테스트 통과 확인**

```bash
.venv/bin/python -m pytest tests/test_batch_processor.py -v
```
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add app/services/batch_processor.py tests/test_batch_processor.py
git commit -m "feat: BatchProcessor — 순차 OCR 파이프라인, 파일별 오류 격리"
```

---

## Task 4: deps.py + POST /jobs 백그라운드 태스크 + SSE

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

- [ ] **Step 2: `app/api/routes/jobs.py` 교체**

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
```

- [ ] **Step 3: 기존 업로드 테스트 통과 확인**

```bash
.venv/bin/python -m pytest tests/test_upload.py -v
```
Expected: `3 passed`

- [ ] **Step 4: 전체 테스트 통과 확인**

```bash
.venv/bin/python -m pytest -v
```
Expected: 전체 passed (job_manager 6 + ollama_client 4 + batch_processor 2 + 기존)

- [ ] **Step 5: Commit**

```bash
git add app/api/deps.py app/api/routes/jobs.py
git commit -m "feat: POST /jobs 백그라운드 OCR 태스크; GET /jobs/{id}/stream SSE"
```

---

## 완료 기준

```bash
# 서버 기동
.venv/bin/uvicorn app.main:app --reload

# 새 터미널: 업로드 → SSE 확인
JOB=$(curl -s -X POST http://localhost:8000/jobs \
  -F "files=@tests/fixtures/sample.jpg" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
curl -N "http://localhost:8000/jobs/${JOB}/stream"
```

**Ollama 미설치 시 기대 출력:**
```
retry: 60000

data: {"job_id":"...","status":"processing","done":0,...}

data: {"job_id":"...","status":"completed","done":1,...}
```
(OllamaClient가 ConnectError → fail_file 기록 → completed로 정상 종료)
