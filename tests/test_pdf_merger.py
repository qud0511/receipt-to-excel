import pytest
from PIL import Image
from app.services.pdf_merger import merge_to_pdf


def make_image(color: str = "white", size: tuple = (200, 150)) -> Image.Image:
    return Image.new("RGB", size, color=color)


def test_merge_single_image(tmp_path):
    out = tmp_path / "out.pdf"
    merge_to_pdf([make_image("red")], out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_merge_multiple_images(tmp_path):
    out = tmp_path / "out.pdf"
    images = [make_image("red"), make_image("blue"), make_image("green")]
    merge_to_pdf(images, out)
    assert out.exists()


def test_merge_empty_list_does_not_create_file(tmp_path):
    out = tmp_path / "out.pdf"
    merge_to_pdf([], out)
    assert not out.exists()


def test_merge_rgba_image_converted(tmp_path):
    out = tmp_path / "out.pdf"
    img = Image.new("RGBA", (100, 80), color=(255, 0, 0, 128))
    merge_to_pdf([img], out)
    assert out.exists()
