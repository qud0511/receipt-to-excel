"""Phase 6.4 — Transaction Matcher 5 케이스.

영수증 파서 (Phase 4) 결과와 카드 사용내역 파서 (Phase 6.3) 결과를 거래 시각 +
금액 기준으로 매칭. ADR-010 자료 검증 C-1 후속 (영수증 사진의 원본 파일 경로를
카드 transaction 의 receipt_file_path 로 link).

매칭 기준:
- 거래일 동일
- 거래시각 ±5분
- 금액 정확히 동일 (원 단위)
"""

from __future__ import annotations

from datetime import date, time

from app.domain.parsed_transaction import ParsedTransaction
from app.services.matchers.transaction_matcher import (
    match_receipts_with_card_transactions,
)


def _make_tx(
    *,
    merchant: str = "가짜식당",
    tx_date: date = date(2026, 5, 1),
    tx_time: time | None = time(12, 30, 0),
    amount: int = 10000,
) -> ParsedTransaction:
    return ParsedTransaction(
        가맹점명=merchant,
        거래일=tx_date,
        거래시각=tx_time,
        금액=amount,
        카드사="shinhan",
        parser_used="rule_based",
        field_confidence={"가맹점명": "high", "거래일": "high", "금액": "high"},
    )


def test_matches_receipt_to_card_transaction_by_time_and_amount() -> None:
    receipt = _make_tx(merchant="영수증가맹점", tx_time=time(12, 30, 0), amount=8900)
    card_tx = _make_tx(merchant="카드내역가맹점", tx_time=time(12, 32, 0), amount=8900)

    matches = match_receipts_with_card_transactions(
        receipts=[receipt],
        card_transactions=[card_tx],
    )

    assert len(matches) == 1
    assert matches[0].receipt is receipt
    assert matches[0].card_transaction is card_tx


def test_handles_no_matching_card_transaction_receipt_alone() -> None:
    """영수증만 있고 카드 내역 매칭 0 → receipt 단독 Match (card_transaction=None)."""
    receipt = _make_tx(amount=5000)
    matches = match_receipts_with_card_transactions(receipts=[receipt], card_transactions=[])

    assert len(matches) == 1
    assert matches[0].receipt is receipt
    assert matches[0].card_transaction is None


def test_handles_no_matching_receipt_card_alone() -> None:
    """카드 내역만 있고 영수증 없음 → card 단독 Match (receipt=None)."""
    card_tx = _make_tx(amount=5000)
    matches = match_receipts_with_card_transactions(receipts=[], card_transactions=[card_tx])

    assert len(matches) == 1
    assert matches[0].receipt is None
    assert matches[0].card_transaction is card_tx


def test_5_min_tolerance_window() -> None:
    """매칭 허용 시각 차이 ±5분. 6분 차이는 매칭 안 됨."""
    receipt = _make_tx(tx_time=time(12, 0, 0), amount=3000)
    # 4분 차이 — 매칭
    near = _make_tx(tx_time=time(12, 4, 0), amount=3000)
    # 6분 차이 — 매칭 안 됨
    far = _make_tx(tx_time=time(12, 6, 0), amount=3000)

    matches = match_receipts_with_card_transactions(
        receipts=[receipt],
        card_transactions=[near, far],
    )

    matched_pairs = [m for m in matches if m.receipt is not None and m.card_transaction is not None]
    assert len(matched_pairs) == 1
    assert matched_pairs[0].card_transaction is near

    # far 는 단독 Match.
    far_alone = [m for m in matches if m.card_transaction is far and m.receipt is None]
    assert len(far_alone) == 1


def test_different_amounts_no_match() -> None:
    """동일 시각이라도 금액 다르면 매칭 안 됨 — 각각 단독."""
    receipt = _make_tx(amount=10000)
    card_tx = _make_tx(amount=10500)  # 500 원 차이.

    matches = match_receipts_with_card_transactions(
        receipts=[receipt],
        card_transactions=[card_tx],
    )

    # 영수증 단독 + 카드 단독 = 2 매치.
    assert len(matches) == 2
    receipt_alone = [m for m in matches if m.receipt is receipt and m.card_transaction is None]
    card_alone = [m for m in matches if m.card_transaction is card_tx and m.receipt is None]
    assert len(receipt_alone) == 1
    assert len(card_alone) == 1
