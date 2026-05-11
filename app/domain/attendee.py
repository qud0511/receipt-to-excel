"""Attendee — 도메인 참석자 (단순 value object)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Attendee(BaseModel):
    model_config = ConfigDict(extra="forbid")

    이름: str
    팀그룹: str | None = None
