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
    assert "job_id" in data
    assert data["status"] == "pending"
    assert data["total"] == 1


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
    data = resp.json()
    assert "job_id" in data
    assert data["total"] == 2
