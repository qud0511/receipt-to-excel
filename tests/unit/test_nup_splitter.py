"""Phase 4 (보완) — N-up splitter generic utility.

ADR-005 §"split_by_marker 인터페이스" 검증. 카드사 무관한 단일-컬럼 텍스트 splitter.
"""

from __future__ import annotations

import pytest
from app.services.parsers.base import ProviderNotDetectedError
from app.services.parsers.preprocessor.nup_splitter import split_by_marker

_WOORI_MARKER = "국내전용카드"


def _build_woori_text(n_transactions: int, *, with_page_headers: int = 1) -> str:
    """단일-컬럼 우리카드 텍스트 simulator.

    실 자료 layout 을 line-by-line 으로 재현. 페이지 발행 timestamp 는 선두에 1 회 (옵션).
    """
    lines: list[str] = []
    for _ in range(with_page_headers):
        lines.append("2026.05.04 16:55:07")
    for i in range(n_transactions):
        lines.extend(
            [
                _WOORI_MARKER,
                "9500-****-****-8751",
                f"2026/04/0{i + 1}09:00:00",
                "일시불",
                "10,000원",
                "0원",
                "909원",
                "0원",
                f"1234567{i}",
                f"가맹점{i}",
                "서울특별시강남구테헤란로 123",
                "123456789",
                "000-00-00000",
                "0212345678",
            ]
        )
    return "\n".join(lines)


# ── 1) 단일 페이지 4 거래 분할 ───────────────────────────────────────────────
def test_splits_woori_4_transactions_single_page() -> None:
    text = _build_woori_text(4, with_page_headers=1)
    blocks = split_by_marker(text, _WOORI_MARKER)
    assert len(blocks) == 4
    for b in blocks:
        # 블록 안에 마커는 포함되지 않는다 (마커 이후 line 들만).
        assert _WOORI_MARKER not in b
        # 각 블록은 비어있지 않다.
        assert b.strip() != ""


# ── 2) 2 페이지 5 거래 분할 (페이지 헤더 2 개 — 페이지마다) ───────────────
def test_splits_woori_5_transactions_across_2_pages() -> None:
    # 페이지 헤더 2 개 (페이지 발행 timestamp) 가 모두 skip 돼야 정확히 5 블록.
    text = _build_woori_text(5, with_page_headers=2)
    blocks = split_by_marker(text, _WOORI_MARKER)
    assert len(blocks) == 5


# ── 3) 단일 거래 PDF 도 일관 분할 (길이 1 list) ──────────────────────────
def test_single_transaction_returns_list_of_one() -> None:
    text = _build_woori_text(1)
    blocks = split_by_marker(text, _WOORI_MARKER)
    assert len(blocks) == 1


# ── 4) 빈 텍스트 → ProviderNotDetectedError ───────────────────────────────
def test_empty_text_raises_provider_not_detected_error() -> None:
    with pytest.raises(ProviderNotDetectedError):
        split_by_marker("", _WOORI_MARKER)
    with pytest.raises(ProviderNotDetectedError):
        split_by_marker("    \n\n   ", _WOORI_MARKER)


# ── 5) 마커 미발견 → ProviderNotDetectedError ────────────────────────────
def test_marker_absent_raises_provider_not_detected_error() -> None:
    text = "2026.05.04 16:55:07\n그저 흔한 영수증 본문\n다른 카드사 내용\n"
    with pytest.raises(ProviderNotDetectedError):
        split_by_marker(text, _WOORI_MARKER)


# ── 6) 페이지 발행 timestamp 단독 line 은 마커보다 우선 skip ─────────────
def test_skips_page_header_timestamp_lines() -> None:
    # 발행 timestamp 가 블록 내부에 새지 않아야 한다.
    text = (
        "2026.05.04 16:55:07\n"
        f"{_WOORI_MARKER}\n"
        "first-tx-line-1\n"
        "first-tx-line-2\n"
        "2026.05.04 16:57:52\n"  # 페이지 2 헤더
        f"{_WOORI_MARKER}\n"
        "second-tx-line-1\n"
    )
    blocks = split_by_marker(text, _WOORI_MARKER)
    assert len(blocks) == 2
    # 페이지 헤더 timestamp 가 블록 내용에 새지 않는다.
    assert "16:55:07" not in blocks[0]
    assert "16:57:52" not in blocks[1]


# ── 7) 마커가 다른 토큰과 같은 line 에 있을 때 (예: 2 col N-up "마커 마커") ──
def test_treats_repeated_marker_on_same_line_as_block_start() -> None:
    # "국내전용카드 국내전용카드" 처럼 마커가 line 에 1 회 이상 — 블록 시작으로 인정.
    # (column 분할은 caller 책임이며, splitter 는 토큰 수와 무관하게 1 블록 시작으로 처리.)
    text = (
        f"{_WOORI_MARKER} {_WOORI_MARKER}\n"
        "value-a value-b\n"
        f"{_WOORI_MARKER} {_WOORI_MARKER}\n"
        "value-c value-d\n"
    )
    blocks = split_by_marker(text, _WOORI_MARKER)
    # 마커 line 2 회 → 블록 2 개.
    assert len(blocks) == 2
