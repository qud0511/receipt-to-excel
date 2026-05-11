"""인증 응답 스키마 — UserInfo, AuthConfigResponse."""

from __future__ import annotations

from pydantic import BaseModel, Field


class UserInfo(BaseModel):
    """현재 사용자. CLAUDE.md §"보안": 서버가 토큰에서 결정 (oid/email/name)."""

    oid: str = Field(..., description="Azure object id 또는 stub 모드 시 'default'.")
    name: str = ""
    email: str = ""


class AuthConfigResponse(BaseModel):
    """프론트엔드가 로그인 UI 분기에 사용. tenant/client_id 는 공개해도 무방."""

    require_auth: bool
    tenant_id: str = ""
    client_id: str = ""
