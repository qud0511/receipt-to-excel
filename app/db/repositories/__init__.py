"""Repository 패키지 — 모든 메서드 시그니처에 ``*, user_id: int`` 키워드 전용.

CLAUDE.md §"보안": 모든 변경 쿼리에 ``WHERE user_id = :current``.
IDOR 차단은 본 패키지 단일 책임 — 라우터·도메인 코드가 우회 못 하도록 keyword-only.
"""

from app.db.repositories import (
    card_meta_repo,
    expense_record_repo,
    merchant_repo,
    project_repo,
    session_repo,
    team_group_repo,
    template_repo,
    transaction_repo,
    vendor_repo,
)

__all__ = [
    "card_meta_repo",
    "expense_record_repo",
    "merchant_repo",
    "project_repo",
    "session_repo",
    "team_group_repo",
    "template_repo",
    "transaction_repo",
    "vendor_repo",
]
