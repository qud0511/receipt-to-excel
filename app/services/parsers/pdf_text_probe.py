"""PDF 텍스트 임베디드 여부 검사 + 추출 helper.

ADR-007 §"text-aware provider 감지": PDF 한글 텍스트는 font glyph encoding 으로 인해
raw bytes 매칭 불가. ``extract_pdf_text()`` 가 추출 텍스트를 반환해 router 의
한글 시그니처 매칭에 사용.
"""

from __future__ import annotations

import io


def is_text_embedded(content: bytes) -> bool:
    """PDF 가 텍스트 레이어를 가졌는지 — BT 토큰 기반 빠른 검사."""
    if not content.startswith(b"%PDF"):
        # PDF 가 아닌 입력 (JPG 등) — 텍스트 임베디드 아님으로 간주.
        return False
    return b"BT" in content


def extract_pdf_text(content: bytes) -> str | None:
    """텍스트 임베디드 PDF 의 추출 텍스트. 비-PDF/스캔본/추출 실패 → ``None``.

    ADR-007: detect_provider 의 한글 시그니처 매칭 + 우리카드 dual gate 에 사용.
    텍스트 추출 비용은 rule_based parser 가 어차피 동일 작업을 수행하므로 큰 부담 없음.

    pdfplumber import 는 함수 내부 — 본 모듈을 부담 없이 import 하는 경량 호출자
    (예: byte heuristic 만 필요한 경우) 를 위해.
    """
    if not is_text_embedded(content):
        return None
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:
        # 손상된 PDF/추출 라이브러리 예외 — provider 감지를 막지 않도록 None 반환.
        return None
