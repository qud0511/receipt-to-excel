import base64
import io

import fitz  # pymupdf
from PIL import Image

from . import ProcessedInput


def process_pdf(file_bytes: bytes, source_name: str) -> list[ProcessedInput]:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    results: list[ProcessedInput] = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))  # 2× 해상도
        img_bytes = pix.tobytes("png")
        b64 = base64.b64encode(img_bytes).decode()
        pil_img = Image.open(io.BytesIO(img_bytes)).copy()
        results.append(ProcessedInput(
            source_name=source_name,
            source_page=page_num,
            image_b64=b64,
            text=None,
            pil_image=pil_img,
        ))
    doc.close()
    return results
