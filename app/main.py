"""FastAPI 앱 팩토리 — uvicorn 진입점 + 테스트용 create_app()."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import health


def create_app() -> FastAPI:
    app = FastAPI(
        title="Receipt-to-Excel v4",
        version="0.1.0",
        description="한국 카드/계좌 영수증 → 회계 XLSX 자동 변환.",
    )
    app.include_router(health.router)
    return app


app = create_app()
