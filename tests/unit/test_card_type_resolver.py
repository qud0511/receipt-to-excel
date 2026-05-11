"""Phase 4.7 — CardTypeResolver 3-tier deterministic 5 케이스."""

from __future__ import annotations

from datetime import date
from typing import Literal

import pytest
from app.domain.parsed_transaction import ParsedTransaction
from app.services.resolvers.card_type import is_generation_ready, resolve_card_type

CardType = Literal["법인", "개인"]


def _tx(masked: str | None) -> ParsedTransaction:
    return ParsedTransaction(
        가맹점명="x",
        거래일=date(2026, 1, 1),
        금액=1,
        카드사="shinhan",
        카드번호_마스킹=masked,
        parser_used="rule_based",
        field_confidence={},
    )


class _MockLookup:
    """card_meta_lookup Protocol 호환 — 호출 횟수 추적."""

    def __init__(self, returns: CardType | None) -> None:
        self._returns = returns
        self.call_count = 0

    async def __call__(self, user_id: int, masked: str) -> CardType | None:
        self.call_count += 1
        return self._returns


# ── 1) Priority 1 — batch_card_type 이 모든 row override ─────────────────────
async def test_priority_1_batch_selection_overrides_all() -> None:
    lookup = _MockLookup(returns="법인")  # card_meta 는 법인 반환할 것
    tx = _tx("1234-****-****-9999")

    result = await resolve_card_type(tx, user_id=1, batch_card_type="개인", card_meta_lookup=lookup)
    assert result == "개인"
    assert lookup.call_count == 0  # batch 가 우선이라 lookup 호출 안 됨.


# ── 2) Priority 2 — card_meta canonical match ─────────────────────────────────
async def test_priority_2_card_meta_lookup_canonical_match() -> None:
    lookup = _MockLookup(returns="법인")
    tx = _tx("1234-****-****-9999")

    result = await resolve_card_type(tx, user_id=1, batch_card_type=None, card_meta_lookup=lookup)
    assert result == "법인"
    assert lookup.call_count == 1


# ── 3) Priority 2 — AD-2 silent fail 방어 (canonical 미준수) ─────────────────
async def test_priority_2_silent_fail_on_format_mismatch() -> None:
    # 파서가 카드번호를 못 잡은 케이스 (도메인 차원에서 canonical 강제).
    lookup = _MockLookup(returns="법인")  # 호출되면 안 됨
    tx = _tx(None)

    result = await resolve_card_type(tx, user_id=1, batch_card_type=None, card_meta_lookup=lookup)
    # silent fail — None 반환, lookup 호출 0회.
    assert result is None
    assert lookup.call_count == 0


# ── 4) Priority 3 — unresolved → None (UI prompt) ────────────────────────────
async def test_priority_3_unresolved_returns_none_for_ui_prompt() -> None:
    lookup = _MockLookup(returns=None)  # card_meta 에 등록 안 됨
    tx = _tx("9999-****-****-1111")

    result = await resolve_card_type(tx, user_id=1, batch_card_type=None, card_meta_lookup=lookup)
    assert result is None


# ── 5) generation gate — 1건이라도 unresolved 면 차단 ─────────────────────────
def test_generation_blocked_when_any_row_unresolved() -> None:
    with_unresolved = ["법인", "개인", None, "법인"]
    assert is_generation_ready(with_unresolved) is False

    all_resolved = ["법인", "개인", "법인"]
    assert is_generation_ready(all_resolved) is True

    empty: list[CardType | None] = []
    # 빈 list — 차단 대상 없음 = ready.
    assert is_generation_ready(empty) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
