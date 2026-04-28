# Receipt-to-Excel 변환 서비스 — 설계 문서

**작성일:** 2026-04-28  
**최종 수정:** 2026-04-28 (v2 — 증적용 PDF 생성 기능, 다중 페이지 처리, SSE 안정성 추가)  
**상태:** 확정

---

## 1. 서비스 개요

영수증·매출전표 이미지(또는 문서)를 업로드하면, 로컬 VLM(Gemma 4)이 데이터를 추출하고, 사전 등록된 엑셀 템플릿의 Named Range 구조에 맞춰 행을 누적 기록하여 완성된 `.xlsx` 파일을 반환하는 서비스.

**핵심 원칙:**
- 외부 유료 API 미사용 — 모든 추론은 로컬 Ollama에서 수행
- 템플릿은 한 번 등록 후 반복 재사용 (Template Library)
- 영수증 N장 → 엑셀 1개 (행 누적 방식)
- 영수증 N장 → 증적용 PDF 1개 (이미지 순서 병합, 엑셀과 동시 생성)
- PDF/PPTX의 각 페이지는 개별 영수증 1건으로 처리 (각각 새로운 행 누적)

---

## 2. 시스템 아키텍처

### 2.1 전체 흐름도

```
┌───────────────────────────────────────────────────────────────────────────┐
│                           Browser (HTML/JS)                               │
│                                                                           │
│  ┌──────────────────┐  ┌────────────────────────┐  ┌──────────────────┐  │
│  │  템플릿 라이브러리  │  │  배치 변환 요청           │  │ 진행률 + 다운로드  │  │
│  │  (등록/목록/선택)  │  │  (템플릿 선택+파일 업로드) │  │ SSE + xlsx + pdf  │  │
│  └────────┬──────────┘  └───────────┬────────────┘  └────────┬─────────┘  │
└───────────┼─────────────────────────┼─────────────────────────┼──────────┘
            │ Template API            │ Job API                 │ SSE/Download
            ▼                         ▼                          ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                            FastAPI Server                                 │
│                                                                           │
│  ┌──────────────────────┐     ┌────────────────────────────────────────┐  │
│  │     Template API      │     │              Job API                   │  │
│  │  POST /templates      │     │  POST /jobs                            │  │
│  │  GET  /templates      │     │  GET  /jobs/{id}/stream  (SSE)         │  │
│  │  GET  /templates/{id} │     │  GET  /jobs/{id}/result  (xlsx)        │  │
│  │  PUT  /templates/{id}/│     │  GET  /jobs/{id}/result/pdf            │  │
│  │        prompt         │     └──────────────┬─────────────────────────┘  │
│  │  DELETE /templates/{id}│                   │                            │
│  └──────────┬────────────┘                    │                            │
│             │                                 │                            │
│             ▼                                 ▼                            │
│  ┌─────────────────────┐    ┌─────────────────────────────────────────┐   │
│  │   TemplateStore      │    │     BatchProcessor (asyncio)            │   │
│  │  (SQLite + 파일시스템) │    │                                         │   │
│  │  data/templates/     │    │  pdf_pages: list[PIL.Image] = []        │   │
│  │  {id}.xlsx           │    │                                         │   │
│  │  data/templates.db   │    │  for each ProcessedInput                │   │
│  └─────────────────────┘    │    (PDF/PPTX → 페이지별로 1건씩):         │   │
│                              │  ┌───────────────────────────────────┐  │   │
│                              │  │  1. Preprocessor                  │  │   │
│                              │  │  jpg/png → base64 + PIL.Image     │  │   │
│                              │  │  pdf     → 페이지별 base64+Image   │  │   │
│                              │  │  xlsx    → 텍스트 직접 추출        │  │   │
│                              │  │  pptx    → 슬라이드별 base64+Image │  │   │
│                              │  └─────────────────┬─────────────────┘  │   │
│                              │                    │ ProcessedInput       │   │
│                              │  ┌─────────────────▼─────────────────┐  │   │
│                              │  │  2. OllamaClient (gemma4)          │  │   │
│                              │  │     system_prompt 결정:            │  │   │
│                              │  │     custom_prompt → .env 전역      │  │   │
│                              │  │     이미지: base64 + prompt        │  │   │
│                              │  │     텍스트: text + prompt          │  │   │
│                              │  │     → ReceiptData JSON 반환        │  │   │
│                              │  └──────┬──────────────────┬──────────┘  │   │
│                              │  ReceiptData             PIL.Image        │   │
│                              │  ┌───────▼─────────┐  ┌──▼────────────┐  │   │
│                              │  │ 3. ExcelMapper   │  │ pdf_pages     │  │   │
│                              │  │ Named Range 매핑  │  │  .append()    │  │   │
│                              │  │ openpyxl 행 추가  │  └───────────────┘  │   │
│                              │  └─────────────────┘                      │   │
│                              │  (모든 파일 처리 후)                        │   │
│                              │  ┌────────────────────────────────────┐   │   │
│                              │  │  4. PdfMerger (Pillow)             │   │   │
│                              │  │  pdf_pages → evidence.pdf          │   │   │
│                              │  │  data/jobs/{job_id}/evidence.pdf   │   │   │
│                              │  └──────────────────┬─────────────────┘   │   │
│                              │                     │                      │   │
│                              │  ┌──────────────────▼─────────────────┐   │   │
│                              │  │  5. JobManager (SSE push)           │   │   │
│                              │  │  상태 + xlsx_url + pdf_url 업데이트  │   │   │
│                              │  └────────────────────────────────────┘   │   │
│                              └─────────────────────────────────────────┘   │
└──────────────────────────────────────┬────────────────────────────────────┘
                                       │ HTTP localhost:11434
                                       ▼
                             ┌─────────────────────┐
                             │  Ollama (로컬 서비스)  │
                             │  gemma4  (기본값)      │
                             └─────────────────────┘
```

### 2.2 하드웨어 적합성

| 항목 | 사양 |
|------|------|
| 서버 | Ubuntu, 8코어 CPU, 16GB RAM |
| GPU | 없음 (CPU 전용 추론) |
| Ollama 모델 | `gemma4` (기본값, `.env`의 `OLLAMA_MODEL`로 주입) |
| 처리 속도 (예상) | 영수증 1장당 8~20초 |
| 동시 처리 | asyncio 기반 순차 처리 (CPU 과부하 방지) |

---

## 3. 폴더 구조

```
receipt-to-excel/
├── app/
│   ├── main.py                        # FastAPI 앱 생성, 라우터·미들웨어 등록
│   ├── api/
│   │   ├── routes/
│   │   │   ├── templates.py           # Template CRUD 엔드포인트
│   │   │   ├── jobs.py                # 배치 변환 + PDF 다운로드 엔드포인트
│   │   │   └── stream.py              # SSE 진행률 스트림
│   │   └── deps.py                    # JobManager·TemplateStore 싱글턴 주입
│   ├── core/
│   │   ├── config.py                  # 환경변수 (Pydantic Settings)
│   │   └── job_manager.py             # JobManager Protocol + InMemory 구현
│   ├── services/
│   │   ├── preprocessor/
│   │   │   ├── __init__.py            # route_file() — 파일 타입 감지·분기
│   │   │   ├── image.py               # jpg/png → base64 + PIL.Image
│   │   │   ├── pdf.py                 # pdf → 페이지별 base64 + PIL.Image (pymupdf)
│   │   │   ├── spreadsheet.py         # xlsx → 텍스트 직렬화 (openpyxl)
│   │   │   └── presentation.py        # pptx → 슬라이드별 base64 + PIL.Image
│   │   ├── ollama_client.py           # gemma4 VLM 호출, JSON 추출
│   │   ├── excel_mapper.py            # Named Range 읽기, 행 추가, DATA_START 결정
│   │   ├── pdf_merger.py              # PIL.Image 목록 → 증적용 PDF 생성
│   │   ├── template_store.py          # 템플릿 CRUD (SQLite + 파일시스템)
│   │   └── batch_processor.py         # 배치 오케스트레이션 (엑셀 + PDF 동시 생성)
│   └── schemas/
│       ├── receipt.py                 # ReceiptData (Pydantic)
│       ├── template.py                # Template, TemplateCreate (Pydantic)
│       └── job.py                     # JobStatus, JobProgress (Pydantic)
├── data/
│   ├── templates/                     # 등록된 xlsx 템플릿 영구 저장
│   │   └── {template_id}.xlsx
│   ├── jobs/                          # 배치 결과 임시 저장
│   │   └── {job_id}/
│   │       ├── result.xlsx            # 변환 결과 엑셀
│   │       └── evidence.pdf           # 증적용 영수증 모음 PDF
│   └── templates.db                   # SQLite (템플릿 메타데이터)
├── static/
│   ├── index.html                     # 단일 페이지 UI
│   ├── app.js                         # 업로드·SSE·다운로드 로직 (타임아웃/재연결 포함)
│   └── style.css
├── tests/
│   ├── test_preprocessor.py
│   ├── test_ollama_client.py
│   ├── test_excel_mapper.py
│   ├── test_pdf_merger.py
│   └── test_template_store.py
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-04-28-receipt-to-excel-design.md
├── .env                               # 실제 환경변수 (git 제외)
├── .env.example                       # 환경변수 템플릿 (git 포함)
├── requirements.txt
└── README.md
```

---

## 4. API 엔드포인트

### 4.1 Template API

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/templates` | xlsx 업로드 → Named Range 검증 → 등록 |
| `GET` | `/templates` | 등록된 템플릿 목록 |
| `GET` | `/templates/{id}` | 템플릿 상세 (필드 목록, 커스텀 프롬프트 여부) |
| `PUT` | `/templates/{id}/prompt` | 템플릿별 시스템 프롬프트 수정 |
| `DELETE` | `/templates/{id}` | 템플릿 삭제 |

**POST /templates 요청 (multipart/form-data):**
```
file: File          # Named Range가 설정된 .xlsx 파일
name: str           # 표시 이름 (예: "지출결의서_3월")
system_prompt: str  # (선택) 템플릿 전용 시스템 프롬프트
```

**POST /templates 응답:**
```json
{
  "template_id": "tpl_a1b2c3",
  "name": "지출결의서_3월",
  "fields": ["날짜", "업체명", "품목", "금액", "부가세", "결제수단"],
  "has_custom_prompt": false,
  "created_at": "2026-04-28T10:30:00"
}
```

### 4.2 Job API

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/jobs` | 배치 변환 시작 (template_id + 파일들) |
| `GET` | `/jobs/{id}/stream` | SSE 진행률 스트림 |
| `GET` | `/jobs/{id}/result` | 완성된 xlsx 파일 다운로드 |
| `GET` | `/jobs/{id}/result/pdf` | 증적용 PDF 파일 다운로드 |

**POST /jobs 요청 (multipart/form-data):**
```
template_id: str    # 등록된 템플릿 ID
files: File[]       # 영수증 파일들 (jpg/png/pdf/xlsx/pptx, 최대 50개)
```

**GET /jobs/{id}/stream — SSE 이벤트 형식:**
```json
{"status": "processing", "done": 5, "total": 20, "current_file": "receipt_006.jpg"}
{"status": "completed",  "done": 20, "total": 20,
 "download_url": "/jobs/abc123/result",
 "pdf_url": "/jobs/abc123/result/pdf"}
{"status": "failed",     "done": 3,  "total": 20, "error": "Ollama connection refused"}
```

**SSE 타임아웃 및 재연결 처리 (app.js):**
- Ollama 로컬 추론은 영수증 1장당 최대 60초 소요 가능 → SSE `retry: 60000` 헤더 설정
- 클라이언트는 `EventSource` 끊김 시 자동 재연결 + 마지막 `done` 카운트 표시 유지
- 에러 이벤트 수신 시 사용자에게 인라인 알림 표시 (toast / 상태 배너)
- `completed` 이벤트 수신 시 xlsx·pdf 다운로드 버튼 동시 노출

---

## 5. 핵심 로직 상세

### 5.1 전처리 파이프라인 (Preprocessor)

파일 확장자를 감지하여 적절한 전처리기로 분기한다. 모든 전처리기는 `ProcessedInput` 리스트를 반환한다.

**다중 페이지 처리 원칙:** PDF·PPTX에서 반환된 복수의 `ProcessedInput`은 각각 독립적인 영수증 1건으로 취급한다. `batch_processor.py`는 이를 순차적으로 Ollama에 전송하고 엑셀에 각각 새로운 행으로 누적한다.

```python
@dataclass
class ProcessedInput:
    source_name: str        # 원본 파일명 (로그·오류 추적용)
    source_page: int        # 페이지/슬라이드 번호 (단일 파일은 0)
    image_b64: str | None   # base64 인코딩 이미지 (이미지 입력 시)
    text: str | None        # 직접 추출 텍스트 (xlsx 입력 시)
    pil_image: Image | None # PIL.Image 원본 (PDF 병합용, xlsx은 None)
```

| 입력 형식 | 처리 방법 | 라이브러리 | PDF 병합용 이미지 |
|-----------|-----------|-----------|-----------------|
| `.jpg` / `.png` | PIL 로드 → base64 인코딩 | `Pillow` | O (PIL.Image 반환) |
| `.pdf` | 페이지별 이미지 렌더링 → base64 | `pymupdf` | O (페이지별 PIL.Image) |
| `.xlsx` | 시트 셀값 텍스트 직렬화 (이미지 변환 불필요) | `openpyxl` | X (None) |
| `.pptx` | 슬라이드별 이미지 렌더링 → base64 | `python-pptx` + `Pillow` | O (슬라이드별 PIL.Image) |

### 5.2 Ollama VLM 호출 (단일 파이프라인)

EasyOCR 없이 이미지를 gemma4 VLM에 직접 전달한다.

```python
# services/ollama_client.py

class OllamaClient:
    async def extract_receipt(
        self,
        input: ProcessedInput,
        system_prompt: str,
    ) -> ReceiptData:
        payload = {
            "model": self.model,      # 기본값 "gemma4" (.env OLLAMA_MODEL로 오버라이드)
            "system": system_prompt,
            "stream": False,
            "format": "json",         # Ollama JSON 모드 강제
        }

        if input.image_b64:
            # VLM 경로: 이미지 base64 직접 전달
            payload["prompt"] = "이 영수증에서 데이터를 추출하세요."
            payload["images"] = [input.image_b64]
        else:
            # 텍스트 경로: xlsx 등 텍스트 직접 추출 케이스
            payload["prompt"] = input.text

        response = await self.http.post("/api/generate", json=payload)
        return ReceiptData.model_validate_json(response.json()["response"])
```

### 5.3 시스템 프롬프트 관리 (계층적 우선순위)

프롬프트를 코드에 하드코딩하지 않는다. 우선순위는 다음과 같다:

```
[1순위] 템플릿 DB의 custom_prompt (템플릿별 개별 설정)
    ↓ 없으면
[2순위] .env의 OLLAMA_SYSTEM_PROMPT (전역 기본 프롬프트)
    ↓ 없으면
[3순위] .env.example에 명시된 기본값 (초기 설치 가이드)
```

**`.env.example` 기본값:**
```ini
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma4

# 전역 시스템 프롬프트 (템플릿별 커스텀 프롬프트가 없을 때 사용)
OLLAMA_SYSTEM_PROMPT="""
당신은 영수증·매출전표 데이터 추출 전문가입니다.
이미지 또는 텍스트에서 영수증 정보를 추출하여 반드시 아래 JSON 형식으로만 응답하세요.
마크다운 코드블록 없이 순수 JSON만 출력하세요.

{
  "날짜": "YYYY-MM-DD",
  "업체명": "string",
  "품목": "string",
  "금액": integer,
  "부가세": integer,
  "결제수단": "카드|현금|계좌이체|기타",
  "비고": "string or null"
}
"""
```

**`batch_processor.py` 프롬프트 결정 로직:**
```python
def resolve_prompt(template: Template, config: Config) -> str:
    return template.custom_prompt or config.ollama_system_prompt
```

**`PUT /templates/{id}/prompt`** 엔드포인트로 런타임에 프롬프트 교체 가능 (서버 재시작 불필요).

### 5.4 Named Range → 엑셀 행 매핑 (ExcelMapper)

**템플릿 작성 규칙:**
엑셀에서 헤더 셀에 `FIELD_` 접두사로 이름을 정의한다.

```
FIELD_날짜     → B열 헤더 셀
FIELD_업체명   → C열 헤더 셀
FIELD_품목     → D열 헤더 셀
FIELD_금액     → E열 헤더 셀
FIELD_부가세   → F열 헤더 셀
FIELD_결제수단 → G열 헤더 셀
DATA_START     → (선택) 데이터 시작 행 지정 셀
```

**DATA_START 결정 로직 (중요):**
```python
def resolve_data_start_row(wb: Workbook) -> int:
    """
    DATA_START Named Range가 있으면 그 행을 사용.
    없으면 FIELD_* Named Range 중 가장 큰 행번호 + 1을 데이터 시작행으로 사용.
    FIELD_* Named Range가 전혀 없으면 등록 단계에서 ValidationError.
    """
    defined = wb.defined_names

    if "DATA_START" in defined:
        _, cell_ref = list(defined["DATA_START"].destinations)[0]
        return int(cell_ref.replace("$", "").lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))

    max_header_row = 0
    for name in defined:
        if name.startswith("FIELD_"):
            _, cell_ref = list(defined[name].destinations)[0]
            row_num = int(cell_ref.replace("$", "").lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
            max_header_row = max(max_header_row, row_num)

    if max_header_row == 0:
        raise ValidationError("템플릿에 FIELD_* Named Range가 없습니다.")

    return max_header_row + 1
```

**매핑 로직:**
```python
from openpyxl.utils import column_index_from_string

def load_field_mapping(wb: Workbook) -> dict[str, int]:
    mapping = {}
    for name in wb.defined_names:
        if name.startswith("FIELD_"):
            field = name[6:]                              # "FIELD_날짜" → "날짜"
            destinations = list(wb.defined_names[name].destinations)
            _, cell_ref = destinations[0]                 # ('Sheet1', '$B$2')
            col_letter = cell_ref.replace("$", "")[0]
            mapping[field] = column_index_from_string(col_letter)
    return mapping

def append_receipt_row(ws, mapping: dict[str, int], data: ReceiptData, row: int):
    row_data = data.model_dump()
    for field, col in mapping.items():
        ws.cell(row=row, column=col, value=row_data.get(field))
```

### 5.5 증적용 PDF 생성 (PdfMerger)

배치 처리 중 수집된 `PIL.Image` 목록을 한 장의 PDF로 병합한다. xlsx 입력(이미지 없음)은 목록에 포함되지 않는다.

```python
# services/pdf_merger.py

from pathlib import Path
from PIL import Image

def merge_images_to_pdf(images: list[Image.Image], output_path: Path) -> None:
    """
    수집된 PIL.Image 목록을 순서대로 병합하여 단일 PDF 생성.
    images가 빈 리스트면 (xlsx만 업로드된 경우) 파일을 생성하지 않는다.
    """
    if not images:
        return

    rgb_images = [img.convert("RGB") for img in images]
    first, rest = rgb_images[0], rgb_images[1:]
    first.save(output_path, save_all=True, append_images=rest, format="PDF")
```

**batch_processor.py 통합 패턴:**
```python
async def run(self, job_id: str, template: Template, inputs: list[UploadFile]) -> None:
    pdf_pages: list[Image.Image] = []
    current_row = self.excel_mapper.data_start_row

    for upload in inputs:
        processed_list = await self.preprocessor.route_file(upload)
        # PDF/PPTX는 processed_list에 페이지 수만큼 항목이 들어옴 → 각각 1건 처리
        for processed in processed_list:
            try:
                receipt = await self.ollama.extract_receipt(processed, prompt)
                self.excel_mapper.append_receipt_row(ws, mapping, receipt, current_row)
                current_row += 1
                if processed.pil_image:
                    pdf_pages.append(processed.pil_image)
            except Exception as e:
                await self.job_manager.fail_file(job_id, processed.source_name)
            await self.job_manager.update(job_id, ...)

    wb.save(excel_path)
    merge_images_to_pdf(pdf_pages, pdf_path)
    await self.job_manager.complete(job_id, excel_path, pdf_path)
```

---

## 6. 데이터 스키마

```python
# schemas/template.py
class Template(BaseModel):
    template_id: str
    name: str
    fields: list[str]               # Named Range에서 추출한 필드 목록
    custom_prompt: str | None       # 템플릿별 시스템 프롬프트 (없으면 전역 사용)
    created_at: datetime

# schemas/job.py
class JobProgress(BaseModel):
    job_id: str
    template_id: str
    status: Literal["pending", "processing", "completed", "failed"]
    total: int
    done: int
    failed_files: list[str]         # 부분 실패 허용 — 실패 파일만 기록
    current_file: str | None = None
    download_url: str | None = None  # xlsx 다운로드 URL
    pdf_url: str | None = None       # 증적용 PDF 다운로드 URL
    error: str | None = None

# schemas/receipt.py
class ReceiptData(BaseModel):
    날짜: str
    업체명: str
    품목: str
    금액: int
    부가세: int
    결제수단: Literal["카드", "현금", "계좌이체", "기타"]
    비고: str | None = None
```

---

## 7. JobManager — 확장 가능 설계

```python
# core/job_manager.py

class JobManager(Protocol):
    """인터페이스: MVP는 InMemory, 추후 Redis로 교체 가능"""
    async def create(self, job_id: str, template_id: str, total: int) -> None: ...
    async def update(self, job_id: str, done: int, current_file: str) -> None: ...
    async def fail_file(self, job_id: str, filename: str) -> None: ...
    async def complete(self, job_id: str, result_path: str, pdf_path: str | None) -> None: ...
    async def fail(self, job_id: str, error: str) -> None: ...
    async def get(self, job_id: str) -> JobProgress: ...

class InMemoryJobManager:
    """MVP 구현 — 서버 재시작 시 상태 초기화됨"""
    def __init__(self):
        self._jobs: dict[str, JobProgress] = {}
        self._lock = asyncio.Lock()
    ...
```

---

## 8. 기술 스택 및 의존성

```
# requirements.txt

fastapi
uvicorn[standard]
python-multipart          # 파일 업로드
openpyxl                  # 엑셀 읽기/쓰기 + Named Range 처리
pymupdf                   # PDF → 이미지 변환
python-pptx               # PPTX → 슬라이드 이미지
Pillow                    # 이미지 처리 + base64 인코딩 + 증적 PDF 병합
httpx                     # Ollama API 비동기 HTTP 호출
aiosqlite                 # SQLite 비동기 (템플릿 메타데이터 DB)
pydantic-settings         # .env 기반 설정 관리
```

**Ollama 설치 및 모델 준비 (서버에서 1회):**
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemma4        # 기본 모델 (태그는 .env OLLAMA_MODEL로 지정)
ollama serve              # 백그라운드 서비스로 실행
```

---

## 9. 단계별 확장 경로 (향후)

| 단계 | 변경 사항 |
|------|-----------|
| MVP | InMemoryJobManager, SQLite, 단일 서버 |
| 확장 1 | RedisJobManager로 교체 → 서버 재시작 시 작업 보존 |
| 확장 2 | Celery 워커 도입 → 수평 확장, 동시 배치 처리 |
| 확장 3 | 작업 이력 DB 저장 → 관리 대시보드 |
| 확장 4 | 더 강력한 모델 투입 (gemma4 대형 태그, GPU 서버 확보 시) |

---

## 10. 구현 지침 (중요)

### 10.1 Ollama 모델 태그
- 코드 기본값: `gemma4` (하드코딩 금지, 항상 `config.ollama_model` 참조)
- 실제 서버 태그 확인 및 세팅: `.env` 파일의 `OLLAMA_MODEL` 값으로 주입

### 10.2 SSE 타임아웃 및 재연결 (app.js)
- SSE 응답 헤더에 `retry: 60000` 포함 (60초 재연결 간격)
- `EventSource` onerror 핸들러: 재연결 시도 중임을 사용자에게 표시
- 에러 이벤트 수신 시: toast 또는 상태 배너로 인라인 알림
- completed 이벤트: xlsx 다운로드 버튼 + PDF 다운로드 버튼 동시 활성화

### 10.3 DATA_START 폴백 로직 (excel_mapper.py)
- `DATA_START` Named Range 미설정 시: `FIELD_*` 중 가장 큰 행번호 + 1을 데이터 시작행으로 사용
- `FIELD_*` Named Range가 전혀 없으면 템플릿 등록 단계에서 ValidationError 반환

### 10.4 다중 페이지 처리 (batch_processor.py)
- PDF·PPTX 전처리 시 반환되는 N개의 `ProcessedInput`을 각각 독립 영수증 1건으로 처리
- Ollama 호출 → 엑셀 행 추가 → pdf_pages 누적을 순차적으로 반복
- 한 페이지 실패 시 해당 페이지만 `failed_files`에 기록하고 다음 페이지 계속 처리
