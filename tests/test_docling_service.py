import pytest
from docling.datamodel.pipeline_options import EasyOcrOptions


def test_make_pipeline_options_uses_korean_easyocr():
    from app.services.docling_service import _make_pipeline_options
    opts = _make_pipeline_options()
    assert isinstance(opts.ocr_options, EasyOcrOptions)
    assert "ko" in opts.ocr_options.lang
    assert "en" in opts.ocr_options.lang
    assert opts.ocr_options.force_full_page_ocr is True


def test_make_pipeline_options_disables_heavy_analysis():
    from app.services.docling_service import _make_pipeline_options
    opts = _make_pipeline_options()
    assert opts.do_table_structure is False
    assert opts.do_picture_classification is False
    assert opts.do_picture_description is False


def test_make_pipeline_options_sets_high_scale():
    from app.services.docling_service import _make_pipeline_options
    opts = _make_pipeline_options()
    assert opts.images_scale >= 2.0
    assert opts.generate_page_images is True
