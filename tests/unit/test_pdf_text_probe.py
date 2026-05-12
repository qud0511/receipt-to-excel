"""Phase 4 종료 — `is_text_embedded` 다중 토큰 휴리스틱 회귀 테스트.

배경: 직전 smoke gate 에서 우리카드 N-up case 2 (`woori_nup_02.pdf`) 가
text-aware router 로도 감지 실패. 원인은 압축 content stream 으로 ``BT`` 토큰이
raw bytes 에 부재 — 단일 토큰 휴리스틱의 한계.

ADR (phase-4-done.md §결함 1 후속): ``BT`` OR ``/Font`` OR ``/ToUnicode`` OR.
- ``BT``: 비압축 content stream 의 begin-text.
- ``/Font``: 폰트 리소스 참조 — 압축 stream 의 텍스트 PDF 도 보유.
- ``/ToUnicode``: CID 폰트의 Unicode mapping — 한글/CJK 텍스트 PDF 의 강한 시그니처.

False positive 비용: 잘못 True → router 가 extract_pdf_text() 시도 → 텍스트 부재면 ""
반환 → provider 미감지 → OCR 폴백 (현재 경로 유지). 비용은 pdfplumber open 1회.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.services.parsers.pdf_text_probe import is_text_embedded

from tests.fixtures.synthetic_pdfs import make_shinhan_receipt

_REAL_PDFS = Path(__file__).resolve().parents[1] / "smoke" / "real_pdfs"
_WOORI_NUP_02 = _REAL_PDFS / "woori_nup_02.pdf"


# ── 1) 비압축 BT 토큰 — 기존 동작 보존 ─────────────────────────────────────
def test_uncompressed_bt_token_detected() -> None:
    pdf = b"%PDF-1.4\nBT\nshinhancard.com\nET\n%%EOF"
    assert is_text_embedded(pdf) is True


# ── 2) 압축 content stream + /Font ref — 신규 검출 경로 ───────────────────
def test_compressed_stream_with_font_ref_detected() -> None:
    pdf = b"%PDF-1.4\n<< /Type /Page /Resources << /Font << /F1 5 0 R >> >> >>\n%%EOF"
    assert is_text_embedded(pdf) is True


# ── 3) /ToUnicode mapping — CID 한글 PDF 강한 시그니처 ────────────────────
def test_pdf_with_tounicode_detected() -> None:
    pdf = b"%PDF-1.4\n<< /CIDInit /ToUnicode CMap >>\n%%EOF"
    assert is_text_embedded(pdf) is True


# ── 4) 마커 없음 — 이미지 only PDF (스캔본) ────────────────────────────────
def test_image_only_pdf_without_text_markers_not_embedded() -> None:
    pdf = b"%PDF-1.4\n%scanned image only, no text layer\n<< /XObject 1 0 R >>\n%%EOF"
    assert is_text_embedded(pdf) is False


# ── 5) PDF 매직 부재 — JPG/PNG 등은 즉시 False ─────────────────────────────
def test_non_pdf_input_returns_false() -> None:
    jpg = b"\xff\xd8\xff\xe0JFIF\x00BT/Font/ToUnicode"  # 토큰 모두 들어있어도
    assert is_text_embedded(jpg) is False


# ── 6) 합성 reportlab CID 폰트 PDF — 회귀 보장 ─────────────────────────────
def test_synthetic_reportlab_cid_pdf_detected() -> None:
    pdf = make_shinhan_receipt()
    assert is_text_embedded(pdf) is True


# ── 7) 실 자료 woori_nup_02.pdf — 본 휴리스틱 보강의 직접 동기 ─────────────
@pytest.mark.real_pdf
@pytest.mark.skipif(not _WOORI_NUP_02.exists(), reason="woori_nup_02.pdf 미존재 (gitignore)")
def test_woori_nup_02_real_pdf_detected() -> None:
    """직전 smoke 에서 단일 BT 휴리스틱이 놓친 압축 stream PDF.

    텍스트 추출 가능 (직전 세션에서 page 0 = 546 chars, page 1 = 149 chars 검증) →
    is_text_embedded() 가 True 반환해야 router 가 text-aware detect_provider 진입.
    """
    assert is_text_embedded(_WOORI_NUP_02.read_bytes()) is True
