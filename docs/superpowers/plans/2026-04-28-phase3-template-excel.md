# Phase 3 — Template Store, Excel Mapper, xlsx Download

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** xlsx 템플릿 등록/CRUD API, Named Range 기반 ExcelMapper, BatchProcessor 엑셀 쓰기 통합, 완성된 xlsx 다운로드 엔드포인트를 구현한다.

**Architecture:** `TemplateStore` 가 SQLite(메타) + 파일시스템(xlsx 원본)을 관리한다. `ExcelMapper` 는 템플릿의 Named Range(`FIELD_*`)를 읽어 열 번호를 매핑하고, `DATA_START` Named Range가 없으면 FIELD 헤더 최대 행+1을 시작 행으로 결정한다. `BatchProcessor` 는 OCR 결과를 모아 마지막에 엑셀에 일괄 기록한다. FastAPI `lifespan` 에서 SQLite 스키마를 초기화한다.

**Tech Stack:** openpyxl, aiosqlite, FastAPI lifespan

**전제:** Phase 2 완료

---

**Definition of Done:**
```bash
# 1. 서버 기동
source .venv/bin/activate && uvicorn app.main:app --reload

# 2. 템플릿 등록 (Named Range 있는 xlsx 필요 → 아래 스크립트로 생성)
python3 scripts/make_sample_template.py   # → tests/fixtures/template.xlsx 생성
curl -s -X POST http://localhost:8000/templates \
  -F "file=@tests/fixtures/template.xlsx" \
  -F "name=지출결의서" | python3 -m json.tool
# 기대: {"template_id": "tpl_...", "name": "지출결의서", "fields": [...]}

# 3. 영수증 업로드 (template_id 포함)
TPL_ID="tpl_xxxxxxxx"
JOB=$(curl -s -X POST http://localhost:8000/jobs \
  -F "template_id=$TPL_ID" \
  -F "files=@tests/fixtures/sample.jpg" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")

# 4. SSE 완료 대기
curl -N "http://localhost:8000/jobs/$JOB/stream"

# 5. xlsx 다운로드
curl -OJ "http://localhost:8000/jobs/$JOB/result"
# → 지출결의서_$JOB.xlsx 파일 생성 확인
```

---

## 파일 구조

```
app/
  main.py                            (MODIFY — lifespan 추가, templates 라우터 등록)
  api/
    deps.py                          (MODIFY — TemplateStore 추가)
    routes/
      jobs.py                        (MODIFY — template_id Form 추가, result 엔드포인트 추가)
      templates.py                   (NEW)
  services/
    template_store.py                (NEW)
    excel_mapper.py                  (NEW)
    batch_processor.py               (MODIFY — 엑셀 쓰기 추가)

scripts/
  make_sample_template.py            (NEW — 테스트용 템플릿 생성 스크립트)

tests/
  test_template_store.py             (NEW)
  test_excel_mapper.py               (NEW)
  test_templates_api.py              (NEW)
```

---

## Task 1: TemplateStore (SQLite + 파일시스템)

**Files:**
- Create: `app/services/template_store.py`
- Create: `tests/test_template_store.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_template_store.py`:
```python
import io
import pytest
from openpyxl import Workbook
from app.services.template_store import TemplateStore


def make_dummy_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws["B2"] = "날짜"
    ws["C2"] = "금액"
    wb.defined_names["FIELD_날짜"] = "Sheet!$B$2"
    wb.defined_names["FIELD_금액"] = "Sheet!$C$2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
def store(tmp_data_dir):
    return TemplateStore(data_dir=tmp_data_dir)


async def test_init_and_list_empty(store):
    await store.init_db()
    templates = await store.list_all()
    assert templates == []


async def test_save_and_get(store):
    await store.init_db()
    t = await store.save(
        name="지출결의서",
        fields=["날짜", "금액"],
        xlsx_bytes=make_dummy_xlsx(),
    )
    assert t.template_id.startswith("tpl_")
    assert t.name == "지출결의서"
    assert t.has_custom_prompt is False

    fetched = await store.get(t.template_id)
    assert fetched.template_id == t.template_id


async def test_update_prompt(store):
    await store.init_db()
    t = await store.save(name="A", fields=["날짜"], xlsx_bytes=make_dummy_xlsx())
    updated = await store.update_prompt(t.template_id, "새 프롬프트")
    assert updated.custom_prompt == "새 프롬프트"
    assert updated.has_custom_prompt is True


async def test_delete(store):
    await store.init_db()
    t = await store.save(name="A", fields=["날짜"], xlsx_bytes=make_dummy_xlsx())
    await store.delete(t.template_id)
    with pytest.raises(KeyError):
        await store.get(t.template_id)
    assert not store.template_path(t.template_id).exists()


async def test_get_nonexistent_raises(store):
    await store.init_db()
    with pytest.raises(KeyError):
        await store.get("tpl_notexist")
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
source .venv/bin/activate && pytest tests/test_template_store.py -v
```
Expected: `ImportError`

- [ ] **Step 3: `app/services/template_store.py` 작성**

```python
import uuid
from datetime import datetime
from pathlib import Path

import aiosqlite

from app.schemas.template import Template


class TemplateStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.db_path = data_dir / "templates.db"
        self.templates_dir = data_dir / "templates"
        self.templates_dir.mkdir(parents=True, exist_ok=True)

    def template_path(self, template_id: str) -> Path:
        return self.templates_dir / f"{template_id}.xlsx"

    async def init_db(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS templates (
                    template_id   TEXT PRIMARY KEY,
                    name          TEXT NOT NULL,
                    fields        TEXT NOT NULL,
                    custom_prompt TEXT,
                    created_at    TEXT NOT NULL
                )
            """)
            await db.commit()

    async def save(
        self,
        name: str,
        fields: list[str],
        xlsx_bytes: bytes,
        custom_prompt: str | None = None,
    ) -> Template:
        template_id = f"tpl_{uuid.uuid4().hex[:8]}"
        created_at = datetime.utcnow()
        self.template_path(template_id).write_bytes(xlsx_bytes)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO templates VALUES (?, ?, ?, ?, ?)",
                (template_id, name, ",".join(fields), custom_prompt, created_at.isoformat()),
            )
            await db.commit()
        return Template(
            template_id=template_id,
            name=name,
            fields=fields,
            custom_prompt=custom_prompt,
            created_at=created_at,
        )

    async def list_all(self) -> list[Template]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM templates ORDER BY created_at DESC"
            ) as cur:
                rows = await cur.fetchall()
        return [_row_to_template(r) for r in rows]

    async def get(self, template_id: str) -> Template:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM templates WHERE template_id = ?", (template_id,)
            ) as cur:
                row = await cur.fetchone()
        if row is None:
            raise KeyError(f"Template {template_id!r} not found")
        return _row_to_template(row)

    async def update_prompt(self, template_id: str, prompt: str) -> Template:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE templates SET custom_prompt = ? WHERE template_id = ?",
                (prompt, template_id),
            )
            await db.commit()
        return await self.get(template_id)

    async def delete(self, template_id: str) -> None:
        path = self.template_path(template_id)
        if path.exists():
            path.unlink()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM templates WHERE template_id = ?", (template_id,)
            )
            await db.commit()


def _row_to_template(row: aiosqlite.Row) -> Template:
    return Template(
        template_id=row["template_id"],
        name=row["name"],
        fields=row["fields"].split(","),
        custom_prompt=row["custom_prompt"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
source .venv/bin/activate && pytest tests/test_template_store.py -v
```
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add app/services/template_store.py tests/test_template_store.py
git commit -m "feat: TemplateStore — SQLite metadata + filesystem xlsx storage"
```

---

## Task 2: ExcelMapper (Named Range → 행 추가)

**Files:**
- Create: `app/services/excel_mapper.py`
- Create: `tests/test_excel_mapper.py`
- Create: `scripts/make_sample_template.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_excel_mapper.py`:
```python
import io
import re
import pytest
from openpyxl import Workbook, load_workbook
from app.services.excel_mapper import build_excel, validate_template
from app.schemas.receipt import ReceiptData


def make_template_xlsx(with_data_start: bool = False) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws["B2"] = "날짜"
    ws["C2"] = "업체명"
    ws["D2"] = "금액"
    wb.defined_names["FIELD_날짜"] = "Sheet1!$B$2"
    wb.defined_names["FIELD_업체명"] = "Sheet1!$C$2"
    wb.defined_names["FIELD_금액"] = "Sheet1!$D$2"
    if with_data_start:
        ws["A5"] = "data_start_marker"
        wb.defined_names["DATA_START"] = "Sheet1!$A$5"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def make_receipt(name: str = "스타벅스", amount: int = 5500) -> ReceiptData:
    return ReceiptData(
        날짜="2024-01-15", 업체명=name, 품목="아메리카노",
        금액=amount, 부가세=500, 결제수단="카드",
    )


def test_validate_template_returns_fields(tmp_path):
    xlsx = make_template_xlsx()
    fields = validate_template(xlsx)
    assert set(fields) == {"날짜", "업체명", "금액"}


def test_validate_template_no_fields_raises(tmp_path):
    wb = Workbook()
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(ValueError, match="FIELD_"):
        validate_template(buf.getvalue())


def test_build_excel_writes_rows(tmp_path):
    template_bytes = make_template_xlsx()
    template_path = tmp_path / "template.xlsx"
    template_path.write_bytes(template_bytes)
    output_path = tmp_path / "result.xlsx"

    receipts = [make_receipt("A", 1000), make_receipt("B", 2000)]
    build_excel(template_path, output_path, receipts)

    wb = load_workbook(output_path)
    ws = wb.active
    # DATA_START 없음 → FIELD 최대 행(2) + 1 = 3 행부터 데이터
    assert ws.cell(row=3, column=3).value == "A"  # 업체명 C열
    assert ws.cell(row=4, column=3).value == "B"


def test_build_excel_with_data_start(tmp_path):
    template_bytes = make_template_xlsx(with_data_start=True)
    template_path = tmp_path / "template.xlsx"
    template_path.write_bytes(template_bytes)
    output_path = tmp_path / "result.xlsx"

    build_excel(template_path, output_path, [make_receipt("X", 9999)])

    wb = load_workbook(output_path)
    ws = wb.active
    # DATA_START = 5행
    assert ws.cell(row=5, column=3).value == "X"
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
source .venv/bin/activate && pytest tests/test_excel_mapper.py -v
```
Expected: `ImportError`

- [ ] **Step 3: `app/services/excel_mapper.py` 작성**

```python
import re
import shutil
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string

from app.schemas.receipt import ReceiptData


def validate_template(xlsx_bytes: bytes) -> list[str]:
    """FIELD_* Named Range 목록을 반환. 없으면 ValueError."""
    import io
    wb = load_workbook(io.BytesIO(xlsx_bytes))
    fields = _field_mapping(wb)
    wb.close()
    if not fields:
        raise ValueError("템플릿에 FIELD_* Named Range가 없습니다.")
    return list(fields.keys())


def build_excel(
    template_path: Path,
    output_path: Path,
    receipts: list[ReceiptData],
) -> None:
    shutil.copy2(template_path, output_path)
    wb = load_workbook(output_path)
    ws = wb.active
    mapping = _field_mapping(wb)
    start_row = _data_start_row(wb)

    for i, receipt in enumerate(receipts):
        row = start_row + i
        row_data = receipt.model_dump()
        for field, col in mapping.items():
            ws.cell(row=row, column=col, value=row_data.get(field))

    wb.save(output_path)
    wb.close()


def _field_mapping(wb) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for name in wb.defined_names:
        if name.startswith("FIELD_"):
            field = name[6:]
            _, cell_ref = list(wb.defined_names[name].destinations)[0]
            col_letter = re.sub(r"[\$\d]", "", cell_ref)
            mapping[field] = column_index_from_string(col_letter)
    return mapping


def _data_start_row(wb) -> int:
    defined = wb.defined_names
    if "DATA_START" in defined:
        _, cell_ref = list(defined["DATA_START"].destinations)[0]
        return int(re.sub(r"[^\d]", "", cell_ref))

    max_row = 0
    for name in defined:
        if name.startswith("FIELD_"):
            _, cell_ref = list(defined[name].destinations)[0]
            row = int(re.sub(r"[^\d]", "", cell_ref))
            max_row = max(max_row, row)

    if max_row == 0:
        raise ValueError("템플릿에 FIELD_* Named Range가 없습니다.")
    return max_row + 1
```

- [ ] **Step 4: `scripts/make_sample_template.py` 작성 (DoD 수동 확인용)**

```bash
mkdir -p scripts
```

`scripts/make_sample_template.py`:
```python
"""
지출결의서 샘플 템플릿(Named Range 포함)을 생성합니다.
출력: tests/fixtures/template.xlsx
"""
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

Path("tests/fixtures").mkdir(parents=True, exist_ok=True)

wb = Workbook()
ws = wb.active
ws.title = "지출결의서"

# 제목행
ws["A1"] = "지출결의서"
ws["A1"].font = Font(bold=True, size=14)

# 헤더행 (행 3)
headers = ["날짜", "업체명", "품목", "금액", "부가세", "결제수단", "비고"]
cols    = ["B",   "C",    "D",   "E",   "F",    "G",    "H"]
for col, header in zip(cols, headers):
    cell = ws[f"{col}3"]
    cell.value = header
    cell.font = Font(bold=True)
    cell.fill = PatternFill("solid", fgColor="DDEBF7")
    cell.alignment = Alignment(horizontal="center")
    # Named Range 등록
    wb.defined_names[f"FIELD_{header}"] = f"지출결의서!${col}$3"

# DATA_START = 4행
ws["A4"] = ""
wb.defined_names["DATA_START"] = "지출결의서!$B$4"

out = Path("tests/fixtures/template.xlsx")
wb.save(out)
print(f"Template saved: {out}")
print(f"Fields: {headers}")
```

- [ ] **Step 5: 테스트 실행 — 통과 확인**

```bash
source .venv/bin/activate && pytest tests/test_excel_mapper.py -v
```
Expected: `4 passed`

- [ ] **Step 6: Commit**

```bash
git add app/services/excel_mapper.py tests/test_excel_mapper.py scripts/
git commit -m "feat: ExcelMapper — Named Range field mapping and DATA_START row resolution"
```

---

## Task 3: Template API (CRUD)

**Files:**
- Create: `app/api/routes/templates.py`
- Modify: `app/api/deps.py` (TemplateStore 추가)
- Modify: `app/main.py` (lifespan + templates 라우터 등록)
- Create: `tests/test_templates_api.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_templates_api.py`:
```python
import io
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook


def make_valid_template_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws["B2"] = "날짜"
    wb.defined_names["FIELD_날짜"] = "Sheet1!$B$2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
def client(tmp_data_dir, monkeypatch):
    import app.api.deps as deps
    # 테스트용 임시 경로 사용
    from app.services.template_store import TemplateStore
    store = TemplateStore(data_dir=tmp_data_dir)
    deps._template_store = store

    import asyncio
    asyncio.get_event_loop().run_until_complete(store.init_db())

    from app.main import app
    return TestClient(app)


def test_register_template(client):
    resp = client.post(
        "/templates",
        files={"file": ("t.xlsx", make_valid_template_bytes(), "application/octet-stream")},
        data={"name": "지출결의서"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["template_id"].startswith("tpl_")
    assert "날짜" in data["fields"]


def test_register_invalid_template(client):
    wb = Workbook()
    buf = io.BytesIO()
    wb.save(buf)
    resp = client.post(
        "/templates",
        files={"file": ("bad.xlsx", buf.getvalue(), "application/octet-stream")},
        data={"name": "bad"},
    )
    assert resp.status_code == 422


def test_list_templates(client):
    client.post(
        "/templates",
        files={"file": ("t.xlsx", make_valid_template_bytes(), "application/octet-stream")},
        data={"name": "A"},
    )
    resp = client.get("/templates")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_delete_template(client):
    reg = client.post(
        "/templates",
        files={"file": ("t.xlsx", make_valid_template_bytes(), "application/octet-stream")},
        data={"name": "del"},
    )
    tid = reg.json()["template_id"]
    resp = client.delete(f"/templates/{tid}")
    assert resp.status_code == 204
    assert client.get(f"/templates/{tid}").status_code == 404
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
source .venv/bin/activate && pytest tests/test_templates_api.py -v
```
Expected: `ImportError`

- [ ] **Step 3: `app/api/routes/templates.py` 작성**

```python
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile

from app.api.deps import get_template_store
from app.schemas.template import Template
from app.services.excel_mapper import validate_template
from app.services.template_store import TemplateStore

router = APIRouter()


@router.post("", response_model=Template)
async def register_template(
    file: UploadFile = File(...),
    name: str = Form(...),
    system_prompt: str | None = Form(None),
    store: TemplateStore = Depends(get_template_store),
):
    content = await file.read()
    try:
        fields = validate_template(content)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return await store.save(name=name, fields=fields, xlsx_bytes=content, custom_prompt=system_prompt)


@router.get("", response_model=list[Template])
async def list_templates(store: TemplateStore = Depends(get_template_store)):
    return await store.list_all()


@router.get("/{template_id}", response_model=Template)
async def get_template(
    template_id: str,
    store: TemplateStore = Depends(get_template_store),
):
    try:
        return await store.get(template_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Template not found")


@router.put("/{template_id}/prompt", response_model=Template)
async def update_prompt(
    template_id: str,
    prompt: str = Form(...),
    store: TemplateStore = Depends(get_template_store),
):
    try:
        return await store.update_prompt(template_id, prompt)
    except KeyError:
        raise HTTPException(status_code=404, detail="Template not found")


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: str,
    store: TemplateStore = Depends(get_template_store),
):
    try:
        await store.delete(template_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Template not found")
    return Response(status_code=204)
```

- [ ] **Step 4: `app/api/deps.py` 수정 (TemplateStore 추가)**

```python
from app.core.config import get_config
from app.core.job_manager import InMemoryJobManager
from app.services.ollama_client import OllamaClient
from app.services.template_store import TemplateStore

_job_manager: InMemoryJobManager | None = None
_template_store: TemplateStore | None = None


def get_job_manager() -> InMemoryJobManager:
    global _job_manager
    if _job_manager is None:
        _job_manager = InMemoryJobManager()
    return _job_manager


def get_ollama_client() -> OllamaClient:
    config = get_config()
    return OllamaClient(base_url=config.ollama_base_url, model=config.ollama_model)


def get_template_store() -> TemplateStore:
    global _template_store
    if _template_store is None:
        config = get_config()
        _template_store = TemplateStore(data_dir=config.data_dir)
    return _template_store
```

- [ ] **Step 5: `app/main.py` 수정 (lifespan + templates 라우터)**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.deps import get_template_store
from app.api.routes import jobs, templates


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = get_template_store()
    await store.init_db()
    yield


app = FastAPI(title="Receipt to Excel", lifespan=lifespan)

app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(templates.router, prefix="/templates", tags=["templates"])
```

- [ ] **Step 6: 테스트 실행 — 통과 확인**

```bash
source .venv/bin/activate && pytest tests/test_templates_api.py -v
```
Expected: `4 passed`

- [ ] **Step 7: Commit**

```bash
git add app/api/routes/templates.py app/api/deps.py app/main.py tests/test_templates_api.py
git commit -m "feat: Template CRUD API and TemplateStore SQLite integration"
```

---

## Task 4: BatchProcessor 엑셀 쓰기 통합 + POST /jobs template_id + xlsx 다운로드

**Files:**
- Modify: `app/services/batch_processor.py`
- Modify: `app/api/routes/jobs.py`

- [ ] **Step 1: `app/services/batch_processor.py` 전체 교체**

```python
from pathlib import Path

from app.core.config import Config
from app.core.job_manager import InMemoryJobManager
from app.schemas.receipt import ReceiptData
from app.services.excel_mapper import build_excel
from app.services.ollama_client import OllamaClient
from app.services.preprocessor import ProcessedInput
from app.services.template_store import TemplateStore


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

        for i, processed in enumerate(inputs):
            await job_manager.update(job_id, done=i, current_file=processed.source_name)
            try:
                receipt = await ollama.extract_receipt(processed, system_prompt)
                receipts.append(receipt)
            except Exception:
                label = f"{processed.source_name}:p{processed.source_page}"
                await job_manager.fail_file(job_id, label)

        jobs_dir = config.data_dir / "jobs" / job_id
        jobs_dir.mkdir(parents=True, exist_ok=True)
        excel_path = jobs_dir / "result.xlsx"

        build_excel(template_store.template_path(template_id), excel_path, receipts)

        await job_manager.complete(job_id, download_url=f"/jobs/{job_id}/result")
    except Exception as e:
        await job_manager.fail(job_id, str(e))
```

- [ ] **Step 2: batch_processor 테스트 업데이트**

`tests/test_batch_processor.py` 의 `run_job` 호출 시그니처를 업데이트한다.
기존 `await run_job("j1", inputs, mgr, ollama, config)` →
`await run_job("j1", inputs, "tpl_x", mgr, ollama, mock_template_store, config)` 로 교체.

완성된 `tests/test_batch_processor.py`:
```python
import io
import pytest
from unittest.mock import AsyncMock, MagicMock
from openpyxl import Workbook

from app.services.batch_processor import run_job
from app.core.job_manager import InMemoryJobManager
from app.services.preprocessor import ProcessedInput
from app.schemas.receipt import ReceiptData
from app.schemas.template import Template
from datetime import datetime


def make_input(name: str, page: int = 0) -> ProcessedInput:
    return ProcessedInput(
        source_name=name, source_page=page,
        image_b64="aGVsbG8=", text=None, pil_image=None,
    )


def make_receipt(name: str = "스타벅스") -> ReceiptData:
    return ReceiptData(
        날짜="2024-01-15", 업체명=name, 품목="아메리카노",
        금액=5500, 부가세=500, 결제수단="카드",
    )


def make_template_xlsx_path(tmp_path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws["B2"] = "날짜"
    ws["C2"] = "업체명"
    wb.defined_names["FIELD_날짜"] = "Sheet1!$B$2"
    wb.defined_names["FIELD_업체명"] = "Sheet1!$C$2"
    (tmp_path / "templates").mkdir(exist_ok=True)
    path = tmp_path / "templates" / "tpl_test.xlsx"
    wb.save(path)


def make_mock_store(tmp_data_dir) -> MagicMock:
    make_template_xlsx_path(tmp_data_dir)
    store = MagicMock()
    store.get = AsyncMock(return_value=Template(
        template_id="tpl_test", name="A",
        fields=["날짜", "업체명"], custom_prompt=None,
        created_at=datetime.utcnow(),
    ))
    store.template_path = MagicMock(
        return_value=tmp_data_dir / "templates" / "tpl_test.xlsx"
    )
    return store


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


async def test_run_job_partial_failure(tmp_data_dir):
    mgr = InMemoryJobManager()
    await mgr.create("j1", template_id="tpl_test", total=2)

    ollama = MagicMock()
    ollama.extract_receipt = AsyncMock(side_effect=Exception("timeout"))

    config = MagicMock()
    config.ollama_system_prompt = "prompt"
    config.data_dir = tmp_data_dir

    inputs = [make_input("a.jpg"), make_input("b.jpg")]
    await run_job("j1", inputs, "tpl_test", mgr, ollama, make_mock_store(tmp_data_dir), config)

    job = await mgr.get("j1")
    assert job.status == "completed"
    assert len(job.failed_files) == 2
```

- [ ] **Step 3: 테스트 실행 — 통과 확인**

```bash
source .venv/bin/activate && pytest tests/test_batch_processor.py -v
```
Expected: `2 passed`

- [ ] **Step 4: `app/api/routes/jobs.py` 전체 교체**

```python
import asyncio
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from app.api.deps import get_job_manager, get_ollama_client, get_template_store
from app.core.config import Config, get_config
from app.core.job_manager import InMemoryJobManager
from app.services.batch_processor import run_job
from app.services.ollama_client import OllamaClient
from app.services.preprocessor import route_file
from app.services.template_store import TemplateStore

router = APIRouter()


@router.post("")
async def create_job(
    files: list[UploadFile] = File(...),
    template_id: str = Form(...),
    background_tasks: BackgroundTasks = None,
    job_manager: InMemoryJobManager = Depends(get_job_manager),
    ollama: OllamaClient = Depends(get_ollama_client),
    template_store: TemplateStore = Depends(get_template_store),
    config: Config = Depends(get_config),
):
    try:
        await template_store.get(template_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Template not found")

    all_inputs = []
    for f in files:
        content = await f.read()
        try:
            all_inputs.extend(route_file(content, f.filename or "unknown"))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    job_id = uuid.uuid4().hex[:8]
    await job_manager.create(job_id, template_id=template_id, total=len(all_inputs))

    background_tasks.add_task(
        run_job, job_id, all_inputs, template_id,
        job_manager, ollama, template_store, config,
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


@router.get("/{job_id}/result")
async def download_excel(
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

    excel_path = config.data_dir / "jobs" / job_id / "result.xlsx"
    if not excel_path.exists():
        raise HTTPException(status_code=404, detail="Excel file not found")

    return FileResponse(
        path=excel_path,
        filename=f"지출결의서_{job_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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
git commit -m "feat: BatchProcessor writes Excel; POST /jobs requires template_id; GET /jobs/{id}/result"
```

---

## Self-Review

| 스펙 요구사항 | 구현 태스크 |
|--------------|------------|
| Named Range FIELD_* → 열 매핑 | Task 2 — `_field_mapping()` |
| DATA_START 폴백 로직 | Task 2 — `_data_start_row()` |
| 등록 시 FIELD_* 없으면 ValidationError | Task 2 — `validate_template()` |
| custom_prompt 우선, 없으면 env 전역 | Task 4 — `template.custom_prompt or config.ollama_system_prompt` |
| template_id 없는 잡 생성 시 404 | Task 4 — jobs.py 검증 |
| xlsx 파일 다운로드 | Task 4 — `GET /jobs/{id}/result` |
| PUT /templates/{id}/prompt 런타임 교체 | Task 3 — templates.py |

**플레이스홀더 없음.**  
**타입 일관성** — `run_job` 시그니처 Task 3 정의 ↔ Task 4 호출 동일 (6인자 + template_id 추가).
