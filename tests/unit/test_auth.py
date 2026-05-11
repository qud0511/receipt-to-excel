"""Phase 1 인증 — Azure AD JWKS 검증 + stub mode + 1h TTL 캐시."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from app.core.auth import AzureADVerifier, InvalidTokenError
from app.core.config import Settings
from httpx import ASGITransport, MockTransport

_JWKS_PAYLOAD = {"keys": [{"kid": "k1", "kty": "RSA", "n": "x", "e": "AQAB"}]}


@asynccontextmanager
async def make_client() -> AsyncIterator[httpx.AsyncClient]:
    """create_app() 으로 만든 FastAPI 앱 + httpx AsyncClient 컨텍스트."""
    from app.main import create_app

    app = create_app()
    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            yield c
    finally:
        await app.state.verifier.aclose()


def _counting_mock_transport(payload: dict[str, object]) -> tuple[MockTransport, list[int]]:
    """JWKS 호출 횟수를 카운트하는 MockTransport. (transport, [counter])."""
    counter = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        counter[0] += 1
        # CLAUDE.md §"보안": Ollama+JWKS 고정 URL 만 허용 — 호스트 화이트리스트 검증.
        assert request.url.host == "login.microsoftonline.com"
        return httpx.Response(200, json=payload)

    return MockTransport(handler), counter


# ── 1) stub mode ─────────────────────────────────────────────────────────────
async def test_verify_token_returns_stub_when_auth_disabled() -> None:
    # CLAUDE.md §"보안": REQUIRE_AUTH=false → 익명 default 사용자.
    settings = Settings()
    verifier = AzureADVerifier(settings)
    try:
        user = await verifier.verify("any-garbage-token")
        assert user.oid == "default"
    finally:
        await verifier.aclose()


# ── 2) garbage token → InvalidTokenError ─────────────────────────────────────
async def test_verify_token_raises_401_on_garbage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client")
    settings = Settings()
    verifier = AzureADVerifier(settings)
    try:
        with pytest.raises(InvalidTokenError):
            await verifier.verify("not.a.jwt")
    finally:
        await verifier.aclose()


# ── 3) JWKS cache within TTL ─────────────────────────────────────────────────
async def test_jwks_cache_reuses_within_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client")
    settings = Settings()

    transport, counter = _counting_mock_transport(_JWKS_PAYLOAD)
    http = httpx.AsyncClient(transport=transport)
    clock = [1000.0]
    verifier = AzureADVerifier(settings, http_client=http, now=lambda: clock[0])
    try:
        await verifier.get_jwks()
        assert counter[0] == 1

        # CLAUDE.md §"성능": JWKS 1h TTL — 직전에는 캐시 hit.
        clock[0] = 1000.0 + 3599.0
        await verifier.get_jwks()
        assert counter[0] == 1
    finally:
        await verifier.aclose()
        await http.aclose()


# ── 4) JWKS refresh after TTL ────────────────────────────────────────────────
async def test_jwks_cache_refreshes_after_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client")
    settings = Settings()

    transport, counter = _counting_mock_transport(_JWKS_PAYLOAD)
    http = httpx.AsyncClient(transport=transport)
    clock = [1000.0]
    verifier = AzureADVerifier(settings, http_client=http, now=lambda: clock[0])
    try:
        await verifier.get_jwks()
        assert counter[0] == 1

        # TTL 경과 → 재요청
        clock[0] = 1000.0 + 3601.0
        await verifier.get_jwks()
        assert counter[0] == 2
    finally:
        await verifier.aclose()
        await http.aclose()


# ── 5) /auth/config returns require_auth flag ────────────────────────────────
async def test_auth_config_returns_require_auth_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REQUIRE_AUTH", "false")
    async with make_client() as c:
        r = await c.get("/auth/config")
        assert r.status_code == 200
        body = r.json()
        assert body["require_auth"] is False


# ── 6) /auth/me stub when auth disabled ──────────────────────────────────────
async def test_auth_me_returns_stub_when_auth_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REQUIRE_AUTH", "false")
    async with make_client() as c:
        r = await c.get("/auth/me")
        assert r.status_code == 200
        assert r.json()["oid"] == "default"


# ── 7) /auth/me rejects missing Bearer when auth required ────────────────────
async def test_auth_me_rejects_missing_bearer_when_auth_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client")
    async with make_client() as c:
        r = await c.get("/auth/me")  # no Authorization header
        assert r.status_code == 401
