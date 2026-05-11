"""FastAPI 앱 팩토리 — uvicorn 진입점 + 테스트용 create_app()."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import auth, health
from app.core.auth import AzureADVerifier
from app.core.config import Settings
from app.core.logging import CorrelationIdMiddleware, configure_logging


def create_app() -> FastAPI:
    settings = Settings()
    configure_logging(log_level=settings.log_level)

    app = FastAPI(
        title="Receipt-to-Excel v4",
        version="0.1.0",
        description="한국 카드/계좌 영수증 → 회계 XLSX 자동 변환.",
    )

    # Application-wide singletons. JWKS 캐시 재사용을 위해 verifier 는 1개 인스턴스만.
    app.state.settings = settings
    app.state.verifier = AzureADVerifier(settings)

    # 가장 바깥 미들웨어로 correlation_id — 모든 요청·예외 경로 cover.
    app.add_middleware(CorrelationIdMiddleware)

    app.include_router(health.router)
    app.include_router(auth.router)
    return app


app = create_app()
