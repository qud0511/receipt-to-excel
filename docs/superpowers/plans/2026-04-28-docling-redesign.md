# Docling 기반 전체 재설계 — Phase Overview

> **For agentic workers:** 이 문서는 설계 승인용 개요입니다. 각 Phase 구현 시 별도 상세 플랜 파일을 작성하세요.

**Goal:** Docling을 전처리+OCR 레이어로 도입하여, 기존 파일별 개별 파서(pymupdf/python-pptx/PIL)를 단일 DoclingService로 통합하고, Ollama는 Docling 구조화 텍스트 기반 필드 해석에만 집중하게 한다.

**Architecture:**
```
파일 업로드
  → DoclingService (Docling DocumentConverter)
      → 파일 파싱 + OCR + 구조화 텍스트 추출
      → 페이지별 PIL.Image 추출 (증적 PDF용)
  → BatchProcessor
      → OllamaClient (Docling 텍스트 → ReceiptData JSON)
      → ExcelMapper (Named Range → 행 누적)
      → PdfMerger (PIL.Image 목록 → evidence.pdf)
  → SSE 진행률 + xlsx/pdf 다운로드
```

**Tech Stack (변경 후):**
```
추가:  docling
제거:  pymupdf, python-pptx  (Docling이 내부적으로 처리)
유지:  fastapi, uvicorn, python-multipart, openpyxl, Pillow,
       httpx, aiosqlite, pydantic-settings
```

---

## ProcessedInput 변경 (핵심 계약)

```python
# 변경 전
@dataclass
class ProcessedInput:
    source_name: str
    source_page: int
    image_b64: str | None   # VLM용 base64
    text: str | None        # xlsx 텍스트
    pil_image: Image | None

# 변경 후
@dataclass
class ProcessedInput:
    source_name: str
    source_page: int
    docling_text: str       # Docling 구조화 텍스트 → Ollama 텍스트 모드로만 전달
    pil_image: Image | None # 증적 PDF용 (xlsx = None)
    confidence: float | None = None  # Docling 신뢰도 (선택)
```

Ollama 호출이 이미지/텍스트 분기 없이 **항상 텍스트 모드**로 단일화된다.

---

## Phase 1 — 전처리기 재작성 (현재 완료 → 수정 필요)

### 변경
| 파일 | 현재 | 변경 후 |
|------|------|---------|
| `preprocessor/__init__.py` | `ProcessedInput.image_b64 + text` | `ProcessedInput.docling_text` |
| `preprocessor/image.py` | PIL → base64 | Docling OCR → docling_text + PIL.Image |
| `preprocessor/pdf.py` | pymupdf 페이지 렌더링 → base64 | Docling → docling_text + 페이지 PIL.Image |
| `preprocessor/spreadsheet.py` | openpyxl 텍스트 직렬화 | Docling → docling_text (PIL.Image 없음) |
| `preprocessor/presentation.py` | python-pptx + PIL 임베드 이미지 | Docling → docling_text + 슬라이드 PIL.Image |

### 신규
- `app/services/docling_service.py` — `DocumentConverter` 싱글턴 래퍼
  ```python
  from docling.document_converter import DocumentConverter
  from docling.datamodel.pipeline_options import PdfPipelineOptions

  class DoclingService:
      def __init__(self):
          opts = PdfPipelineOptions(generate_page_images=True)
          self._converter = DocumentConverter(...)

      def process(self, file_bytes: bytes, filename: str, source_name: str) -> list[ProcessedInput]:
          # 임시 파일 → DocumentConverter.convert() → DoclingDocument
          # 페이지별 doc.pages → docling_text (markdown export) + pil_image
          ...
  ```

### 유지
- `route_file()` 외부 인터페이스 (호출 시그니처 불변)
- `ProcessedInput.source_name`, `source_page`, `pil_image` 필드

### 완료 기준
```bash
pytest tests/test_preprocessor.py -v
# jpg, pdf(멀티페이지), xlsx, pptx 각각 ProcessedInput 반환
# docling_text != "" 확인
# pdf/pptx는 페이지/슬라이드 수만큼 항목 반환 확인
```

---

## Phase 2 — Docling+Ollama OCR 파이프라인 + SSE

### 변경
| 파일 | 현재 | 변경 후 |
|------|------|---------|
| `services/ollama_client.py` | image_b64 VLM / text 분기 | 항상 text 모드 (`docling_text`만 전달) |
| `services/batch_processor.py` | preprocessor 직접 호출 | DoclingService 경유 후 Ollama 텍스트 호출 |

```python
# ollama_client.py — 변경 후
async def extract_receipt(self, input: ProcessedInput, system_prompt: str) -> ReceiptData:
    payload = {
        "model": self.model,
        "system": system_prompt,
        "prompt": input.docling_text,   # 항상 텍스트 (VLM 분기 없음)
        "stream": False,
        "format": "json",
    }
    response = await self.http.post("/api/generate", json=payload)
    return ReceiptData.model_validate_json(response.json()["response"])
```

### 유지
- `InMemoryJobManager` + `JobManager` Protocol
- SSE 스트리밍 구조 (`GET /jobs/{id}/stream`)
- `retry: 60000` 헤더
- `BatchProcessor` 오케스트레이션 흐름 (for loop + fail-safe)

### 신규
없음 (Phase 1 DoclingService 도입으로 충분)

### 완료 기준
```bash
# Ollama 없어도 구조 검증 가능
pytest tests/test_ollama_client.py tests/test_batch_processor.py -v

# Ollama 있을 때 E2E
JOB=$(curl -s -X POST http://localhost:8000/jobs \
  -F "files=@tests/fixtures/sample.jpg" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
curl -N http://localhost:8000/jobs/$JOB/stream
# → data: {"status":"completed",...} 확인
```

---

## Phase 3 — Template 관리 + Excel 매핑

### 변경
없음 (Docling 영향 없음)

### 유지
- `ExcelMapper` — Named Range 읽기, DATA_START 폴백, 행 추가
- `TemplateStore` — SQLite CRUD
- Template API 전체 (`POST/GET/PUT/DELETE /templates`)
- `resolve_prompt()` 계층적 프롬프트 우선순위

### 완료 기준
```bash
# 템플릿 등록
curl -X POST http://localhost:8000/templates \
  -F "file=@tests/fixtures/template.xlsx" \
  -F "name=지출결의서"

# 배치 처리 → xlsx 다운로드 + 행 누적 확인
JOB=$(curl -s -X POST http://localhost:8000/jobs \
  -F "template_id=tpl_xxx" \
  -F "files=@tests/fixtures/sample.jpg" \
  -F "files=@tests/fixtures/sample2.jpg" | ...)
curl -o result.xlsx http://localhost:8000/jobs/$JOB/result
# openpyxl로 행 2개 추가됐는지 확인
```

---

## Phase 4 — 증적용 PDF 생성

### 변경
- PDF용 PIL.Image 소스: ~~pymupdf~~ → `DoclingService`에서 `generate_page_images=True` 옵션으로 페이지 이미지 추출
- PPTX용 PIL.Image 소스: ~~python-pptx~~ → Docling 슬라이드 렌더링 이미지

### 유지
- `PdfMerger.merge_images_to_pdf(images, output_path)` — 함수 시그니처/로직 불변
- `ProcessedInput.pil_image` 경로 (xlsx만 None, 나머지는 Image 포함)
- `data/jobs/{job_id}/evidence.pdf` 저장 경로
- `GET /jobs/{id}/result/pdf` 엔드포인트

### 완료 기준
```bash
# xlsx + evidence.pdf 동시 생성 확인
curl -o evidence.pdf http://localhost:8000/jobs/$JOB/result/pdf
# PDF 열어서 영수증 이미지 포함 확인 (페이지 수 = 업로드 영수증 수)
```

---

## Phase 5 — 프론트엔드 UI

### 변경
없음 (Docling은 백엔드 전처리 레이어, UI에 영향 없음)

### 유지 (기존 설계 그대로)
- `static/index.html` — 템플릿 선택 + 파일 업로드 + 진행률
- `static/app.js` — EventSource SSE + xlsx/pdf 다운로드 버튼 동시 노출
- `static/style.css`

### 완료 기준
```
브라우저에서:
1. 템플릿 등록 → 목록에서 선택
2. 영수증 3장 업로드
3. 진행률 바 표시 (SSE)
4. 완료 후 xlsx 다운로드 버튼 + PDF 다운로드 버튼 노출
5. 각 파일 정상 다운로드 확인
```

---

## 의존성 변경 요약

```diff
# requirements.txt
+ docling
- pymupdf
- python-pptx
  fastapi
  uvicorn[standard]
  python-multipart
  openpyxl
  Pillow
  httpx
  aiosqlite
  pydantic-settings
```

> **주의:** Docling 설치 시 torch, transformers 등 ML 의존성이 함께 설치됨.
> CPU 전용 서버에서는 `docling[cpu]` 또는 `torch` CPU 버전 명시 필요.

---

## Phase 실행 순서

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5
(전처리기)  (OCR+SSE)  (템플릿+엑셀)  (PDF병합)  (프론트엔드)
```

각 Phase는 독립적으로 테스트 가능하며, 이전 Phase 완료 후 다음으로 진행한다.
Phase 1~2가 연속으로 묶여야 E2E 흐름 (파일 → OCR → SSE) 검증 가능.
