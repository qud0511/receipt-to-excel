"""Phase 6.6 — JobRunner: 잡 큐 worker.

책임:
- 영수증 파서 (Phase 4) + 카드 사용내역 파서 (Phase 6.3) 양쪽 호출
- Transaction Matcher (Phase 6.4) 적용
- JobEventBus 에 stage 별 publish (UI Upload 진행 표시)
- error 시 'error' event + JobRunnerError raise

CLAUDE.md 성능:
- Ollama 호출은 ``asyncio.Semaphore(2)`` 로 제한 (영수증 OCR 단계).
- pdfplumber/openpyxl 동기 호출은 ``asyncio.to_thread``.

Sessions API (Phase 6.7) 가 BackgroundTasks 로 본 ``run()`` async 실행.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from app.domain.parsed_transaction import ParsedTransaction
from app.services.jobs.event_bus import JobEvent, JobEventBus
from app.services.matchers.transaction_matcher import (
    TransactionMatch,
    match_receipts_with_card_transactions,
)

# Caller (Sessions API) 가 주입할 parser callable shape.
ReceiptParser = Callable[..., Awaitable[list[ParsedTransaction]]]
CardStatementParser = Callable[..., list[ParsedTransaction]]

# CLAUDE.md 성능: Ollama 동시 호출 ≤ 2.
_OLLAMA_CONCURRENCY = 2


class JobRunnerError(RuntimeError):
    """잡 실패 — Sessions API 가 Session.status='failed' 로 설정."""


@dataclass
class JobResult:
    """잡 결과 — Sessions API 가 Transaction 영속 시 사용."""

    transactions: list[ParsedTransaction] = field(default_factory=list)
    matches: list[TransactionMatch] = field(default_factory=list)
    matched_count: int = 0


class JobRunner:
    """단일 잡 실행. Sessions API 가 인스턴스 1개 공유 (event_bus + parser 주입)."""

    def __init__(
        self,
        *,
        event_bus: JobEventBus,
        receipt_parser: ReceiptParser,
        card_statement_parser: CardStatementParser | None = None,
        ollama_concurrency: int = _OLLAMA_CONCURRENCY,
    ) -> None:
        self._event_bus = event_bus
        self._receipt_parser = receipt_parser
        self._card_statement_parser = card_statement_parser
        self._ollama_sem = asyncio.Semaphore(ollama_concurrency)

    async def run(
        self,
        *,
        session_id: int,
        receipts: list[tuple[str, bytes]],
        card_statements: list[tuple[str, bytes]],
    ) -> JobResult:
        """잡 e2e — 영수증 + 카드 사용내역 파싱 + 매칭. 단일 호출 atomic."""
        total = len(receipts) + len(card_statements)
        try:
            self._publish(
                session_id, stage="uploaded", file_idx=0, total=total,
                msg=f"업로드 수신 — 영수증 {len(receipts)} / 카드내역 {len(card_statements)}",
            )

            receipt_txs = await self._run_receipts(session_id, receipts, total=total)
            card_txs = self._run_card_statements(
                session_id, card_statements, total=total, offset=len(receipts),
            )

            matches = match_receipts_with_card_transactions(
                receipts=receipt_txs, card_transactions=card_txs,
            )
            matched_count = sum(
                1 for m in matches if m.receipt is not None and m.card_transaction is not None
            )

            transactions = self._reconcile_transactions(matches)
            self._publish(
                session_id, stage="done", file_idx=total, total=total,
                msg=f"파싱 완료 — {len(transactions)} 거래, 매칭 {matched_count}",
            )
            return JobResult(
                transactions=transactions, matches=matches, matched_count=matched_count,
            )
        except Exception as exc:
            self._publish(
                session_id, stage="error", file_idx=0, total=total,
                msg=f"잡 실패: {type(exc).__name__}: {exc}",
            )
            raise JobRunnerError(f"잡 {session_id} 실패: {exc}") from exc

    async def _run_receipts(
        self, session_id: int, receipts: list[tuple[str, bytes]], *, total: int,
    ) -> list[ParsedTransaction]:
        """영수증 파일별 파서 호출. Ollama 동시성 Semaphore(2) 제한."""
        results: list[ParsedTransaction] = []
        for idx, (filename, content) in enumerate(receipts):
            self._publish(
                session_id, stage="rule_based", file_idx=idx, total=total, filename=filename,
                msg=f"영수증 파싱 — {filename}",
            )
            async with self._ollama_sem:
                parsed = await self._receipt_parser(content, filename=filename)
            results.extend(parsed)
        return results

    def _run_card_statements(
        self,
        session_id: int,
        card_statements: list[tuple[str, bytes]],
        *,
        total: int,
        offset: int,
    ) -> list[ParsedTransaction]:
        """카드 사용내역 XLSX/CSV 파서 호출 — Phase 6.3 의 동기 진입점."""
        if not self._card_statement_parser:
            return []
        results: list[ParsedTransaction] = []
        for idx, (filename, content) in enumerate(card_statements):
            self._publish(
                session_id, stage="rule_based", file_idx=offset + idx, total=total,
                filename=filename, msg=f"카드 사용내역 파싱 — {filename}",
            )
            suffix = PurePosixPath(filename).suffix.lower()
            parsed = self._card_statement_parser(content, suffix=suffix)
            results.extend(parsed)
        return results

    def _reconcile_transactions(
        self, matches: list[TransactionMatch],
    ) -> list[ParsedTransaction]:
        """Match 결과 → 최종 ParsedTransaction list.

        매칭 성공 시 영수증 (parser 가 가맹점명 정확) 을 우선 채택.
        매칭 실패 시 영수증 단독 또는 카드 단독 그대로 추가.
        """
        out: list[ParsedTransaction] = []
        for m in matches:
            if m.receipt is not None:
                out.append(m.receipt)
            elif m.card_transaction is not None:
                out.append(m.card_transaction)
        return out

    def _publish(
        self,
        session_id: int,
        *,
        stage: str,
        file_idx: int,
        total: int,
        filename: str | None = None,
        msg: str = "",
    ) -> None:
        """event_bus.publish wrapper — JobStage Literal 안전성은 caller 책임."""
        # cast 는 caller (본 클래스 내부) 가 보장 — Literal 외 값 publish 안 함.
        from typing import cast

        from app.services.jobs.event_bus import JobStage

        self._event_bus.publish(
            session_id=session_id,
            event=JobEvent(
                stage=cast(JobStage, stage),
                file_idx=file_idx,
                total=total,
                filename=filename,
                msg=msg,
            ),
        )
