from __future__ import annotations

import tempfile
from collections import defaultdict
from pathlib import Path

from PIL import Image as PilImage

from app.services.preprocessor import ProcessedInput


class DoclingService:
    """DocumentConverter 싱글턴 래퍼. 모든 파일 타입을 ProcessedInput 목록으로 변환."""

    def __init__(self) -> None:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions

        pdf_opts = PdfPipelineOptions(generate_page_images=True)
        self._converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_opts),
            }
        )

    def process(self, file_bytes: bytes, filename: str, source_name: str) -> list[ProcessedInput]:
        suffix = Path(filename).suffix.lower()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(file_bytes)
            tmp_path = Path(f.name)

        try:
            result = self._converter.convert(str(tmp_path))
        finally:
            tmp_path.unlink(missing_ok=True)

        doc = result.document

        if suffix in (".pdf", ".pptx"):
            return self._split_by_page(doc, source_name)
        else:
            return self._single_page(doc, source_name, suffix, file_bytes)

    # ------------------------------------------------------------------
    def _split_by_page(self, doc, source_name: str) -> list[ProcessedInput]:
        page_texts: dict[int, list[str]] = defaultdict(list)
        for item, _level in doc.iterate_items():
            provs = getattr(item, "prov", None) or []
            for prov in provs:
                page_no = getattr(prov, "page_no", None)
                if page_no is None:
                    continue
                text = getattr(item, "text", None)
                if text:
                    page_texts[page_no].append(text)

        if not page_texts:
            full = doc.export_to_markdown()
            return [ProcessedInput(source_name=source_name, source_page=0,
                                   docling_text=full, pil_image=None)]

        results: list[ProcessedInput] = []
        for page_no in sorted(page_texts.keys()):
            text = "\n".join(page_texts[page_no])
            pil_img = self._page_image(doc, page_no)
            results.append(ProcessedInput(
                source_name=source_name,
                source_page=page_no - 1,  # Docling 1-indexed → 0-indexed
                docling_text=text,
                pil_image=pil_img,
            ))
        return results

    def _single_page(
        self, doc, source_name: str, suffix: str, file_bytes: bytes
    ) -> list[ProcessedInput]:
        text = doc.export_to_markdown()
        pil_img: PilImage.Image | None = None
        if suffix in (".jpg", ".jpeg", ".png"):
            import io
            pil_img = PilImage.open(io.BytesIO(file_bytes)).convert("RGB")
        return [ProcessedInput(source_name=source_name, source_page=0,
                               docling_text=text, pil_image=pil_img)]

    @staticmethod
    def _page_image(doc, page_no: int) -> PilImage.Image | None:
        page = (doc.pages or {}).get(page_no)
        if page is None:
            return None
        img_ref = getattr(page, "image", None)
        if img_ref is None:
            return None
        return getattr(img_ref, "pil_image", None)
