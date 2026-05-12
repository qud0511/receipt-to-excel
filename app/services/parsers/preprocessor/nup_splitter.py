"""N-up 매출전표 블록 splitter — 단일-컬럼 텍스트를 마커 기준으로 분할.

ADR-005 §"split_by_marker 인터페이스" 참조. 카드사 무관 generic utility.

호출 책임:
- 다중-컬럼 N-up PDF 인 경우 caller 가 먼저 pdfplumber crop 등으로 컬럼별 텍스트 추출.
- 본 splitter 는 단일-컬럼 텍스트만 처리. 마커가 같은 line 에 N 회 반복돼도 1 블록 시작.

반환:
- ``list[str]`` — 각 원소는 마커 이후 line 들을 ``\n`` join 한 블록 텍스트.
- 빈 입력 또는 마커 미발견 → ``ProviderNotDetectedError``.
"""

from __future__ import annotations

import re

from app.services.parsers.base import ProviderNotDetectedError

# 발행 timestamp (yyyy.mm.dd hh:mm:ss 공백 옵션) — 거래일과 분리, splitter 단계에서 skip.
_PAGE_HEADER_TIMESTAMP = re.compile(r"^\d{4}\.\d{2}\.\d{2}\s*\d{2}:\d{2}:\d{2}$")


def split_by_marker(text: str, marker: str) -> list[str]:
    """``marker`` line 단위로 ``text`` 를 블록으로 분할.

    - line 이 marker 만 포함 (또는 marker 가 같은 line 에 N 회 반복) → 블록 시작
    - 페이지 발행 timestamp (yyyy.mm.dd hh:mm:ss) line 은 skip
    - 빈 line 은 skip
    - 단일 블록도 길이 1 list 반환 (일관성)

    Raises:
        ProviderNotDetectedError: 빈 입력 또는 마커 미발견 시.
    """
    if not text.strip():
        raise ProviderNotDetectedError(
            "split_by_marker: empty text",
            reason="text contains no non-whitespace content",
            tier_attempted="rule_based",
        )

    blocks: list[list[str]] = []
    current: list[str] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if _PAGE_HEADER_TIMESTAMP.match(line):
            continue
        # 마커 — 단독 또는 같은 line 에 N 회 반복 (N-up 잔재).
        if _is_marker_line(line, marker):
            if current is not None:
                blocks.append(current)
            current = []
            continue
        if current is not None:
            current.append(line)
    if current is not None:
        blocks.append(current)

    if not blocks:
        raise ProviderNotDetectedError(
            f"split_by_marker: marker {marker!r} not found in text",
            reason="no block marker line detected",
            tier_attempted="rule_based",
        )

    return ["\n".join(b) for b in blocks]


def _is_marker_line(line: str, marker: str) -> bool:
    """``line`` 이 marker 만으로 구성되었는지 (공백/반복 허용)."""
    remainder = line.replace(marker, "").strip()
    return marker in line and remainder == ""
