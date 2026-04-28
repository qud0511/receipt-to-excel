import base64
import io

from PIL import Image

from . import ProcessedInput


def process_image(file_bytes: bytes, source_name: str) -> list[ProcessedInput]:
    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return [ProcessedInput(
        source_name=source_name,
        source_page=0,
        image_b64=b64,
        text=None,
        pil_image=img,
    )]
