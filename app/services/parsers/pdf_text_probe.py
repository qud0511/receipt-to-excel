"""PDF 텍스트 임베디드 여부 검사 — 스캔본 vs 텍스트 PDF 분기.

Phase 3: 외부 IO/패키지 없는 byte-level heuristic.
- 텍스트 PDF: ``BT...ET`` (Begin/End Text) 블록을 포함.
- 스캔 PDF: 이미지 XObject 만, BT 토큰 부재.

후속 phase 에서 ``pdfplumber`` 등으로 정확도를 올리는 차원의 교체 가능
— 본 모듈의 시그니처는 유지.
"""

from __future__ import annotations


def is_text_embedded(content: bytes) -> bool:
    """PDF 가 텍스트 레이어를 가졌는지 — BT 토큰 기반 빠른 검사."""
    if not content.startswith(b"%PDF"):
        # PDF 가 아닌 입력 (JPG 등) — 텍스트 임베디드 아님으로 간주.
        return False
    return b"BT" in content
