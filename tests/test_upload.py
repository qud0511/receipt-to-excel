import io
import asyncio
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from openpyxl.workbook.defined_name import DefinedName
from PIL import Image


def make_valid_template_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws["B2"] = "날짜"
    wb.defined_names.add(DefinedName("FIELD_날짜", attr_text="Sheet1!$B$2"))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
def client(tmp_data_dir):
    import app.api.deps as deps
    from app.services.template_store import TemplateStore
    store = TemplateStore(data_dir=tmp_data_dir)
    deps._template_store = store
    asyncio.get_event_loop().run_until_complete(store.init_db())

    from app.main import app
    return TestClient(app)


@pytest.fixture
def template_id(client) -> str:
    resp = client.post(
        "/templates",
        files={"file": ("t.xlsx", make_valid_template_bytes(), "application/octet-stream")},
        data={"name": "테스트"},
    )
    return resp.json()["template_id"]


@pytest.fixture
def jpg_bytes() -> bytes:
    img = Image.new("RGB", (100, 80), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_upload_single_image(client, template_id, jpg_bytes):
    resp = client.post(
        "/jobs",
        files={"files": ("receipt.jpg", jpg_bytes, "image/jpeg")},
        data={"template_id": template_id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "pending"
    assert data["total"] == 1


def test_upload_unsupported_type(client, template_id):
    resp = client.post(
        "/jobs",
        files={"files": ("notes.txt", b"hello", "text/plain")},
        data={"template_id": template_id},
    )
    assert resp.status_code == 422


def test_upload_multiple_files(client, template_id, jpg_bytes):
    resp = client.post(
        "/jobs",
        files=[
            ("files", ("a.jpg", jpg_bytes, "image/jpeg")),
            ("files", ("b.jpg", jpg_bytes, "image/jpeg")),
        ],
        data={"template_id": template_id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["total"] == 2
