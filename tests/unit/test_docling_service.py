"""Phase 4 사후 회귀 — DoclingService._extract_sync 가 BytesIO 가 아닌 DocumentStream 사용.

배경: DocumentConverter.convert() 는 ``Path | str | DocumentStream`` 만 허용 (docling
Pydantic strict). 본 회귀가 test_ocr_hybrid_parser.py 의 mock 으로는 가려졌던 실제 버그.
"""

from __future__ import annotations

import pytest
from app.services.parsers.ocr_hybrid.docling_service import DoclingService

# [ocr] 미설치 환경에서는 skip — docling 자체가 의존성.
pytest.importorskip("docling")


def test_extract_sync_wraps_bytes_in_documentstream_not_bytesio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``DocumentConverter.convert()`` 에 ``DocumentStream`` 이 들어가는지 검증.

    실제 OCR 모델 다운로드/실행 회피 — convert 를 monkeypatch 로 캡쳐만.
    """
    captured: dict[str, object] = {}

    from docling import document_converter as dc

    def _fake_init(self: object, *args: object, **kwargs: object) -> None:
        # __init__ 부수효과만 차단 (실제 docling DocumentConverter 는 모델 로드 시도).
        return None

    def _fake_convert(self: object, source: object) -> object:
        captured["source"] = source

        class _Doc:
            @staticmethod
            def export_to_markdown() -> str:
                return "ok"

        class _Result:
            document = _Doc()

        return _Result()

    monkeypatch.setattr(dc.DocumentConverter, "__init__", _fake_init)
    monkeypatch.setattr(dc.DocumentConverter, "convert", _fake_convert)

    service = DoclingService()
    out = service._extract_sync(b"%PDF-1.4\nfake content", "kakaobank_01.jpg")

    assert out == "ok"

    # ── 회귀의 핵심: source 는 DocumentStream 이어야 한다 (BytesIO 그대로 X). ──
    from docling.datamodel.base_models import DocumentStream

    source = captured["source"]
    assert isinstance(source, DocumentStream), (
        f"convert() 에 BytesIO 가 전달되면 docling Pydantic 이 거부 — "
        f"DocumentStream 으로 래핑 필수. 실제 type={type(source).__name__}"
    )
    # name 은 호출자가 준 filename — docling 이 InputFormat 추론에 사용.
    assert source.name == "kakaobank_01.jpg"
