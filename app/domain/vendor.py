"""Vendor — 도메인 거래처."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Vendor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    user_id: int
    이름: str
    사용횟수: int = Field(default=0, ge=0)
    최근사용: datetime | None = None
