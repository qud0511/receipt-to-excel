from __future__ import annotations

from app.services.docling_service import DoclingService
from . import ProcessedInput

_svc = DoclingService()


def process_presentation(file_bytes: bytes, source_name: str) -> list[ProcessedInput]:
    return _svc.process(file_bytes, source_name, source_name)
