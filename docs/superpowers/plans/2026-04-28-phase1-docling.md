# Phase 1 — Docling 전처리기 재작성

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 pymupdf/python-pptx/PIL 기반 전처리기를 Docling 기반 단일 파이프라인으로 교체. `ProcessedInput.image_b64 + text` → `docling_text` 로 통합.

**Architecture:**
- `DoclingService`: `DocumentConverter` 싱글턴 래퍼. 모든 파일 타입을 단일 인터페이스로 처리.
- 각 preprocessor 파일은 `DoclingService`를 받아서 호출하는 얇은 함수로 전환.
- `pil_image` 필드는 유지 (이미지·PDF·PPTX → 증적 PDF용). XLSX는 None.
- Ollama로 전달하는 입력이 `image_b64` + `text` 분기 → `docling_text` 단일 텍스트로 통합.

**Tech Stack:** Python 3.11+, docling, Pillow, pytest

**전제:** Phase 1 스캐폴딩 완료 (preprocessor 4개 파일, `ProcessedInput` 기존 버전)

---

## 파일 맵

| 파일 | 작업 |
|------|------|
| `requirements.txt` | `docling` 추가, `pymupdf`·`python-pptx` test-only 주석 |
| `app/services/preprocessor/__init__.py` | `ProcessedInput` 필드 변경 (`image_b64`·`text` → `docling_text`) |
| `app/services/docling_service.py` | 신규 — `DocumentConverter` 래퍼 |
| `app/services/preprocessor/image.py` | Docling OCR 기반으로 교체 |
| `app/services/preprocessor/pdf.py` | Docling 기반으로 교체 |
| `app/services/preprocessor/spreadsheet.py` | Docling 기반으로 교체 |
| `app/services/preprocessor/presentation.py` | Docling 기반으로 교체 |
| `tests/test_preprocessor.py` | `image_b64`·`text` → `docling_text` 참조 갱신 |

---

## Task 1: requirements.txt 업데이트

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: requirements.txt 수정**

```
fastapi
uvicorn[standard]
python-multipart
openpyxl
docling
Pillow
httpx
aiosqlite
pydantic-settings
pytest
pytest-asyncio
# test fixture generation only (not used in production code):
pymupdf
python-pptx
```

- [ ] **Step 2: docling 설치**

```bash
pip install docling
```

Expected: 설치 완료 (torch, transformers 등 ML 의존성 함께 설치됨)

- [ ] **Step 3: import 확인**

```bash
python -c "from docling.document_converter import DocumentConverter; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add docling, keep pymupdf/python-pptx as test-only"
```

---

## Task 2: ProcessedInput 필드 변경

**Files:**
- Modify: `app/services/preprocessor/__init__.py`

- [ ] **Step 1: 실패할 테스트 먼저 작성**

`tests/test_preprocessor.py` 상단에 아래 테스트 추가 (기존 테스트는 아직 건드리지 않음):

```python
def test_processed_input_has_docling_text_field():
    pi = ProcessedInput(
        source_name="test.jpg",
        source_page=0,
        docling_text="업체명: 스타벅스\n금액: 5500",
        pil_image=None,
    )
    assert pi.docling_text == "업체명: 스타벅스\n금액: 5500"
    assert not hasattr(pi, "image_b64")
    assert not hasattr(pi, "text")
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd /bj-dev/receipt-to-excel && python -m pytest tests/test_preprocessor.py::test_processed_input_has_docling_text_field -v
```

Expected: FAIL — `TypeError` (ProcessedInput에 docling_text 없음)

- [ ] **Step 3: ProcessedInput 필드 변경**

`app/services/preprocessor/__init__.py` 전체 교체:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL.Image import Image as PilImage


@dataclass
class ProcessedInput:
    source_name: str        # 원본 파일명 (로그·오류 추적용)
    source_page: int        # 페이지/슬라이드 번호 (단일 파일은 0)
    docling_text: str       # Docling 구조화 텍스트 → Ollama 텍스트 모드로 전달
    pil_image: PilImage | None  # 증적 PDF 병합용 (xlsx은 None)
    confidence: float | None = field(default=None)  # Docling 신뢰도 (선택)


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

- [ ] **Step 4: 새 테스트 통과 확인**

```bash
python -m pytest tests/test_preprocessor.py::test_processed_input_has_docling_text_field -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/preprocessor/__init__.py tests/test_preprocessor.py
git commit -m "feat: ProcessedInput — image_b64+text → docling_text"
```

---

## Task 3: DoclingService 구현

**Files:**
- Create: `app/services/docling_service.py`

- [ ] **Step 1: DoclingService 작성**

```python
# app/services/docling_service.py
from __future__ import annotations

import tempfile
from collections import defaultdict
from pathlib import Path

from PIL import Image as PilImage

from app.services.preprocessor import ProcessedInput


class DoclingService:
    """DocumentConverter 싱글턴 래퍼. 모든 파일 타입을 ProcessedInput 목록으로 변환."""

    def __init__(self) -> None:
        from docling.document_converter import DocumentConverter
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions, PipelineOptions

        pdf_opts = PdfPipelineOptions(generate_page_images=True)
        self._converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PipelineOptions(pipeline_options=pdf_opts),
            }
        )

    def process(self, file_bytes: bytes, filename: str, source_name: str) -> list[ProcessedInput]:
        suffix = Path(filename).suffix.lower()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(file_bytes)
            tmp_path = Path(f.name)

        try:
            result = self._converter.convert(str(tmp_path))
        finally:
            tmp_path.unlink(missing_ok=True)

        doc = result.document

        if suffix in (".pdf", ".pptx"):
            return self._split_by_page(doc, source_name, suffix)
        else:
            return self._single_page(doc, source_name, suffix, file_bytes)

    # ------------------------------------------------------------------
    def _split_by_page(self, doc, source_name: str, suffix: str) -> list[ProcessedInput]:
        page_texts: dict[int, list[str]] = defaultdict(list)
        for item, _level in doc.iterate_items():
            provs = getattr(item, "prov", None) or []
            for prov in provs:
                page_no = getattr(prov, "page_no", None)
                if page_no is None:
                    continue
                text = getattr(item, "text", None)
                if text:
                    page_texts[page_no].append(text)

        if not page_texts:
            full = doc.export_to_markdown()
            return [ProcessedInput(source_name=source_name, source_page=0,
                                   docling_text=full, pil_image=None)]

        results: list[ProcessedInput] = []
        for page_no in sorted(page_texts.keys()):
            text = "\n".join(page_texts[page_no])
            pil_img = self._page_image(doc, page_no)
            results.append(ProcessedInput(
                source_name=source_name,
                source_page=page_no - 1,  # Docling은 1-indexed
                docling_text=text,
                pil_image=pil_img,
            ))
        return results

    def _single_page(self, doc, source_name: str, suffix: str,
                     file_bytes: bytes) -> list[ProcessedInput]:
        text = doc.export_to_markdown()
        pil_img: PilImage.Image | None = None
        if suffix in (".jpg", ".jpeg", ".png"):
            import io
            pil_img = PilImage.open(io.BytesIO(file_bytes)).convert("RGB")
        return [ProcessedInput(source_name=source_name, source_page=0,
                               docling_text=text, pil_image=pil_img)]

    @staticmethod
    def _page_image(doc, page_no: int) -> PilImage.Image | None:
        page = (doc.pages or {}).get(page_no)
        if page is None:
            return None
        img_ref = getattr(page, "image", None)
        if img_ref is None:
            return None
        return getattr(img_ref, "pil_image", None)
```

- [ ] **Step 2: import 확인 (모델 다운로드 포함)**

```bash
python -c "
from app.services.docling_service import DoclingService
svc = DoclingService()
print('DoclingService init ok')
"
```

Expected: `DoclingService init ok` (첫 실행 시 모델 다운로드로 수 분 소요 가능)

- [ ] **Step 3: Commit**

```bash
git add app/services/docling_service.py
git commit -m "feat: DoclingService — DocumentConverter 싱글턴 래퍼"
```

---

## Task 4: image.py 교체

**Files:**
- Modify: `app/services/preprocessor/image.py`
- Modify: `tests/test_preprocessor.py`

- [ ] **Step 1: 새 테스트 작성**

`tests/test_preprocessor.py` 에서 기존 `test_jpg_returns_single_input`, `test_png_base64_decodable` 를 아래로 교체:

```python
def test_jpg_returns_single_input(white_jpg_bytes):
    results = route_file(white_jpg_bytes, "receipt.jpg")
    assert len(results) == 1
    r = results[0]
    assert r.source_name == "receipt.jpg"
    assert r.source_page == 0
    assert r.docling_text  # 비어있지 않음
    assert r.pil_image is not None


def test_png_has_pil_image(white_png_bytes):
    results = route_file(white_png_bytes, "scan.png")
    r = results[0]
    assert r.pil_image is not None
    assert r.pil_image.size[0] > 0
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_preprocessor.py::test_jpg_returns_single_input tests/test_preprocessor.py::test_png_has_pil_image -v
```

Expected: FAIL (image.py 아직 image_b64 반환)

- [ ] **Step 3: image.py 교체**

```python
# app/services/preprocessor/image.py
from __future__ import annotations

from app.services.docling_service import DoclingService
from . import ProcessedInput

_svc = DoclingService()


def process_image(file_bytes: bytes, source_name: str) -> list[ProcessedInput]:
    return _svc.process(file_bytes, source_name, source_name)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_preprocessor.py::test_jpg_returns_single_input tests/test_preprocessor.py::test_png_has_pil_image -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/preprocessor/image.py tests/test_preprocessor.py
git commit -m "feat: image preprocessor — Docling OCR 기반으로 교체"
```

---

## Task 5: pdf.py 교체

**Files:**
- Modify: `app/services/preprocessor/pdf.py`
- Modify: `tests/test_preprocessor.py`

- [ ] **Step 1: 새 테스트 작성**

기존 `test_pdf_one_input_per_page`, `test_pdf_page_metadata` 를 아래로 교체:

```python
def test_pdf_one_input_per_page(two_page_pdf_bytes):
    results = route_file(two_page_pdf_bytes, "invoice.pdf")
    assert len(results) == 2


def test_pdf_page_metadata(two_page_pdf_bytes):
    results = route_file(two_page_pdf_bytes, "invoice.pdf")
    assert results[0].source_page == 0
    assert results[1].source_page == 1
    assert results[0].docling_text  # 비어있지 않음
    assert results[0].pil_image is not None
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_preprocessor.py::test_pdf_one_input_per_page tests/test_preprocessor.py::test_pdf_page_metadata -v
```

Expected: FAIL (pdf.py 아직 image_b64 반환)

- [ ] **Step 3: pdf.py 교체**

```python
# app/services/preprocessor/pdf.py
from __future__ import annotations

from app.services.docling_service import DoclingService
from . import ProcessedInput

_svc = DoclingService()


def process_pdf(file_bytes: bytes, source_name: str) -> list[ProcessedInput]:
    return _svc.process(file_bytes, source_name, source_name)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_preprocessor.py::test_pdf_one_input_per_page tests/test_preprocessor.py::test_pdf_page_metadata -v
```

Expected: PASS

> **참고:** DoclingService에서 `_split_by_page`가 페이지 텍스트를 찾지 못하면 단일 항목이 반환될 수 있음.
> 그 경우 `_split_by_page` 로직 확인 필요 (Task 3 Step 2 실행 후 `doc.pages` 구조 디버깅).

- [ ] **Step 5: Commit**

```bash
git add app/services/preprocessor/pdf.py tests/test_preprocessor.py
git commit -m "feat: pdf preprocessor — Docling 기반으로 교체"
```

---

## Task 6: spreadsheet.py 교체

**Files:**
- Modify: `app/services/preprocessor/spreadsheet.py`
- Modify: `tests/test_preprocessor.py`

- [ ] **Step 1: 새 테스트 작성**

기존 `test_xlsx_returns_single_text_input` 교체:

```python
def test_xlsx_returns_single_text_input(simple_xlsx_bytes):
    results = route_file(simple_xlsx_bytes, "data.xlsx")
    assert len(results) == 1
    r = results[0]
    assert r.pil_image is None
    assert r.docling_text  # 비어있지 않음
    assert "5500" in r.docling_text
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_preprocessor.py::test_xlsx_returns_single_text_input -v
```

Expected: FAIL (spreadsheet.py 아직 text 필드 반환)

- [ ] **Step 3: spreadsheet.py 교체**

```python
# app/services/preprocessor/spreadsheet.py
from __future__ import annotations

from app.services.docling_service import DoclingService
from . import ProcessedInput

_svc = DoclingService()


def process_spreadsheet(file_bytes: bytes, source_name: str) -> list[ProcessedInput]:
    return _svc.process(file_bytes, source_name, source_name)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_preprocessor.py::test_xlsx_returns_single_text_input -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/preprocessor/spreadsheet.py tests/test_preprocessor.py
git commit -m "feat: spreadsheet preprocessor — Docling 기반으로 교체"
```

---

## Task 7: presentation.py 교체

**Files:**
- Modify: `app/services/preprocessor/presentation.py`
- Modify: `tests/test_preprocessor.py`

- [ ] **Step 1: 새 테스트 작성**

기존 `test_pptx_one_input_per_slide`, `test_pptx_text_extracted` 교체:

```python
def test_pptx_one_input_per_slide(two_slide_pptx_bytes):
    results = route_file(two_slide_pptx_bytes, "slides.pptx")
    assert len(results) == 2


def test_pptx_text_extracted(two_slide_pptx_bytes):
    results = route_file(two_slide_pptx_bytes, "slides.pptx")
    combined = results[0].docling_text + results[1].docling_text
    assert "영수증" in combined
    assert results[0].source_page == 0
    assert results[1].source_page == 1
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_preprocessor.py::test_pptx_one_input_per_slide tests/test_preprocessor.py::test_pptx_text_extracted -v
```

Expected: FAIL (presentation.py 아직 text 필드 반환)

- [ ] **Step 3: presentation.py 교체**

```python
# app/services/preprocessor/presentation.py
from __future__ import annotations

from app.services.docling_service import DoclingService
from . import ProcessedInput

_svc = DoclingService()


def process_presentation(file_bytes: bytes, source_name: str) -> list[ProcessedInput]:
    return _svc.process(file_bytes, source_name, source_name)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_preprocessor.py::test_pptx_one_input_per_slide tests/test_preprocessor.py::test_pptx_text_extracted -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/preprocessor/presentation.py tests/test_preprocessor.py
git commit -m "feat: presentation preprocessor — Docling 기반으로 교체"
```

---

## Task 8: 기존 테스트 정리 + 전체 통과 확인

**Files:**
- Modify: `tests/test_preprocessor.py`

- [ ] **Step 1: 구버전 test_processed_input_fields 제거**

`tests/test_preprocessor.py` 에서 아래 테스트 삭제 (image_b64 참조):

```python
# 삭제할 테스트
def test_processed_input_fields():
    pi = ProcessedInput(
        source_name="test.jpg",
        source_page=0,
        image_b64="abc",   # 더 이상 존재하지 않는 필드
        text=None,
        pil_image=None,
    )
    ...
```

- [ ] **Step 2: 전체 테스트 실행**

```bash
python -m pytest tests/test_preprocessor.py -v
```

Expected: 모든 테스트 PASS, 0 FAILED

- [ ] **Step 3: Commit**

```bash
git add tests/test_preprocessor.py
git commit -m "test: preprocessor 테스트 docling_text 기준으로 정리"
```

---

## 완료 기준 (Phase 1 전체)

```bash
# 전체 테스트 통과
python -m pytest tests/test_preprocessor.py -v
# Expected: 전체 PASS

# 빠른 E2E 확인 (DoclingService 직접 호출)
python -c "
import io
from PIL import Image
from app.services.preprocessor import route_file

# 흰색 JPG 생성
img = Image.new('RGB', (200, 150), 'white')
buf = io.BytesIO()
img.save(buf, format='JPEG')

results = route_file(buf.getvalue(), 'test.jpg')
r = results[0]
print('source_name:', r.source_name)
print('docling_text length:', len(r.docling_text))
print('pil_image:', r.pil_image is not None)
print('Phase 1 OK')
"
```

**Phase 1 완료 조건:**
- `pytest tests/test_preprocessor.py` 전체 통과
- `ProcessedInput.image_b64` 및 `.text` 필드 미존재
- `route_file()` 호출 시 모든 파일 타입에서 `docling_text` 비어있지 않음
- `pil_image`: 이미지/PDF/PPTX는 `Image` 객체, XLSX는 `None`
