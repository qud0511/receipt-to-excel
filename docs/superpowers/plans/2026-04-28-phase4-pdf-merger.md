# Phase 4 — PDF Merger (증적용 영수증 모음 PDF)

> ⚠️ **[2026-04-29 업데이트]** 구현 방향 변경 사항:
> - **파일 경로**: `config.data_dir / "jobs" / job_id` → `FileSystemManager.from_config(data_dir, user_id)` 사용
>   - `fs.evidence_pdf(job_id)` → 일반 PDF, `fs.evidence_nup_pdf(job_id)` → N-up PDF
> - **N-up PDF 추가**: A4@150DPI(1240×1754px) 기준 2×2 격자 배치. 별도 엔드포인트 `GET /jobs/{id}/result/pdf/nup`
> - **JobProgress**: `pdf_url`, `nup_pdf_url` 모두 포함 (완료 시 두 URL 모두 설정)
> - **`make_nup_pdf(pdf_pages, nup_path, cols=2, rows=2)`** 함수를 `batch_processor.py` 또는 `pdf_merger.py`에 추가
> - **user_id 격리**: 잡별로 `data/users/{user_id}/jobs/{job_id}/` 하위에 저장

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 배치 처리 중 수집된 PIL.Image 목록을 하나의 PDF로 병합하는 PdfMerger를 구현하고, BatchProcessor와 다운로드 엔드포인트에 통합한다. xlsx와 증적용 PDF를 동시에 다운로드 가능한 상태.

**Architecture:** `PdfMerger.merge()` 는 PIL.Image 리스트를 RGB로 변환 후 Pillow의 `save(save_all=True)` 로 단일 PDF를 생성한다. BatchProcessor는 OCR 루프에서 `pil_image` 가 있는 항목만 수집하고, 마지막에 `merge_to_pdf()` 를 호출한다. xlsx-only 입력(pil_image=None)은 PDF에 포함되지 않는다.

**Tech Stack:** Pillow (PDF save), FastAPI FileResponse

**전제:** Phase 3 완료

---

**Definition of Done:**
```bash
# 서버 기동 + 영수증 업로드 (Phase 3 DoD와 동일 절차)
JOB="..."  # 완료된 job_id

# xlsx 다운로드
curl -OJ "http://localhost:8000/jobs/$JOB/result"

# PDF 다운로드 (이미지/PDF 입력이 있었을 때)
curl -OJ "http://localhost:8000/jobs/$JOB/result/pdf"
# → 증적용_영수증_모음_$JOB.pdf 생성 확인

# xlsx-only 업로드 시 PDF 404 반환 확인
curl -s http://localhost:8000/jobs/$JOB/result/pdf  # → 404
```

---

## 파일 구조

```
app/
  services/
    pdf_merger.py                    (NEW)
    batch_processor.py               (MODIFY — pdf_pages 수집 + merge 호출)
  api/
    routes/
      jobs.py                        (MODIFY — GET /jobs/{id}/result/pdf 추가)

tests/
  test_pdf_merger.py                 (NEW)
```

---

## Task 1: PdfMerger

**Files:**
- Create: `app/services/pdf_merger.py`
- Create: `tests/test_pdf_merger.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_pdf_merger.py`:
```python
import io
import pytest
from pathlib import Path
from PIL import Image
from app.services.pdf_merger import merge_to_pdf


def make_image(color: str = "white", size: tuple = (200, 150)) -> Image.Image:
    return Image.new("RGB", size, color=color)


def test_merge_single_image(tmp_path):
    out = tmp_path / "out.pdf"
    merge_to_pdf([make_image("red")], out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_merge_multiple_images(tmp_path):
    out = tmp_path / "out.pdf"
    images = [make_image("red"), make_image("blue"), make_image("green")]
    merge_to_pdf(images, out)
    assert out.exists()


def test_merge_empty_list_does_not_create_file(tmp_path):
    out = tmp_path / "out.pdf"
    merge_to_pdf([], out)
    assert not out.exists()


def test_merge_rgba_image_converted(tmp_path):
    out = tmp_path / "out.pdf"
    img = Image.new("RGBA", (100, 80), color=(255, 0, 0, 128))
    merge_to_pdf([img], out)
    assert out.exists()
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
source .venv/bin/activate && pytest tests/test_pdf_merger.py -v
```
Expected: `ImportError`

- [ ] **Step 3: `app/services/pdf_merger.py` 작성**

```python
from pathlib import Path

from PIL.Image import Image


def merge_to_pdf(images: list[Image], output_path: Path) -> None:
    """PIL.Image 목록을 결제일시 순서 그대로 단일 PDF로 병합.
    images가 빈 리스트면 (xlsx-only 업로드) 파일을 생성하지 않는다."""
    if not images:
        return

    rgb_images = [img.convert("RGB") for img in images]
    first, rest = rgb_images[0], rgb_images[1:]
    first.save(output_path, save_all=True, append_images=rest, format="PDF")
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
source .venv/bin/activate && pytest tests/test_pdf_merger.py -v
```
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add app/services/pdf_merger.py tests/test_pdf_merger.py
git commit -m "feat: PdfMerger — PIL.Image list to single evidence PDF via Pillow"
```

---

## Task 2: BatchProcessor PDF 통합 + GET /jobs/{id}/result/pdf

**Files:**
- Modify: `app/services/batch_processor.py`
- Modify: `app/api/routes/jobs.py`

- [ ] **Step 1: `app/services/batch_processor.py` 전체 교체**

```python
from app.core.config import Config
from app.core.job_manager import InMemoryJobManager
from app.schemas.receipt import ReceiptData
from app.services.excel_mapper import build_excel
from app.services.ollama_client import OllamaClient
from app.services.pdf_merger import merge_to_pdf
from app.services.preprocessor import ProcessedInput
from app.services.template_store import TemplateStore
from PIL.Image import Image


async def run_job(
    job_id: str,
    inputs: list[ProcessedInput],
    template_id: str,
    job_manager: InMemoryJobManager,
    ollama: OllamaClient,
    template_store: TemplateStore,
    config: Config,
) -> None:
    try:
        template = await template_store.get(template_id)
        system_prompt = template.custom_prompt or config.ollama_system_prompt
        receipts: list[ReceiptData] = []
        pdf_pages: list[Image] = []

        for i, processed in enumerate(inputs):
            await job_manager.update(job_id, done=i, current_file=processed.source_name)
            try:
                receipt = await ollama.extract_receipt(processed, system_prompt)
                receipts.append(receipt)
                if processed.pil_image is not None:
                    pdf_pages.append(processed.pil_image)
            except Exception:
                label = f"{processed.source_name}:p{processed.source_page}"
                await job_manager.fail_file(job_id, label)

        jobs_dir = config.data_dir / "jobs" / job_id
        jobs_dir.mkdir(parents=True, exist_ok=True)

        excel_path = jobs_dir / "result.xlsx"
        build_excel(template_store.template_path(template_id), excel_path, receipts)

        pdf_path = jobs_dir / "evidence.pdf"
        merge_to_pdf(pdf_pages, pdf_path)

        pdf_url = f"/jobs/{job_id}/result/pdf" if pdf_path.exists() else None
        await job_manager.complete(
            job_id,
            download_url=f"/jobs/{job_id}/result",
            pdf_url=pdf_url,
        )
    except Exception as e:
        await job_manager.fail(job_id, str(e))
```

- [ ] **Step 2: batch_processor 테스트에 pil_image 추가 확인**

`tests/test_batch_processor.py` 의 `make_input()` 에 `pil_image` 추가:

```python
from PIL import Image as PilImage

def make_input(name: str, page: int = 0, with_image: bool = True) -> ProcessedInput:
    img = PilImage.new("RGB", (10, 10), "white") if with_image else None
    return ProcessedInput(
        source_name=name, source_page=page,
        image_b64="aGVsbG8=" if with_image else None,
        text=None if with_image else "text",
        pil_image=img,
    )
```

`test_run_job_completes` 에 pdf_url 확인 추가:

```python
async def test_run_job_completes(tmp_data_dir):
    mgr = InMemoryJobManager()
    await mgr.create("j1", template_id="tpl_test", total=2)

    ollama = MagicMock()
    ollama.extract_receipt = AsyncMock(return_value=make_receipt())

    config = MagicMock()
    config.ollama_system_prompt = "prompt"
    config.data_dir = tmp_data_dir

    inputs = [make_input("a.jpg"), make_input("b.jpg")]
    await run_job("j1", inputs, "tpl_test", mgr, ollama, make_mock_store(tmp_data_dir), config)

    job = await mgr.get("j1")
    assert job.status == "completed"
    assert job.download_url == "/jobs/j1/result"
    assert job.pdf_url == "/jobs/j1/result/pdf"  # pil_image가 있으므로 PDF 생성됨
```

- [ ] **Step 3: 테스트 실행 — 통과 확인**

```bash
source .venv/bin/activate && pytest tests/test_batch_processor.py tests/test_pdf_merger.py -v
```
Expected: 모두 passed

- [ ] **Step 4: `app/api/routes/jobs.py` 에 PDF 다운로드 엔드포인트 추가**

기존 `download_excel` 함수 아래에 추가:

```python
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
        raise HTTPException(
            status_code=404,
            detail="PDF not generated (xlsx-only input has no images)",
        )

    return FileResponse(
        path=pdf_path,
        filename=f"증적용_영수증_모음_{job_id}.pdf",
        media_type="application/pdf",
    )
```

- [ ] **Step 5: 전체 테스트 통과 확인**

```bash
source .venv/bin/activate && pytest -v
```
Expected: 모든 테스트 passed

- [ ] **Step 6: Commit**

```bash
git add app/services/batch_processor.py app/api/routes/jobs.py tests/test_batch_processor.py
git commit -m "feat: PDF evidence generation integrated into BatchProcessor; GET /jobs/{id}/result/pdf"
```

---

## Self-Review

| 스펙 요구사항 | 구현 태스크 |
|--------------|------------|
| 이미지 수집 후 단일 PDF 병합 | Task 1 — `merge_to_pdf()` |
| xlsx-only 입력 → PDF 미생성 | Task 1 — `if not images: return` |
| completed 이벤트에 pdf_url 포함 | Task 2 — `job_manager.complete(pdf_url=...)` |
| 증적용 PDF 다운로드 엔드포인트 | Task 2 — `GET /jobs/{id}/result/pdf` |
| pdf_url: null (xlsx-only 시) | Task 2 — `pdf_url = ... if pdf_path.exists() else None` |

**플레이스홀더 없음.**  
**타입 일관성** — `merge_to_pdf(list[Image], Path)` Task 1 정의 ↔ Task 2 호출 동일.
