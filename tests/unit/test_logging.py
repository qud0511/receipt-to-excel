"""Phase 1 로깅 — structlog JSON + correlation_id + PII 마스킹."""

from __future__ import annotations

import io
import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import structlog
from app.core.logging import (
    CORRELATION_ID_HEADER,
    configure_logging,
    mask_card_number,
)
from httpx import ASGITransport


@asynccontextmanager
async def make_client() -> AsyncIterator[httpx.AsyncClient]:
    from app.main import create_app

    app = create_app()
    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            yield c
    finally:
        await app.state.verifier.aclose()


# ── 1) X-Correlation-Id 응답 헤더 존재 + UUID 형식 ─────────────────────────────
async def test_correlation_id_added_to_response_header() -> None:
    async with make_client() as c:
        r = await c.get("/healthz")
        cid = r.headers.get(CORRELATION_ID_HEADER)
        assert cid is not None
        # UUID4 형식 — 8-4-4-4-12 hex
        assert re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", cid), cid


# ── 2) 로그 라인에 correlation_id 키 자동 주입 ─────────────────────────────────
def test_log_line_includes_correlation_id() -> None:
    buf = io.StringIO()
    configure_logging(stream=buf)

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(correlation_id="test-cid-1234")
    try:
        logger = structlog.get_logger("test")
        logger.info("hello")
    finally:
        structlog.contextvars.clear_contextvars()

    line = buf.getvalue().strip().splitlines()[-1]
    data = json.loads(line)
    assert data["correlation_id"] == "test-cid-1234"
    assert data["event"] == "hello"


# ── 3) PII — 카드번호 가운데 8자리 마스킹 (마지막 4자리 보존) ──────────────────
def test_pii_filter_masks_card_number_last_4() -> None:
    src = "거래 카드번호 1234-5678-9012-3456 승인됨"
    masked = mask_card_number(src)
    assert "1234-****-****-3456" in masked
    assert "5678" not in masked
    assert "9012" not in masked


# ── 4) PII — 한국어 파일명을 session_id+idx 형식으로 마스킹 ────────────────────
def test_pii_filter_masks_korean_filename_in_log() -> None:
    buf = io.StringIO()
    configure_logging(stream=buf)

    logger = structlog.get_logger("test")
    logger.info(
        "file uploaded",
        filename="거래내역서_5월.pdf",
        session_id="abc123",
        idx=0,
    )

    line = buf.getvalue().strip().splitlines()[-1]
    data = json.loads(line)
    # 한글 원본은 로그 어느 위치에도 등장하면 안 됨
    assert "거래내역서" not in line
    assert data["filename"] == "session_abc123_idx_0"
