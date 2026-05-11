"""분류된 AppError 계층 + 외부 응답 핸들러.

CLAUDE.md §"에러 응답": 분류된 AppError 메시지만 외부, 스택트레이스 절대 노출 금지.
"""

from __future__ import annotations

from typing import ClassVar

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

_log = structlog.get_logger(__name__)


class AppError(Exception):
    """애플리케이션 도메인 에러의 기반 클래스. 서브클래스가 code/status 를 declare."""

    code: ClassVar[str] = "INTERNAL"
    status_code: ClassVar[int] = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class BadRequestError(AppError):
    code: ClassVar[str] = "BAD_REQUEST"
    status_code: ClassVar[int] = 400


class UnauthorizedError(AppError):
    code: ClassVar[str] = "UNAUTHORIZED"
    status_code: ClassVar[int] = 401


class ForbiddenError(AppError):
    code: ClassVar[str] = "FORBIDDEN"
    status_code: ClassVar[int] = 403


class NotFoundError(AppError):
    code: ClassVar[str] = "NOT_FOUND"
    status_code: ClassVar[int] = 404


class ConflictError(AppError):
    code: ClassVar[str] = "CONFLICT"
    status_code: ClassVar[int] = 409


class UnprocessableEntityError(AppError):
    code: ClassVar[str] = "UNPROCESSABLE"
    status_code: ClassVar[int] = 422


async def _app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    _log.warning(
        "app_error",
        code=exc.code,
        message=exc.message,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # 스택트레이스는 _log.exception 으로 로깅만; 응답 본문은 generic.
    _log.exception(
        "unhandled_error",
        exc_type=type(exc).__name__,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL", "message": "Internal server error"},
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
