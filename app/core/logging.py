"""구조화 로깅 — structlog JSON + correlation_id + PII 마스킹.

CLAUDE.md §"관측성": 모든 응답에 X-Correlation-Id, 모든 로그 라인에 correlation_id.
CLAUDE.md §"보안": 카드번호 마지막 4자리만, 한국어 파일명은 session_id+idx.
"""

from __future__ import annotations

import logging
import re
import sys
import uuid
from collections.abc import Awaitable, Callable
from typing import TextIO

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from structlog.types import EventDict, WrappedLogger

CORRELATION_ID_HEADER = "X-Correlation-Id"

# 카드번호 — 4-4-4-4 형식. 가운데 8자리만 마스킹해 추적성 + 회계 매칭 보조 (마지막 4 자리).
_CARD_PATTERN = re.compile(r"\b(\d{4})-?\d{4}-?\d{4}-?(\d{4})\b")

# 한글 음절 범위 — `가` U+AC00 ~ `힣` U+D7A3.
_HANGUL_RE = re.compile(r"[가-힣]")


def mask_card_number(text: str) -> str:
    """카드번호 (1234-5678-9012-3456 류) 가운데 8자리를 ****-**** 로 치환."""
    return _CARD_PATTERN.sub(r"\1-****-****-\2", text)


def _pii_filter(
    _logger: WrappedLogger,
    _method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """structlog processor — 카드번호 + 한국어 파일명 마스킹."""

    # 한국어 파일명: filename + session_id + idx 가 함께 있을 때만 마스킹.
    # 이렇게 좁힌 이유 — session/idx 없으면 마스킹 키를 만들 수 없고,
    # 로그가 끊긴 영수증을 사후 추적할 단일 키가 필요하기 때문.
    filename = event_dict.get("filename")
    session_id = event_dict.get("session_id")
    idx = event_dict.get("idx")
    if (
        isinstance(filename, str)
        and _HANGUL_RE.search(filename)
        and session_id is not None
        and idx is not None
    ):
        event_dict["filename"] = f"session_{session_id}_idx_{idx}"

    # 카드번호: 모든 문자열 값을 일괄 스캔.
    for k, v in list(event_dict.items()):
        if isinstance(v, str):
            event_dict[k] = mask_card_number(v)

    return event_dict


def configure_logging(
    *,
    stream: TextIO | None = None,
    log_level: str = "INFO",
) -> None:
    """structlog 글로벌 설정 — JSON 출력 + correlation_id + PII 마스킹."""
    out = stream or sys.stdout
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }
    level = level_map.get(log_level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _pii_filter,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.WriteLoggerFactory(file=out),
        cache_logger_on_first_use=False,
    )


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """모든 요청에 correlation_id 를 부여하고 응답 헤더로 반환.

    클라이언트가 ``X-Correlation-Id`` 헤더를 보내면 그 값을 그대로 사용 (트레이싱 연동).
    없으면 uuid4 생성. uuid7 도입은 후속 ADR.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        cid = request.headers.get(CORRELATION_ID_HEADER) or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=cid)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers[CORRELATION_ID_HEADER] = cid
        return response
