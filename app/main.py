"""FastAPI 앱 팩토리 — uvicorn 진입점 + 테스트용 create_app()."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from app.api.routes import auth, autocomplete, dashboard, health, sessions, templates
from app.core.auth import AzureADVerifier
from app.core.config import Settings
from app.core.errors import register_error_handlers
from app.core.logging import CorrelationIdMiddleware, configure_logging
from app.core.security import UploadGuard
from app.db.session import make_engine, make_session_maker
from app.domain.parsed_transaction import ParsedTransaction
from app.services.jobs.event_bus import JobEventBus
from app.services.jobs.runner import JobRunner
from app.services.parsers.base import BaseParser
from app.services.parsers.card_statement.xlsx_parser import parse_xlsx as parse_card_xlsx
from app.services.parsers.router import ParserRouter
from app.services.parsers.rule_based.hana import HanaRuleBasedParser
from app.services.parsers.rule_based.hyundai import HyundaiRuleBasedParser
from app.services.parsers.rule_based.kbank import KBankRuleBasedParser
from app.services.parsers.rule_based.lotte import LotteRuleBasedParser
from app.services.parsers.rule_based.samsung import SamsungRuleBasedParser
from app.services.parsers.rule_based.shinhan import ShinhanRuleBasedParser
from app.services.parsers.rule_based.woori import WooriRuleBasedParser
from app.services.storage.file_manager import FileSystemManager


def _build_parser_router(settings: Settings) -> ParserRouter:
    """Phase 4 ParserRouter — rule_based 7 + OCR Hybrid (선택) + LLM (선택).

    OCR Hybrid 는 ``docling``/``easyocr`` extras 설치 시만 활성화 (smoke gate 환경).
    로컬 dev 의 기본 — rule_based 만, OCR 미설치면 자동 skip.
    """
    rule_parsers: dict[str, BaseParser] = {
        "shinhan": ShinhanRuleBasedParser(),
        "samsung": SamsungRuleBasedParser(),
        "kbank": KBankRuleBasedParser(),
        "hana": HanaRuleBasedParser(),
        "hyundai": HyundaiRuleBasedParser(),
        "woori": WooriRuleBasedParser(),
        "lotte": LotteRuleBasedParser(),
    }

    ocr_parser: BaseParser | None = None
    try:
        from app.services.parsers.ocr_hybrid.docling_service import DoclingService
        from app.services.parsers.ocr_hybrid.ollama_vision_client import (
            OllamaVisionClient,
        )
        from app.services.parsers.ocr_hybrid.parser import OCRHybridParser

        ocr_parser = OCRHybridParser(
            docling=DoclingService(),
            ollama=OllamaVisionClient(settings.ollama_base_url, settings.ollama_model),
        )
    except ImportError:
        ocr_parser = None  # extras 미설치 — rule_based 만 가용.

    return ParserRouter(
        rule_based_parsers=rule_parsers,  # type: ignore[arg-type]
        ocr_hybrid_parser=ocr_parser,
        llm_enabled=settings.llm_enabled,
    )


async def _receipt_parser_impl(
    content: bytes, *, filename: str, router: ParserRouter
) -> list[ParsedTransaction]:
    """Phase 6.7b ParserRouter wire — JobRunner.receipt_parser 진입점.

    ``router.parse()`` 가 provider 감지 → rule_based / OCR / LLM tier 선택 후 호출.
    """
    return await router.parse(content, filename=filename)


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

    # Phase 6.6: JobEventBus + JobRunner. Phase 6.7b — ParserRouter wire (rule_based 7).
    app.state.event_bus = JobEventBus()
    app.state.parser_router = _build_parser_router(settings)

    async def _receipt_parser(
        content: bytes, *, filename: str
    ) -> list[ParsedTransaction]:
        return await _receipt_parser_impl(
            content, filename=filename, router=app.state.parser_router,
        )

    app.state.job_runner = JobRunner(
        event_bus=app.state.event_bus,
        receipt_parser=_receipt_parser,
        card_statement_parser=parse_card_xlsx,
    )

    # 가장 바깥 미들웨어로 correlation_id — 모든 요청·예외 경로 cover.
    app.add_middleware(CorrelationIdMiddleware)

    register_error_handlers(app)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(sessions.router)
    app.include_router(templates.router)
    app.include_router(autocomplete.router)
    app.include_router(dashboard.router)
    return app


app = create_app()
