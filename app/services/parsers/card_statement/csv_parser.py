"""CSV 카드 사용내역 파서 — UTF-8 only (Phase 6 정책, cp949 자동 감지는 후속).

ADR-010 자료 검증 C-1: UI Upload 의 영수증 + 카드 사용내역 동시 업로드 지원.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from app.domain.parsed_transaction import ParsedTransaction
from app.services.parsers.card_statement.base import (
    UnsupportedCardStatementError,
    detect_provider_from_content,
)
from app.services.parsers.card_statement.providers.shinhan import parse_shinhan_row


def parse_csv(content: bytes) -> list[ParsedTransaction]:
    """UTF-8 디코드 후 csv.DictReader 로 row 단위 파싱. provider 자동 감지."""
    provider = detect_provider_from_content(content, suffix=".csv")
    parser = _row_parser_for(provider)

    text = content.decode("utf-8-sig", errors="strict")
    reader = csv.DictReader(io.StringIO(text))

    results: list[ParsedTransaction] = []
    for row in reader:
        if all((v is None or str(v).strip() == "") for v in row.values()):
            continue
        results.append(parser(row))
    return results


def _row_parser_for(provider: str) -> Any:  # noqa: ANN401
    if provider == "shinhan":
        return parse_shinhan_row
    raise UnsupportedCardStatementError(f"row parser 미구현: {provider}")
