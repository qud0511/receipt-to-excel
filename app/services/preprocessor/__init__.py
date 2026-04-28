from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL.Image import Image as PilImage


@dataclass
class ProcessedInput:
    source_name: str        # 원본 파일명 (로그·오류 추적용)
    source_page: int        # 페이지/슬라이드 번호 (단일 파일은 0)
    image_b64: str | None   # base64 인코딩 이미지 (VLM 전송용)
    text: str | None        # 직접 추출 텍스트 (xlsx 전용)
    pil_image: PilImage | None  # 증적 PDF 병합용 원본 이미지 (xlsx은 None)


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
