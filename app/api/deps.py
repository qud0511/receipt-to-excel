"""FastAPI 공통 의존성 — 모든 변경 라우터의 단일 인증 진입점."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException, Request, status

from app.core.auth import AzureADVerifier, InvalidTokenError
from app.schemas.auth import UserInfo


async def get_current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> UserInfo:
    """모든 변경 라우터에 ``Depends(get_current_user)`` 필수 (CLAUDE.md §"보안")."""
    verifier: AzureADVerifier = request.app.state.verifier
    settings = verifier._settings

    if not settings.require_auth:
        return UserInfo(oid="default")

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ", 1)[1].strip()
    try:
        return await verifier.verify(token)
    except InvalidTokenError as e:
        # 401 응답 본문에 스택트레이스 / 내부 사유 노출 금지 (CLAUDE.md §"에러 응답").
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
