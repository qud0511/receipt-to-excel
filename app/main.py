"""FastAPI 앱 팩토리 — uvicorn 진입점 + 테스트용 create_app()."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from app.api.routes import auth, health, sessions
from app.core.auth import AzureADVerifier
from app.core.config import Settings
from app.core.errors import register_error_handlers
from app.core.logging import CorrelationIdMiddleware, configure_logging
from app.core.security import UploadGuard
from app.db.session import make_engine, make_session_maker
from app.domain.parsed_transaction import ParsedTransaction
from app.services.jobs.event_bus import JobEventBus
from app.services.jobs.runner import JobRunner
from app.services.parsers.card_statement.xlsx_parser import parse_xlsx as parse_card_xlsx
from app.services.storage.file_manager import FileSystemManager


async def _stub_receipt_parser(
    content: bytes, *, filename: str
) -> list[ParsedTransaction]:
    """Phase 6.7 임시 stub — Phase 6.7b 에서 ParserRouter (Phase 4) 와 wire.

    현재는 빈 list 반환 — 잡 자체는 정상 종료, transaction 영속 0건.
    """
    _ = content, filename
    return []


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

    engine = make_engine(settings.database_url)
    app.state.db_engine = engine
    app.state.db_sessionmaker = make_session_maker(engine)

    # Phase 6.1: UploadGuard + FileSystemManager (per-user FS).
    app.state.upload_guard = UploadGuard()
    app.state.file_manager = FileSystemManager.from_config(
        storage_root=Path(settings.storage_root),
    )

    # Phase 6.6: JobEventBus (in-memory pub/sub) + JobRunner (parser orchestration).
    app.state.event_bus = JobEventBus()
    app.state.job_runner = JobRunner(
        event_bus=app.state.event_bus,
        receipt_parser=_stub_receipt_parser,
        card_statement_parser=parse_card_xlsx,
    )

    # 가장 바깥 미들웨어로 correlation_id — 모든 요청·예외 경로 cover.
    app.add_middleware(CorrelationIdMiddleware)

    register_error_handlers(app)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(sessions.router)
    return app


app = create_app()
