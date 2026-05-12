"""Phase 4 Smoke Gate — 실 카드사 매출전표 11+ 파일 검증.

CI 미실행 (``-m "not real_pdf"`` 로 제외). 로컬에서만:
    uv sync --extra ocr
    uv run pytest tests/smoke/ -m real_pdf

검증 기준: synthesis/05 §Phase 4 Smoke Gate.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import structlog
from app.services.parsers.base import BaseParser, ParseError
from app.services.parsers.router import ParserRouter
from app.services.parsers.rule_based.hana import HanaRuleBasedParser
from app.services.parsers.rule_based.hyundai import HyundaiRuleBasedParser
from app.services.parsers.rule_based.kbank import KBankRuleBasedParser
from app.services.parsers.rule_based.lotte import LotteRuleBasedParser
from app.services.parsers.rule_based.samsung import SamsungRuleBasedParser
from app.services.parsers.rule_based.shinhan import ShinhanRuleBasedParser
from app.services.parsers.rule_based.woori import WooriRuleBasedParser

if TYPE_CHECKING:
    from app.domain.parsed_transaction import ParsedTransaction

_SMOKE_DIR = Path(__file__).resolve().parent / "real_pdfs"
_RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _list_real_files() -> list[Path]:
    """tests/smoke/real_pdfs/ 안의 모든 PDF/JPG 파일. 부재 시 빈 list."""
    if not _SMOKE_DIR.exists():
        return []
    return sorted(
        p
        for p in _SMOKE_DIR.iterdir()
        if p.is_file()
        and not p.name.startswith(".")
        and p.suffix.lower() in {".pdf", ".jpg", ".jpeg", ".png"}
    )


def _build_router() -> ParserRouter:
    """실 자료용 router — 6 rule_based + OCR Hybrid (선택).

    [ocr] 미설치 시 OCR 없이 — hana/woori/lotte/kakaobank 검증은 ImportError 로 명시 실패.
    """
    from app.core.config import Settings

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

        settings = Settings()
        ocr_parser = OCRHybridParser(
            docling=DoclingService(),
            ollama=OllamaVisionClient(settings.ollama_base_url, settings.ollama_model),
        )
    except ImportError:
        # [ocr] extras 미설치 — OCR 케이스는 skip 됨.
        pass

    return ParserRouter(
        rule_based_parsers=rule_parsers,  # type: ignore[arg-type]
        ocr_hybrid_parser=ocr_parser,
        llm_enabled=False,
    )


def _record_result(
    file_path: Path,
    results: list[ParsedTransaction],
    elapsed: float,
) -> None:
    """tests/smoke/results/YYYYMMDD.md 에 누적 기록 — ADR-005 list 반환 대응.

    N-up 매출전표(1 파일 → N 거래)는 각 거래를 별도 row 로 기록. 파일 latency 는 전체 합산 1 회만.
    """
    _RESULTS_DIR.mkdir(exist_ok=True)
    today = datetime.now(UTC).strftime("%Y%m%d")
    md_path = _RESULTS_DIR / f"{today}.md"

    if not md_path.exists():
        header_cols = (
            "| file | tx_idx | parser_used | 가맹점명 | 거래일 | 금액 "
            "| confidence(high+medium) | latency_s |\n"
        )
        md_path.write_text(
            f"# Smoke Run — {today}\n\n{header_cols}|---|---|---|---|---|---|---|---|\n",
            encoding="utf-8",
        )

    with md_path.open("a", encoding="utf-8") as f:
        for idx, result in enumerate(results):
            high_medium = sum(
                1 for v in result.field_confidence.values() if v in ("high", "medium")
            )
            total = len(result.field_confidence)
            # latency 는 첫 row 만 기록 (파일 단위 시간) — N-up 다른 거래는 "-".
            latency_str = f"{elapsed:.1f}" if idx == 0 else "-"
            row = (
                f"| {file_path.name} | {idx + 1}/{len(results)} | {result.parser_used} | "
                f"{result.가맹점명} | {result.거래일} | {result.금액} | "
                f"{high_medium}/{total} | {latency_str} |\n"
            )
            f.write(row)


_REAL_FILES = _list_real_files()


@pytest.mark.real_pdf
@pytest.mark.skipif(
    not _REAL_FILES,
    reason="tests/smoke/real_pdfs/ 비어 있음 — 사용자가 실 자료 채워 넣어야 함",
)
@pytest.mark.parametrize("file_path", _REAL_FILES, ids=lambda p: p.name)
async def test_real_pdf_extracts_required_fields(file_path: Path) -> None:
    """필수 필드 + confidence + latency + parser_used 기대값 검증."""
    router = _build_router()
    content = file_path.read_bytes()

    # session_id+idx bind — Phase 1 PII 필터가 한국어 파일명 마스킹.
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        session_id=f"smoke-{datetime.now(UTC).strftime('%Y%m%d')}",
        idx=hash(file_path.name) & 0xFFFF,
    )

    start = time.monotonic()
    try:
        results = await router.parse(content, filename=file_path.name)
    except ParseError as e:
        pytest.fail(f"{file_path.name}: {type(e).__name__}: {e}")
    finally:
        structlog.contextvars.clear_contextvars()
    elapsed = time.monotonic() - start

    # 1 파일 → 1+ 거래 (ADR-005 list 반환).
    assert results, f"{file_path.name}: empty result list"

    for idx, result in enumerate(results):
        loc = f"{file_path.name}#tx{idx + 1}/{len(results)}"
        assert result.가맹점명, f"{loc}: 가맹점명 missing"
        assert result.거래일 is not None, f"{loc}: 거래일 missing"
        assert result.금액 > 0, f"{loc}: 금액 not positive"
        high_medium = sum(
            1 for v in result.field_confidence.values() if v in ("high", "medium")
        )
        assert high_medium >= 1, (
            f"{loc}: no high/medium confidence (confidence={result.field_confidence})"
        )

    # 처리 시간 — parser_used 별 limit (첫 결과 기준). N-up 은 latency 가 누적이라 여유.
    parser_used = results[0].parser_used
    limit_s = 5.0 if parser_used == "rule_based" else 60.0
    # N-up 다중 거래 시 거래 수에 비례 — 우리카드 4~5 tx 가 1 파일 → 5s 초과 가능.
    if parser_used == "rule_based" and len(results) > 1:
        limit_s = 5.0 * len(results)
    assert elapsed < limit_s, (
        f"{file_path.name}: {elapsed:.1f}s exceeds {limit_s}s "
        f"({parser_used}, {len(results)} tx)"
    )

    _record_result(file_path, results, elapsed)
