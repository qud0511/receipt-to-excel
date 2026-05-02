# Phase 1 — Foundation: Scaffold, Config, Schemas, Preprocessors

> ⚠️ **[2026-04-29 업데이트]** 이 문서의 일부 스키마·코드는 구식입니다.  
> 현재 구현과의 차이점:
> - `ReceiptData`: `업체명`→`가맹점명`, `품목` 제거, `카테고리: ExpenseCategory` 추가, `프로젝트명` 추가
> - `ProcessedInput`: `image_b64 + text` → `docling_text` 단일 필드 (Docling 재설계)
> - `config.py`: `_DEFAULT_PROMPT`는 구식 스키마 사용 — 현재 `ollama_client.py`의 `_SYSTEM_PROMPT`가 단일 소스  
> - 전처리기: 모든 포맷이 Docling `DoclingService`로 통합됨 (`pymupdf`, `python-pptx` 직접 사용 제거)  
> **최신 스키마와 파이프라인은 `2026-04-29-master-refactor.md`를 참조하라.**

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 프로젝트 뼈대·의존성 설정, Pydantic 스키마 3종, 파일 타입별 전처리기(이미지/PDF/xlsx/pptx → `ProcessedInput`)를 구현하여 이후 OllamaClient·ExcelMapper·BatchProcessor가 의존할 기반 레이어를 완성한다.

**Architecture:** 파일 바이트 + 파일명을 받아 `ProcessedInput` 리스트를 반환하는 `route_file()` 디스패처를 중심으로, 각 포맷별 전처리기를 독립 모듈로 분리한다. PDF·PPTX는 페이지/슬라이드 단위로 분해하여 각각 1건의 영수증으로 취급한다. 설정은 `.env` 기반 Pydantic Settings로 주입한다.

**Tech Stack:** Python 3.11+, FastAPI, Pillow, pymupdf (fitz), python-pptx, openpyxl, pydantic-settings, pytest, pytest-asyncio

---

## 파일 구조

```
app/
  __init__.py
  core/
    __init__.py
    config.py              # Pydantic Settings — OLLAMA_*, DATA_DIR
  schemas/
    __init__.py
    receipt.py             # ReceiptData
    template.py            # Template (computed has_custom_prompt)
    job.py                 # JobProgress (pdf_url 포함)
  services/
    __init__.py
    preprocessor/
      __init__.py          # ProcessedInput dataclass + route_file() 디스패처
      image.py             # jpg/png → ProcessedInput
      pdf.py               # pdf → 페이지별 ProcessedInput (pymupdf)
      spreadsheet.py       # xlsx → 텍스트 ProcessedInput
      presentation.py      # pptx → 슬라이드별 ProcessedInput (python-pptx)

tests/
  conftest.py              # 공통 픽스처
  test_schemas.py
  test_preprocessor.py

pytest.ini
requirements.txt
.env.example
```

---

## Task 1: 프로젝트 스캐폴딩 & 설정

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `app/core/config.py`
- Create: `pytest.ini`
- Create: `tests/conftest.py`
- Create: 빈 `__init__.py` 파일들

- [ ] **Step 1: 디렉토리와 빈 패키지 파일 생성**

```bash
mkdir -p app/core app/schemas app/services/preprocessor \
         data/templates data/jobs static tests

touch app/__init__.py \
      app/core/__init__.py \
      app/schemas/__init__.py \
      app/services/__init__.py \
      app/services/preprocessor/__init__.py
```

- [ ] **Step 2: requirements.txt 작성**

`requirements.txt`:
```
fastapi
uvicorn[standard]
python-multipart
openpyxl
pymupdf
python-pptx
Pillow
httpx
aiosqlite
pydantic-settings
pytest
pytest-asyncio
```

- [ ] **Step 3: .env.example 작성**

`.env.example`:
```ini
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma4
DATA_DIR=data

# 전역 시스템 프롬프트 (템플릿별 커스텀 프롬프트가 없을 때 사용)
OLLAMA_SYSTEM_PROMPT=당신은 영수증·매출전표 데이터 추출 전문가입니다. 이미지 또는 텍스트에서 영수증 정보를 추출하여 반드시 아래 JSON 형식으로만 응답하세요. 마크다운 코드블록 없이 순수 JSON만 출력하세요.\n\n{"날짜":"YYYY-MM-DD","업체명":"string","품목":"string","금액":0,"부가세":0,"결제수단":"카드","비고":null}
```

- [ ] **Step 4: app/core/config.py 작성**

```python
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings

_DEFAULT_PROMPT = (
    "당신은 영수증·매출전표 데이터 추출 전문가입니다."
    " 이미지 또는 텍스트에서 영수증 정보를 추출하여"
    " 반드시 아래 JSON 형식으로만 응답하세요."
    " 마크다운 코드블록 없이 순수 JSON만 출력하세요.\n\n"
    '{"날짜":"YYYY-MM-DD","업체명":"string","품목":"string",'
    '"금액":0,"부가세":0,"결제수단":"카드","비고":null}'
)

class Config(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma4"
    ollama_system_prompt: str = _DEFAULT_PROMPT
    data_dir: Path = Path("data")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

@lru_cache
def get_config() -> Config:
    return Config()
```

- [ ] **Step 5: pytest.ini 작성**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 6: tests/conftest.py 작성**

```python
import pytest
from pathlib import Path

@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    (tmp_path / "templates").mkdir()
    (tmp_path / "jobs").mkdir()
    return tmp_path
```

- [ ] **Step 7: 패키지 설치 및 확인**

```bash
pip install -r requirements.txt
python -c "import fastapi, openpyxl, fitz, pptx, PIL, httpx, aiosqlite, pydantic_settings; print('OK')"
```

Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git init
git add requirements.txt .env.example pytest.ini app/ tests/
git commit -m "feat: project scaffold, config, and test setup"
```

---

## Task 2: 데이터 스키마 (ReceiptData, Template, JobProgress)

**Files:**
- Create: `app/schemas/receipt.py`
- Create: `app/schemas/template.py`
- Create: `app/schemas/job.py`
- Test: `tests/test_schemas.py`

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

def test_receipt_invalid_payment_method():
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
                 fields=["날짜"], custom_prompt="extract this",
                 created_at=datetime.utcnow())
    assert t.has_custom_prompt is True

def test_job_progress_defaults():
    j = JobProgress(job_id="j1", template_id="t1",
                    status="pending", total=10, done=0)
    assert j.failed_files == []
    assert j.pdf_url is None
    assert j.download_url is None
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_schemas.py -v
```

Expected: `ImportError` (모듈 미존재)

- [ ] **Step 3: app/schemas/receipt.py 작성**

> ⚠️ **[구식]** 아래 스키마는 초기 설계입니다. 현재 구현 스키마:
```python
# 현재 실제 구현 (app/schemas/receipt.py)
from typing import Literal
from pydantic import BaseModel

ExpenseCategory = Literal[
    "식대", "접대비", "여비교통비", "항공료", "숙박비", "유류대", "주차통행료", "기타비용",
]

class ReceiptData(BaseModel):
    날짜: str                          # '2025.12.05' 형식
    가맹점명: str                       # 비고(O) 컬럼에 기록
    프로젝트명: str | None = None       # 거래처/프로젝트명(B) 컬럼
    금액: int
    부가세: int = 0
    카테고리: ExpenseCategory = "기타비용"
    결제수단: Literal["카드", "현금", "계좌이체", "기타"] = "카드"
    비고: str | None = None
```
> 초기 설계 스키마 (참고용):
```python
from pydantic import BaseModel
from typing import Literal

class ReceiptData(BaseModel):
    날짜: str
    업체명: str      # ← 현재: 가맹점명
    품목: str        # ← 현재: 제거됨 (카테고리로 대체)
    금액: int
    부가세: int
    결제수단: Literal["카드", "현금", "계좌이체", "기타"]
    비고: str | None = None
```

- [ ] **Step 4: app/schemas/template.py 작성**

```python
from pydantic import BaseModel, computed_field
from datetime import datetime

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

- [ ] **Step 5: app/schemas/job.py 작성**

```python
from pydantic import BaseModel
from typing import Literal

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
pytest tests/test_schemas.py -v
```

Expected: `5 passed`

- [ ] **Step 7: Commit**

```bash
git add app/schemas/ tests/test_schemas.py
git commit -m "feat: Pydantic schemas — ReceiptData, Template, JobProgress"
```

---

## Task 3: 전처리기 — ProcessedInput 타입 & 이미지 핸들러

**Files:**
- Modify: `app/services/preprocessor/__init__.py` — `ProcessedInput` + `route_file()`
- Create: `app/services/preprocessor/image.py`
- Test: `tests/test_preprocessor.py` (이미지 케이스)

- [ ] **Step 1: 테스트 작성**

`tests/test_preprocessor.py`:
```python
import io
import pytest
from PIL import Image as PilImage
from app.services.preprocessor import ProcessedInput, route_file

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

def test_png_base64_is_decodable(white_png_bytes):
    import base64
    results = route_file(white_png_bytes, "scan.png")
    decoded = base64.b64decode(results[0].image_b64)
    assert len(decoded) > 0

def test_unsupported_extension_raises():
    with pytest.raises(ValueError, match="Unsupported"):
        route_file(b"data", "document.txt")
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_preprocessor.py -v
```

Expected: `ImportError`

- [ ] **Step 3: app/services/preprocessor/__init__.py 작성**

> ⚠️ **[2026-04-29 SUPERSEDED]** 아래 `ProcessedInput`의 `image_b64 + text` 이중 필드는 구식입니다.  
> 현재 구현은 `docling_text: str | None` 단일 필드만 사용하며, Docling `DocumentConverter`가  
> 이미지·PDF·PPTX 모두를 마크다운 텍스트로 변환합니다.  
> 최신 구조는 `2026-04-29-master-refactor.md` → "파이프라인 레이어" 섹션을 참조하라.

```python
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from PIL.Image import Image as PilImage

@dataclass
class ProcessedInput:
    source_name: str       # 원본 파일명 (로그·오류 추적용)
    source_page: int       # 페이지/슬라이드 번호 (단일 파일은 0)
    image_b64: str | None  # [SUPERSEDED] base64 인코딩 이미지 — 현재 미사용
    text: str | None       # [SUPERSEDED] 직접 추출 텍스트 — 현재 docling_text로 대체
    pil_image: PilImage | None  # 증적 PDF 병합용 원본 이미지 (xlsx은 None)
    # 현재 실제 구현: docling_text: str | None (Docling 변환 결과 마크다운)

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

- [ ] **Step 4: app/services/preprocessor/image.py 작성**

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

- [ ] **Step 5: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_preprocessor.py -v
```

Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add app/services/preprocessor/ tests/test_preprocessor.py
git commit -m "feat: ProcessedInput type and image preprocessor"
```

---

## Task 4: 전처리기 — PDF 핸들러

**Files:**
- Create: `app/services/preprocessor/pdf.py`
- Modify: `tests/test_preprocessor.py` (PDF 케이스 추가)

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
    assert results[0].source_name == "invoice.pdf"
    assert results[0].source_page == 0
    assert results[1].source_page == 1
    assert results[0].image_b64 is not None
    assert results[0].pil_image is not None
    assert results[0].text is None
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_preprocessor.py::test_pdf_one_input_per_page -v
```

Expected: `FAILED` (ImportError 또는 모듈 없음)

- [ ] **Step 3: app/services/preprocessor/pdf.py 작성**

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
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))  # 2x 해상도
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
pytest tests/test_preprocessor.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add app/services/preprocessor/pdf.py tests/test_preprocessor.py
git commit -m "feat: PDF preprocessor — per-page image extraction via pymupdf"
```

---

## Task 5: 전처리기 — Spreadsheet & Presentation

**Files:**
- Create: `app/services/preprocessor/spreadsheet.py`
- Create: `app/services/preprocessor/presentation.py`
- Modify: `tests/test_preprocessor.py` (xlsx, pptx 케이스 추가)

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

def test_xlsx_single_text_input(simple_xlsx_bytes):
    results = route_file(simple_xlsx_bytes, "data.xlsx")
    assert len(results) == 1
    r = results[0]
    assert r.image_b64 is None
    assert r.pil_image is None
    assert r.text is not None
    assert "5500" in r.text

def test_pptx_one_input_per_slide(two_slide_pptx_bytes):
    results = route_file(two_slide_pptx_bytes, "slides.pptx")
    assert len(results) == 2

def test_pptx_text_extracted(two_slide_pptx_bytes):
    results = route_file(two_slide_pptx_bytes, "slides.pptx")
    assert "영수증 1" in results[0].text
    assert "영수증 2" in results[1].text
    assert results[0].source_page == 0
    assert results[1].source_page == 1
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_preprocessor.py::test_xlsx_single_text_input -v
```

Expected: `FAILED` (ImportError)

- [ ] **Step 3: app/services/preprocessor/spreadsheet.py 작성**

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

- [ ] **Step 4: app/services/preprocessor/presentation.py 작성**

```python
import base64
import io
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from PIL import Image
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
            # 슬라이드에 이미지가 있으면 첫 번째 이미지를 VLM에 전달
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
            # 이미지 없는 슬라이드는 텍스트로 추출
            results.append(ProcessedInput(
                source_name=source_name,
                source_page=slide_num,
                image_b64=None,
                text="\n".join(text_parts),
                pil_image=None,
            ))

    return results
```

- [ ] **Step 5: 전체 전처리기 테스트 실행 — 통과 확인**

```bash
pytest tests/test_preprocessor.py -v
```

Expected: `8 passed`

- [ ] **Step 6: Commit**

```bash
git add app/services/preprocessor/spreadsheet.py \
        app/services/preprocessor/presentation.py \
        tests/test_preprocessor.py
git commit -m "feat: xlsx and pptx preprocessors — text and embedded-image extraction"
```

---

## Self-Review

**스펙 커버리지:**

| 요구사항 | 태스크 |
|---------|-------|
| `gemma4` 기본값 (코드 하드코딩 금지, .env 주입) | Task 1 — `Config.ollama_model = "gemma4"` |
| `ProcessedInput.pil_image` (증적 PDF용) | Task 3 — dataclass 정의 |
| PDF/PPTX 각 페이지 = 영수증 1건 | Task 4 (PDF), Task 5 (PPTX) — 리스트 반환 |
| xlsx → 텍스트 경로 (pil_image=None) | Task 5 — spreadsheet.py |
| `JobProgress.pdf_url` 필드 | Task 2 — job.py |
| `Template.has_custom_prompt` | Task 2 — computed_field |

**플레이스홀더 없음** — 모든 단계에 완전한 코드 포함.

**타입 일관성:**
- `ProcessedInput.pil_image: PilImage | None` — Task 3에서 정의, Task 4·5에서 동일하게 사용 ✓
- `route_file(file_bytes: bytes, filename: str) -> list[ProcessedInput]` — Task 3에서 정의, Task 4·5 테스트에서 동일 시그니처로 호출 ✓

---
