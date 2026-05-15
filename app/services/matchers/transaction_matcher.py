"""Phase 6.4 — Transaction Matcher: 영수증 ↔ 카드 사용내역 매칭.

ADR-010 자료 검증 C-1 후속: UI Upload 가 영수증 사진 + 카드 사용내역 동시 업로드 →
잡 파싱 후 거래 시각 + 금액으로 두 source 의 동일 거래 link.

매칭 기준 (사용자 동의 추천 2):
- 거래일 정확 동일
- 거래시각 ±5분 (한국 카드사 결제 승인 시각 vs 영수증 출력 시각 일반 시차)
- 금액 정확 동일 (원 단위, AD-4 강제)

매칭 결과는 ``TransactionMatch`` — receipt 단독 / card 단독 / 양쪽 매칭 모두 표현.
caller (JobRunner) 가 영수증의 source_file_path 를 카드 transaction 의
receipt_file_path 로 link 하는 후처리 수행.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time, timedelta

from app.domain.parsed_transaction import ParsedTransaction

# 사용자 동의 추천 2: ±5분 허용.
_TIME_TOLERANCE = timedelta(minutes=5)


@dataclass(frozen=True)
class TransactionMatch:
    """매칭 결과 1건.

    - receipt + card_transaction 양쪽 모두 not None: 매칭 성공
    - receipt only: 영수증만, 카드 내역 부재
    - card_transaction only: 카드 내역만, 영수증 사진 부재
    """

    receipt: ParsedTransaction | None
    card_transaction: ParsedTransaction | None


def match_receipts_with_card_transactions(
    *,
    receipts: list[ParsedTransaction],
    card_transactions: list[ParsedTransaction],
) -> list[TransactionMatch]:
    """그리디 매칭 — 영수증 한 건마다 가장 가까운 카드 내역 1건 찾음.

    동일 카드 내역이 두 영수증과 매칭될 수 없음 (1:1 link). 매칭 우선순위:
    1. 거래일 동일
    2. 시각 차이 최소 (±5분 이내)
    3. 금액 정확 동일

    반환 list 순서: 매칭 성공 → receipt 단독 → card 단독.
    """
    consumed_card_indices: set[int] = set()
    matched: list[TransactionMatch] = []
    receipt_alone: list[TransactionMatch] = []

    for receipt in receipts:
        best_idx = _find_best_card_match(receipt, card_transactions, consumed=consumed_card_indices)
        if best_idx is None:
            receipt_alone.append(TransactionMatch(receipt=receipt, card_transaction=None))
        else:
            consumed_card_indices.add(best_idx)
            matched.append(
                TransactionMatch(receipt=receipt, card_transaction=card_transactions[best_idx])
            )

    card_alone = [
        TransactionMatch(receipt=None, card_transaction=card_tx)
        for idx, card_tx in enumerate(card_transactions)
        if idx not in consumed_card_indices
    ]

    return matched + receipt_alone + card_alone


def _find_best_card_match(
    receipt: ParsedTransaction,
    card_transactions: list[ParsedTransaction],
    *,
    consumed: set[int],
) -> int | None:
    """매칭 가능 카드 내역 중 시각 차이 최소 index. 없으면 None."""
    best_idx: int | None = None
    best_diff: timedelta | None = None
    for idx, card_tx in enumerate(card_transactions):
        if idx in consumed:
            continue
        if not _is_compatible(receipt, card_tx):
            continue
        diff = _time_diff(receipt.거래시각, card_tx.거래시각)
        if diff > _TIME_TOLERANCE:
            continue
        if best_diff is None or diff < best_diff:
            best_idx = idx
            best_diff = diff
    return best_idx


def _is_compatible(a: ParsedTransaction, b: ParsedTransaction) -> bool:
    """거래일 + 금액 일치 — 시각 검사 전 1차 필터."""
    return a.거래일 == b.거래일 and a.금액 == b.금액


def _time_diff(a: time | None, b: time | None) -> timedelta:
    """시각 차이 (절대값). 둘 중 하나라도 None 이면 큰 값 반환 (매칭 불가)."""
    if a is None or b is None:
        return _TIME_TOLERANCE + timedelta(seconds=1)
    a_sec = a.hour * 3600 + a.minute * 60 + a.second
    b_sec = b.hour * 3600 + b.minute * 60 + b.second
    return timedelta(seconds=abs(a_sec - b_sec))
