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
