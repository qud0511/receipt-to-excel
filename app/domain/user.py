"""User — 도메인 사용자."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class User(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    oid: str  # Azure AD object id
    이름: str = ""
    이메일: str
    default_card_id: int | None = None
