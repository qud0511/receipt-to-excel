"""Project — 도메인 프로젝트 (vendor 종속)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    user_id: int
    vendor_id: int
    이름: str
    사용횟수: int = Field(default=0, ge=0)
    최근사용: datetime | None = None
