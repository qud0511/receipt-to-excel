"""헬스 체크 라우터 — /healthz (liveness), /readyz (readiness)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import Settings, get_settings

router = APIRouter(tags=["health"])


class _HealthOk(BaseModel):
    status: str


class _DbStatus(BaseModel):
    configured: bool


class _OllamaStatus(BaseModel):
    configured: bool
    model: str
    enabled: bool


class _StorageStatus(BaseModel):
    path: str


class _ReadyzResponse(BaseModel):
    db: _DbStatus
    ollama: _OllamaStatus
    storage: _StorageStatus


@router.get("/healthz", response_model=_HealthOk)
async def healthz() -> _HealthOk:
    return _HealthOk(status="ok")


@router.get("/readyz", response_model=_ReadyzResponse)
async def readyz(settings: Annotated[Settings, Depends(get_settings)]) -> _ReadyzResponse:
    # CLAUDE.md §"성능": DB·Ollama·storage 실시간 체크.
    # Phase 1 = 설정값 존재 여부만 보고. 실제 연결 검사는 Phase 2~3 에서 도입.
    return _ReadyzResponse(
        db=_DbStatus(configured=bool(settings.database_url)),
        ollama=_OllamaStatus(
            configured=bool(settings.ollama_base_url),
            model=settings.ollama_model,
            enabled=settings.llm_enabled,
        ),
        storage=_StorageStatus(path="storage/"),
    )
