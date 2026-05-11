"""Phase 1 에러 — AppError 매핑 + 비공개 500 응답."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from app.core.errors import ConflictError
from fastapi import FastAPI
from httpx import ASGITransport


@asynccontextmanager
async def make_client_with(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        yield c
    await app.state.verifier.aclose()


# ── 1) AppError → JSON {code, message} + 적절한 status ────────────────────────
async def test_app_error_maps_to_http_with_code() -> None:
    from app.main import create_app

    app = create_app()

    async def _raise() -> None:
        raise ConflictError("collision detected")

    app.add_api_route("/__test_app_error", _raise, methods=["GET"])

    async with make_client_with(app) as c:
        r = await c.get("/__test_app_error")
        assert r.status_code == 409
        body = r.json()
        assert body["code"] == "CONFLICT"
        assert body["message"] == "collision detected"


# ── 2) Unhandled Exception → 500 + 스택트레이스 비노출 ─────────────────────────
async def test_unhandled_exception_returns_500_no_stack_trace_in_body() -> None:
    from app.main import create_app

    app = create_app()

    async def _boom() -> None:
        raise RuntimeError("super secret internal state leak")

    app.add_api_route("/__test_unhandled", _boom, methods=["GET"])

    async with make_client_with(app) as c:
        r = await c.get("/__test_unhandled")

    assert r.status_code == 500
    body_text = r.text
    # CLAUDE.md §"에러 응답": 스택트레이스 절대 노출 금지.
    assert "super secret" not in body_text
    assert "RuntimeError" not in body_text
    assert "Traceback" not in body_text
    body = r.json()
    assert body["code"] == "INTERNAL"
