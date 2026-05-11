"""Card — 도메인 카드 정보 (한글 필드)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

_CARD_MASKED_PATTERN = r"^\d{4}-\*{4}-\*{4}-\d{4}$"


class Card(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    user_id: int
    카드번호_마스킹: str = Field(pattern=_CARD_MASKED_PATTERN)
    카드구분: Literal["법인", "개인"]
    카드사: str
    별칭: str | None = None
