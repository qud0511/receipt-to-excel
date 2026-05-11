"""Azure AD JWT 검증 — JWKS 1h TTL 캐시 + stub mode."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypedDict, cast

import httpx
from jose import JWTError, jwt

from app.core.config import Settings
from app.schemas.auth import UserInfo


class InvalidTokenError(Exception):
    """JWT 검증 실패. Task 1.5 의 AppError 계층에 흡수 예정."""


class _JWK(TypedDict, total=False):
    kty: str
    kid: str
    use: str
    alg: str
    n: str
    e: str


class _JWKSet(TypedDict):
    keys: list[_JWK]


class AzureADVerifier:
    """Azure AD 토큰 검증기.

    - stub mode: ``settings.require_auth == False`` 면 토큰 무시하고 default 사용자 반환.
    - real mode: JWKS 를 1h TTL 캐시 (CLAUDE.md §"성능") + jose 로 RS256 검증.
    - 시간 주입(``now`` 콜러블)으로 TDD 시 시계 mock 가능 (CLAUDE.md §"TDD 특이사항").
    """

    JWKS_TTL_SECONDS = 3600

    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.AsyncClient | None = None,
        now: Callable[[], float] | None = None,
    ) -> None:
        self._settings = settings
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=10.0)
        self._now: Callable[[], float] = now or time.monotonic
        self._jwks: _JWKSet | None = None
        self._jwks_fetched_at: float = 0.0

    async def verify(self, token: str) -> UserInfo:
        if not self._settings.require_auth:
            return UserInfo(oid="default")

        if not token:
            raise InvalidTokenError("Empty token")

        try:
            unverified_header = jwt.get_unverified_header(token)
        except JWTError as e:
            raise InvalidTokenError(f"Invalid token header: {e}") from e

        kid = unverified_header.get("kid")
        if not kid:
            raise InvalidTokenError("Token header missing 'kid'")

        jwks = await self.get_jwks()
        matching = next((k for k in jwks["keys"] if k.get("kid") == kid), None)
        if matching is None:
            raise InvalidTokenError(f"kid {kid!r} not found in JWKS")

        issuer = f"https://login.microsoftonline.com/{self._settings.azure_tenant_id}/v2.0"
        audience = self._settings.azure_client_id

        try:
            payload = jwt.decode(
                token,
                cast(dict[str, str], matching),
                algorithms=["RS256"],
                audience=audience,
                issuer=issuer,
                options={"require": ["exp", "iss", "aud"]},
            )
        except JWTError as e:
            raise InvalidTokenError(f"JWT verification failed: {e}") from e

        oid = payload.get("oid")
        if not isinstance(oid, str) or not oid:
            raise InvalidTokenError("Token payload missing 'oid' claim")

        return UserInfo(
            oid=oid,
            name=str(payload.get("name", "")),
            email=str(payload.get("preferred_username") or payload.get("email") or ""),
        )

    async def get_jwks(self) -> _JWKSet:
        """JWKS 조회 (캐시 hit 시 네트워크 호출 생략)."""
        if self._jwks is not None:
            age = self._now() - self._jwks_fetched_at
            if age < self.JWKS_TTL_SECONDS:
                return self._jwks

        url = (
            f"https://login.microsoftonline.com/"
            f"{self._settings.azure_tenant_id}/discovery/v2.0/keys"
        )
        r = await self._http.get(url)
        r.raise_for_status()
        body = r.json()
        keys_raw = body.get("keys", [])
        self._jwks = _JWKSet(keys=[cast(_JWK, k) for k in keys_raw])
        self._jwks_fetched_at = self._now()
        return self._jwks

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()
