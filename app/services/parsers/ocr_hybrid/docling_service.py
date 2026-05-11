"""Docling pipeline wrapper — 한글 EasyOCR + 무거운 분석 비활성.

docling 자체는 ``[ocr]`` extras. 본 모듈 import 는 docling 미설치 환경에서도 가능
(PipelineConfig 는 dataclass), 실제 추출 호출 시점에만 lazy import.
"""

from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass


@dataclass(frozen=True)
class PipelineConfig:
    """Docling PdfPipelineOptions 의 우리 도메인 추상화.

    CLAUDE.md §"특이사항": EasyOCR ``lang=["ko","en"], force_full_page_ocr=True`` (v1 자산).
    CLAUDE.md §"성능": Phase 5/6 까지 table/picture/formula 분석 비활성 (메모리/지연 절감).
    """

    languages: tuple[str, ...] = ("ko", "en")
    force_full_page_ocr: bool = True
    do_table_structure: bool = False
    do_picture_classification: bool = False
    do_picture_description: bool = False
    do_formula_enrichment: bool = False


def default_pipeline_config() -> PipelineConfig:
    return PipelineConfig()


class DoclingService:
    """docling DocumentConverter wrapper — lazy import for [ocr] extras."""

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self._config = config or default_pipeline_config()

    @property
    def config(self) -> PipelineConfig:
        return self._config

    async def extract_text(self, content: bytes) -> str:
        # 블로킹 호출 — async 컨텍스트 차단 방지 (CLAUDE.md §"성능").
        return await asyncio.to_thread(self._extract_sync, content)

    def _extract_sync(self, content: bytes) -> str:
        # docling lazy import — [ocr] 미설치 시 ImportError 가 호출 시점에 raise.
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        opts = PdfPipelineOptions()
        opts.do_table_structure = self._config.do_table_structure
        opts.do_picture_classification = self._config.do_picture_classification
        opts.do_picture_description = self._config.do_picture_description
        opts.do_formula_enrichment = self._config.do_formula_enrichment
        opts.ocr_options.lang = list(self._config.languages)
        opts.ocr_options.force_full_page_ocr = self._config.force_full_page_ocr

        converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
        )
        result = converter.convert(io.BytesIO(content))
        return str(result.document.export_to_markdown())
