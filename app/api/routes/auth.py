"""인증 라우터 — /auth/config (공개), /auth/me (인증 필요)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_current_user
from app.schemas.auth import AuthConfigResponse, UserInfo

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config", response_model=AuthConfigResponse)
async def auth_config(request: Request) -> AuthConfigResponse:
    """프론트엔드 로그인 UI 분기용 — REQUIRE_AUTH / tenant / client_id 노출."""
    settings = request.app.state.settings
    return AuthConfigResponse(
        require_auth=settings.require_auth,
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
    )


@router.get("/me", response_model=UserInfo)
async def auth_me(user: Annotated[UserInfo, Depends(get_current_user)]) -> UserInfo:
    return user
