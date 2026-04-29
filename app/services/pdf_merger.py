from pathlib import Path

from PIL.Image import Image


def merge_to_pdf(images: list[Image], output_path: Path) -> None:
    """PIL.Image 목록을 순서대로 단일 PDF로 병합.
    images가 빈 리스트면 (xlsx-only 업로드) 파일을 생성하지 않는다."""
    if not images:
        return

    rgb_images = [img.convert("RGB") for img in images]
    first, rest = rgb_images[0], rgb_images[1:]
    first.save(output_path, save_all=True, append_images=rest, format="PDF")
