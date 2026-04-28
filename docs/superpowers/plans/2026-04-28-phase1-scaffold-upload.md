# Phase 1 — Scaffold, Schemas, Preprocessors, Upload Endpoint

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 프로젝트 기반 구성, Pydantic 스키마 3종, 파일 전처리기 4종(이미지/PDF/xlsx/pptx), FastAPI 서버 기동, 파일 업로드 엔드포인트를 구현한다.

**Architecture:** `route_file(bytes, filename) → list[ProcessedInput]` 디스패처를 중심으로 포맷별 전처리기를 독립 모듈로 분리한다. Phase 1 FastAPI는 POST /jobs 엔드포인트 하나만 구현하여 파일을 수신하고 페이지 분해 결과를 반환한다. 실제 OCR은 Phase 2에서 추가한다.

**Tech Stack:** Python 3.11+, FastAPI, Pillow, pymupdf (fitz), python-pptx, openpyxl, pydantic-settings, pytest, httpx (TestClient)

> **이전 플랜 대체:** 기존 `2026-04-28-phase1-foundation.md` 를 본 문서가 대체한다.

---

**Definition of Done:**
```bash
source .venv/bin/activate && uvicorn app.main:app --reload
# 새 터미널:
curl -s -X POST http://localhost:8000/jobs \
  -F "files=@tests/fixtures/sample.jpg" | python3 -m json.tool
# 기대 출력: {"files": [{"name": "sample.jpg", "pages": 1}], "total_pages": 1}
```

---

## 파일 구조

```
app/
  __init__.py                        (이미 존재)
  main.py                            (NEW)
  core/
    __init__.py                      (이미 존재)
    config.py                        (이미 존재 — 수정 불필요)
  schemas/
    __init__.py                      (이미 존재 — 빈 파일)
    receipt.py                       (NEW)
    template.py                      (NEW)
    job.py                           (NEW)
  api/
    __init__.py                      (NEW)
    deps.py                          (NEW — Phase 1: 빈 stub)
    routes/
      __init__.py                    (NEW)
      jobs.py                        (NEW)
  services/
    __init__.py                      (이미 존재)
    preprocessor/
      __init__.py                    (이미 존재 — 빈 파일, 덮어씀)
      image.py                       (NEW)
      pdf.py                         (NEW)
      spreadsheet.py                 (NEW)
      presentation.py                (NEW)

tests/
  conftest.py                        (이미 존재)
  fixtures/
    sample.jpg                       (NEW — 테스트용 더미 이미지)
  test_schemas.py                    (NEW)
  test_preprocessor.py               (NEW)
  test_upload.py                     (NEW)
```

---

## Task 1: Pydantic 스키마 3종

**Files:**
- Create: `app/schemas/receipt.py`
- Create: `app/schemas/template.py`
- Create: `app/schemas/job.py`
- Create: `tests/test_schemas.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_schemas.py`:
```python
import pytest
from datetime import datetime
from app.schemas.receipt import ReceiptData
from app.schemas.template import Template
from app.schemas.job import JobProgress


def test_receipt_valid():
    r = ReceiptData(날짜="2024-01-15", 업체명="스타벅스", 품목="아메리카노",
                    금액=5500, 부가세=500, 결제수단="카드")
    assert r.비고 is None


def test_receipt_invalid_payment():
    with pytest.raises(Exception):
        ReceiptData(날짜="2024-01-15", 업체명="A", 품목="B",
                    금액=0, 부가세=0, 결제수단="비트코인")


def test_template_has_custom_prompt_false():
    t = Template(template_id="tpl_1", name="지출결의서",
                 fields=["날짜", "금액"], custom_prompt=None,
                 created_at=datetime.utcnow())
    assert t.has_custom_prompt is False


def test_template_has_custom_prompt_true():
    t = Template(template_id="tpl_1", name="지출결의서",
                 fields=["날짜"], custom_prompt="extract",
                 created_at=datetime.utcnow())
    assert t.has_custom_prompt is True


def test_job_defaults():
    j = JobProgress(job_id="j1", template_id="t1",
                    status="pending", total=10, done=0)
    assert j.failed_files == []
    assert j.pdf_url is None
    assert j.download_url is None
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
source .venv/bin/activate && pytest tests/test_schemas.py -v
```
Expected: `ImportError` (모듈 미존재)

- [ ] **Step 3: `app/schemas/receipt.py` 작성**

```python
from typing import Literal
from pydantic import BaseModel


class ReceiptData(BaseModel):
    날짜: str
    업체명: str
    품목: str
    금액: int
    부가세: int
    결제수단: Literal["카드", "현금", "계좌이체", "기타"]
    비고: str | None = None
```

- [ ] **Step 4: `app/schemas/template.py` 작성**

```python
from datetime import datetime
from pydantic import BaseModel, computed_field


class Template(BaseModel):
    template_id: str
    name: str
    fields: list[str]
    custom_prompt: str | None
    created_at: datetime

    @computed_field
    @property
    def has_custom_prompt(self) -> bool:
        return self.custom_prompt is not None
```

- [ ] **Step 5: `app/schemas/job.py` 작성**

```python
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
```

- [ ] **Step 6: 테스트 실행 — 통과 확인**

```bash
source .venv/bin/activate && pytest tests/test_schemas.py -v
```
Expected: `5 passed`

- [ ] **Step 7: Commit**

```bash
git add app/schemas/ tests/test_schemas.py
git commit -m "feat: Pydantic schemas — ReceiptData, Template, JobProgress"
```

---

## Task 2: ProcessedInput 타입 & route_file() 디스패처

**Files:**
- Modify: `app/services/preprocessor/__init__.py`
- Modify: `tests/test_preprocessor.py` (새로 작성)

- [ ] **Step 1: 테스트 작성**

`tests/test_preprocessor.py`:
```python
import io
import pytest
from PIL import Image as PilImage
from app.services.preprocessor import ProcessedInput, route_file


def test_unsupported_extension_raises():
    with pytest.raises(ValueError, match="Unsupported"):
        route_file(b"data", "document.txt")


def test_processed_input_fields():
    pi = ProcessedInput(
        source_name="test.jpg",
        source_page=0,
        image_b64="abc",
        text=None,
        pil_image=None,
    )
    assert pi.source_name == "test.jpg"
    assert pi.text is None
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
source .venv/bin/activate && pytest tests/test_preprocessor.py::test_unsupported_extension_raises -v
```
Expected: `ImportError`

- [ ] **Step 3: `app/services/preprocessor/__init__.py` 작성**

```python
from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path

from PIL.Image import Image as PilImage


@dataclass
class ProcessedInput:
    source_name: str        # 원본 파일명 (로그·오류 추적용)
    source_page: int        # 페이지/슬라이드 번호 (단일 파일은 0)
    image_b64: str | None   # base64 인코딩 이미지 (VLM 전송용)
    text: str | None        # 직접 추출 텍스트 (xlsx 전용)
    pil_image: PilImage | None  # 증적 PDF 병합용 원본 이미지 (xlsx은 None)


def route_file(file_bytes: bytes, filename: str) -> list[ProcessedInput]:
    suffix = Path(filename).suffix.lower()
    if suffix in (".jpg", ".jpeg", ".png"):
        from .image import process_image
        return process_image(file_bytes, filename)
    elif suffix == ".pdf":
        from .pdf import process_pdf
        return process_pdf(file_bytes, filename)
    elif suffix == ".xlsx":
        from .spreadsheet import process_spreadsheet
        return process_spreadsheet(file_bytes, filename)
    elif suffix == ".pptx":
        from .presentation import process_presentation
        return process_presentation(file_bytes, filename)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
source .venv/bin/activate && pytest tests/test_preprocessor.py -v
```
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add app/services/preprocessor/__init__.py tests/test_preprocessor.py
git commit -m "feat: ProcessedInput dataclass and route_file dispatcher"
```

---

## Task 3: 이미지 전처리기 (jpg/png)

**Files:**
- Create: `app/services/preprocessor/image.py`
- Modify: `tests/test_preprocessor.py` (테스트 추가)

- [ ] **Step 1: 테스트 추가**

`tests/test_preprocessor.py` 하단에 추가:
```python
@pytest.fixture
def white_jpg_bytes() -> bytes:
    img = PilImage.new("RGB", (100, 80), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def white_png_bytes() -> bytes:
    img = PilImage.new("RGB", (60, 40), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_jpg_returns_single_input(white_jpg_bytes):
    results = route_file(white_jpg_bytes, "receipt.jpg")
    assert len(results) == 1
    r = results[0]
    assert r.source_name == "receipt.jpg"
    assert r.source_page == 0
    assert r.image_b64 is not None
    assert r.text is None
    assert r.pil_image is not None


def test_png_base64_decodable(white_png_bytes):
    import base64
    results = route_file(white_png_bytes, "scan.png")
    decoded = base64.b64decode(results[0].image_b64)
    assert len(decoded) > 0
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
source .venv/bin/activate && pytest tests/test_preprocessor.py::test_jpg_returns_single_input -v
```
Expected: `FAILED` (ImportError)

- [ ] **Step 3: `app/services/preprocessor/image.py` 작성**

```python
import base64
import io

from PIL import Image

from . import ProcessedInput


def process_image(file_bytes: bytes, source_name: str) -> list[ProcessedInput]:
    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return [ProcessedInput(
        source_name=source_name,
        source_page=0,
        image_b64=b64,
        text=None,
        pil_image=img,
    )]
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
source .venv/bin/activate && pytest tests/test_preprocessor.py -v
```
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add app/services/preprocessor/image.py tests/test_preprocessor.py
git commit -m "feat: image preprocessor (jpg/png → ProcessedInput)"
```

---

## Task 4: PDF 전처리기 (pymupdf)

**Files:**
- Create: `app/services/preprocessor/pdf.py`
- Modify: `tests/test_preprocessor.py` (테스트 추가)

- [ ] **Step 1: 테스트 추가**

`tests/test_preprocessor.py` 하단에 추가:
```python
@pytest.fixture
def two_page_pdf_bytes() -> bytes:
    import fitz
    doc = fitz.open()
    for i in range(2):
        page = doc.new_page(width=200, height=150)
        page.insert_text((50, 75), f"Page {i + 1}")
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def test_pdf_one_input_per_page(two_page_pdf_bytes):
    results = route_file(two_page_pdf_bytes, "invoice.pdf")
    assert len(results) == 2


def test_pdf_page_metadata(two_page_pdf_bytes):
    results = route_file(two_page_pdf_bytes, "invoice.pdf")
    assert results[0].source_page == 0
    assert results[1].source_page == 1
    assert results[0].image_b64 is not None
    assert results[0].pil_image is not None
    assert results[0].text is None
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
source .venv/bin/activate && pytest tests/test_preprocessor.py::test_pdf_one_input_per_page -v
```
Expected: `FAILED` (ImportError)

- [ ] **Step 3: `app/services/preprocessor/pdf.py` 작성**

```python
import base64
import io

import fitz  # pymupdf
from PIL import Image

from . import ProcessedInput


def process_pdf(file_bytes: bytes, source_name: str) -> list[ProcessedInput]:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    results: list[ProcessedInput] = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))  # 2× 해상도
        img_bytes = pix.tobytes("png")
        b64 = base64.b64encode(img_bytes).decode()
        pil_img = Image.open(io.BytesIO(img_bytes)).copy()
        results.append(ProcessedInput(
            source_name=source_name,
            source_page=page_num,
            image_b64=b64,
            text=None,
            pil_image=pil_img,
        ))
    doc.close()
    return results
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
source .venv/bin/activate && pytest tests/test_preprocessor.py -v
```
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add app/services/preprocessor/pdf.py tests/test_preprocessor.py
git commit -m "feat: PDF preprocessor — per-page image extraction via pymupdf"
```

---

## Task 5: Spreadsheet 전처리기 (openpyxl)

**Files:**
- Create: `app/services/preprocessor/spreadsheet.py`
- Modify: `tests/test_preprocessor.py` (테스트 추가)

- [ ] **Step 1: 테스트 추가**

`tests/test_preprocessor.py` 하단에 추가:
```python
@pytest.fixture
def simple_xlsx_bytes() -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "날짜"
    ws["B1"] = "금액"
    ws["A2"] = "2024-01-15"
    ws["B2"] = 5500
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_xlsx_returns_single_text_input(simple_xlsx_bytes):
    results = route_file(simple_xlsx_bytes, "data.xlsx")
    assert len(results) == 1
    r = results[0]
    assert r.image_b64 is None
    assert r.pil_image is None
    assert r.text is not None
    assert "5500" in r.text
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
source .venv/bin/activate && pytest tests/test_preprocessor.py::test_xlsx_returns_single_text_input -v
```
Expected: `FAILED`

- [ ] **Step 3: `app/services/preprocessor/spreadsheet.py` 작성**

```python
import io

from openpyxl import load_workbook

from . import ProcessedInput


def process_spreadsheet(file_bytes: bytes, source_name: str) -> list[ProcessedInput]:
    wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    lines: list[str] = []
    for sheet in wb.worksheets:
        lines.append(f"[Sheet: {sheet.title}]")
        for row in sheet.iter_rows(values_only=True):
            cells = "\t".join(str(v) if v is not None else "" for v in row)
            if cells.strip():
                lines.append(cells)
    wb.close()
    return [ProcessedInput(
        source_name=source_name,
        source_page=0,
        image_b64=None,
        text="\n".join(lines),
        pil_image=None,
    )]
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
source .venv/bin/activate && pytest tests/test_preprocessor.py -v
```
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add app/services/preprocessor/spreadsheet.py tests/test_preprocessor.py
git commit -m "feat: spreadsheet preprocessor — xlsx text extraction"
```

---

## Task 6: Presentation 전처리기 (python-pptx)

**Files:**
- Create: `app/services/preprocessor/presentation.py`
- Modify: `tests/test_preprocessor.py` (테스트 추가)

- [ ] **Step 1: 테스트 추가**

`tests/test_preprocessor.py` 하단에 추가:
```python
@pytest.fixture
def two_slide_pptx_bytes() -> bytes:
    from pptx import Presentation as Prs
    from pptx.util import Inches
    prs = Prs()
    for i in range(2):
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        tb = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(2))
        tb.text_frame.text = f"영수증 {i + 1}\n금액: {(i + 1) * 1000}원"
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def test_pptx_one_input_per_slide(two_slide_pptx_bytes):
    results = route_file(two_slide_pptx_bytes, "slides.pptx")
    assert len(results) == 2


def test_pptx_text_extracted(two_slide_pptx_bytes):
    results = route_file(two_slide_pptx_bytes, "slides.pptx")
    assert "영수증 1" in results[0].text
    assert "영수증 2" in results[1].text
    assert results[0].source_page == 0
    assert results[1].source_page == 1
    assert results[0].pil_image is None  # 텍스트 경로: 이미지 없음
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
source .venv/bin/activate && pytest tests/test_preprocessor.py::test_pptx_one_input_per_slide -v
```
Expected: `FAILED`

- [ ] **Step 3: `app/services/preprocessor/presentation.py` 작성**

```python
import base64
import io

from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from . import ProcessedInput


def process_presentation(file_bytes: bytes, source_name: str) -> list[ProcessedInput]:
    prs = Presentation(io.BytesIO(file_bytes))
    results: list[ProcessedInput] = []

    for slide_num, slide in enumerate(prs.slides):
        embedded_images: list[Image.Image] = []
        text_parts: list[str] = []

        for shape in slide.shapes:
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                img = Image.open(io.BytesIO(shape.image.blob))
                embedded_images.append(img)
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    t = para.text.strip()
                    if t:
                        text_parts.append(t)

        if embedded_images:
            img = embedded_images[0].convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            results.append(ProcessedInput(
                source_name=source_name,
                source_page=slide_num,
                image_b64=b64,
                text=None,
                pil_image=img.copy(),
            ))
        elif text_parts:
            results.append(ProcessedInput(
                source_name=source_name,
                source_page=slide_num,
                image_b64=None,
                text="\n".join(text_parts),
                pil_image=None,
            ))

    return results
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
source .venv/bin/activate && pytest tests/test_preprocessor.py -v
```
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add app/services/preprocessor/presentation.py tests/test_preprocessor.py
git commit -m "feat: PPTX preprocessor — text and embedded-image extraction per slide"
```

---

## Task 7: FastAPI 앱 + 업로드 엔드포인트

**Files:**
- Create: `app/main.py`
- Create: `app/api/__init__.py`
- Create: `app/api/deps.py`
- Create: `app/api/routes/__init__.py`
- Create: `app/api/routes/jobs.py`
- Create: `tests/fixtures/` (디렉토리)
- Create: `tests/test_upload.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_upload.py`:
```python
import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@pytest.fixture
def jpg_bytes() -> bytes:
    img = Image.new("RGB", (100, 80), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_upload_single_image(client, jpg_bytes):
    resp = client.post(
        "/jobs",
        files={"files": ("receipt.jpg", jpg_bytes, "image/jpeg")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_pages"] == 1
    assert data["files"][0]["name"] == "receipt.jpg"
    assert data["files"][0]["pages"] == 1


def test_upload_unsupported_type(client):
    resp = client.post(
        "/jobs",
        files={"files": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 422


def test_upload_multiple_files(client, jpg_bytes):
    resp = client.post(
        "/jobs",
        files=[
            ("files", ("a.jpg", jpg_bytes, "image/jpeg")),
            ("files", ("b.jpg", jpg_bytes, "image/jpeg")),
        ],
    )
    assert resp.status_code == 200
    assert resp.json()["total_pages"] == 2
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
source .venv/bin/activate && pytest tests/test_upload.py -v
```
Expected: `ImportError`

- [ ] **Step 3: `app/api/__init__.py` 생성 (빈 파일)**

```bash
touch app/api/__init__.py app/api/routes/__init__.py
```

- [ ] **Step 4: `app/api/deps.py` 작성 (Phase 1: 빈 stub)**

```python
# Phase 2에서 JobManager, OllamaClient 추가 예정
```

- [ ] **Step 5: `app/api/routes/jobs.py` 작성**

```python
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.preprocessor import route_file

router = APIRouter()


@router.post("")
async def create_job(files: list[UploadFile] = File(...)):
    summary = []
    for f in files:
        content = await f.read()
        try:
            items = route_file(content, f.filename or "unknown")
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        summary.append({"name": f.filename, "pages": len(items)})
    return {"files": summary, "total_pages": sum(s["pages"] for s in summary)}
```

- [ ] **Step 6: `app/main.py` 작성**

```python
from fastapi import FastAPI

from app.api.routes import jobs

app = FastAPI(title="Receipt to Excel")

app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
```

- [ ] **Step 7: 테스트 실행 — 통과 확인**

```bash
source .venv/bin/activate && pytest tests/test_upload.py -v
```
Expected: `3 passed`

- [ ] **Step 8: 전체 테스트 통과 확인**

```bash
source .venv/bin/activate && pytest -v
```
Expected: `17 passed` (schemas 5 + preprocessor 9 + upload 3)

- [ ] **Step 9: 서버 기동 및 수동 확인**

```bash
source .venv/bin/activate && uvicorn app.main:app --reload
```

새 터미널에서:
```bash
# 테스트 이미지 생성
python3 -c "
from PIL import Image; import io
img = Image.new('RGB', (200, 150), 'white')
img.save('tests/fixtures/sample.jpg')
print('sample.jpg created')
"
curl -s -X POST http://localhost:8000/jobs \
  -F "files=@tests/fixtures/sample.jpg" | python3 -m json.tool
```
Expected:
```json
{
    "files": [{"name": "sample.jpg", "pages": 1}],
    "total_pages": 1
}
```

- [ ] **Step 10: Commit**

```bash
mkdir -p tests/fixtures
git add app/main.py app/api/ tests/test_upload.py tests/fixtures/
git commit -m "feat: FastAPI app skeleton and POST /jobs file upload endpoint"
```

---

## Self-Review

| 스펙 요구사항 | 구현 태스크 |
|--------------|------------|
| JPG/PNG → base64 + PIL.Image | Task 3 — image.py |
| PDF → 페이지별 ProcessedInput | Task 4 — pdf.py (2× 해상도) |
| xlsx → 텍스트 직렬화 | Task 5 — spreadsheet.py |
| PPTX → 슬라이드별 (이미지 or 텍스트) | Task 6 — presentation.py |
| ProcessedInput.pil_image (증적 PDF용) | Task 2 — dataclass 정의 |
| Unsupported 타입 → 422 | Task 7 — jobs.py except ValueError |
| config.ollama_model (하드코딩 금지) | config.py 기존 구현 유지 |

**플레이스홀더 없음** — 모든 단계에 완전한 코드 포함.  
**타입 일관성** — `route_file(bytes, str) → list[ProcessedInput]` 모든 태스크에서 동일 시그니처 사용.
