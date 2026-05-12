"""Phase 6.6 — JobRunner 단위 4 케이스.

JobRunner 책임:
- 영수증 파서 + 카드 사용내역 파서 양쪽 호출
- Transaction Matcher 적용 (영수증 ↔ 카드 link)
- JobEventBus publish (stage 별 진행 표시)
- error 시 'error' stage event + Session.status='failed'

CLAUDE.md 성능: Ollama 호출은 Semaphore(2) — 본 테스트는 mock parser 로 검증.
"""

from __future__ import annotations

from datetime import date, time

import pytest
from app.domain.parsed_transaction import ParsedTransaction
from app.services.jobs.event_bus import JobEvent, JobEventBus
from app.services.jobs.runner import JobRunner, JobRunnerError


def _mock_receipt(merchant: str = "영수증가맹점", amount: int = 10000) -> ParsedTransaction:
    return ParsedTransaction(
        가맹점명=merchant,
        거래일=date(2026, 5, 1),
        거래시각=time(12, 30, 0),
        금액=amount,
        카드사="shinhan",
        parser_used="rule_based",
        field_confidence={"가맹점명": "high"},
    )


async def test_runs_receipt_parser_and_publishes_stages() -> None:
    """1 영수증 → uploaded/rule_based/done event."""
    bus = JobEventBus()

    async def fake_receipt_parser(content: bytes, *, filename: str) -> list[ParsedTransaction]:
        return [_mock_receipt(merchant=filename)]

    runner = JobRunner(event_bus=bus, receipt_parser=fake_receipt_parser)
    receipts = [("receipt-1.pdf", b"%PDF-1.4\n")]
    result = await runner.run(session_id=1, receipts=receipts, card_statements=[])

    events: list[JobEvent] = []
    async for e in bus.subscribe(session_id=1, replay=True):
        events.append(e)
    stages = [e.stage for e in events]
    assert "uploaded" in stages
    assert "rule_based" in stages
    assert stages[-1] == "done"
    assert len(result.transactions) == 1


async def test_runs_card_statement_parser_path() -> None:
    """1 카드 사용내역 (XLSX 가정) → uploaded/rule_based/done event."""
    bus = JobEventBus()

    async def fake_receipt_parser(content: bytes, *, filename: str) -> list[ParsedTransaction]:
        return []

    def fake_card_parser(content: bytes, *, suffix: str) -> list[ParsedTransaction]:
        return [_mock_receipt(merchant="카드사용내역A", amount=5000)]

    runner = JobRunner(
        event_bus=bus,
        receipt_parser=fake_receipt_parser,
        card_statement_parser=fake_card_parser,
    )
    card_statements = [("법인카드.xlsx", b"PK\x03\x04dummy")]
    result = await runner.run(session_id=2, receipts=[], card_statements=card_statements)

    assert len(result.transactions) == 1
    events: list[JobEvent] = []
    async for e in bus.subscribe(session_id=2, replay=True):
        events.append(e)
    assert events[-1].stage == "done"


async def test_matches_receipt_to_card_transaction() -> None:
    """영수증 + 카드 둘 다 있을 때 matcher 가 1:1 link → 단일 거래 result."""
    bus = JobEventBus()
    receipt = _mock_receipt(merchant="영수증A", amount=8900)
    card_tx = _mock_receipt(merchant="카드내역A", amount=8900)

    async def fake_receipt_parser(content: bytes, *, filename: str) -> list[ParsedTransaction]:
        return [receipt]

    def fake_card_parser(content: bytes, *, suffix: str) -> list[ParsedTransaction]:
        return [card_tx]

    runner = JobRunner(
        event_bus=bus,
        receipt_parser=fake_receipt_parser,
        card_statement_parser=fake_card_parser,
    )
    result = await runner.run(
        session_id=3,
        receipts=[("a.pdf", b"%PDF-")],
        card_statements=[("c.xlsx", b"PK")],
    )

    # 매칭 성공 → 1 거래 (영수증 source_file 가 link).
    assert len(result.transactions) == 1
    assert result.matched_count == 1


async def test_error_stage_published_on_parser_failure() -> None:
    """파서가 raise 하면 'error' stage event + JobRunnerError."""
    bus = JobEventBus()

    async def failing_parser(content: bytes, *, filename: str) -> list[ParsedTransaction]:
        raise ValueError("OCR 라이브러리 crash 시뮬레이션")

    runner = JobRunner(event_bus=bus, receipt_parser=failing_parser)
    with pytest.raises(JobRunnerError):
        await runner.run(session_id=4, receipts=[("bad.pdf", b"%PDF-")], card_statements=[])

    events: list[JobEvent] = []
    async for e in bus.subscribe(session_id=4, replay=True):
        events.append(e)
    assert events[-1].stage == "error"
