"""CardTypeResolver — 3-tier deterministic 카드구분 결정.

CLAUDE.md §"특이사항: AD-2 silent bug 방어":
canonical 미준수 카드번호는 매치 실패 → silent fail (None) → UI 가 사용자에게 prompt.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Literal, Protocol

from app.domain.parsed_transaction import ParsedTransaction

CardType = Literal["법인", "개인"]

# AD-2 canonical 형식만 허용 — pydantic 도메인 검증과 중복이지만 방어 다층 차원에서 재확인.
_CANONICAL_PATTERN = re.compile(r"^\d{4}-\*{4}-\*{4}-\d{4}$")


class _CardMetaLookup(Protocol):
    async def __call__(self, user_id: int, masked: str) -> CardType | None: ...


async def resolve_card_type(
    parsed: ParsedTransaction,
    *,
    user_id: int,
    batch_card_type: CardType | None,
    card_meta_lookup: _CardMetaLookup,
) -> CardType | None:
    """3-tier 우선순위:

    1) ``batch_card_type`` (배치 업로드 시 사용자가 명시한 시트) → 모든 row override.
    2) ``card_meta`` lookup — ``카드번호_마스킹`` 의 canonical 매치 시 카드구분 반환.
    3) None — UI 가 사용자에게 prompt (generation 차단).
    """
    if batch_card_type is not None:
        return batch_card_type

    masked = parsed.카드번호_마스킹
    if masked is None or not _CANONICAL_PATTERN.match(masked):
        # AD-2: canonical 미준수 = silent fail. lookup 호출도 하지 않음.
        return None

    return await card_meta_lookup(user_id, masked)


def is_generation_ready(card_types: Sequence[CardType | None]) -> bool:
    """모든 row 의 card_type 이 resolved 일 때만 generation 가능.

    빈 list (검증 대상 없음) 는 ready 로 처리 — 호출자가 row 개수 별도 검증.
    """
    return all(ct is not None for ct in card_types)
