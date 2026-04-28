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
