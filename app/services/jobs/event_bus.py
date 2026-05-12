"""Phase 6.6 — Job 진행 event pub/sub (per-session in-memory queue).

ADR-010 자료 검증 SSE 스키마 8 stage. JobRunner 가 publish, Sessions API 의 SSE
endpoint 가 subscribe → response stream.

CLAUDE.md 성능: 1 초 간격 SSE — backlog replay 로 reconnect 안정.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal

JobStage = Literal[
    "uploaded",       # 업로드 수신
    "ocr",            # Docling OCR 진행 중
    "llm",            # OCR Hybrid LLM 호출 중
    "rule_based",     # rule_based parser 실행 중
    "resolved",       # CardTypeResolver / category 결정 완료
    "vendor_failed",  # 거래처 추정 실패 (UI "거래처 추정 실패" 메시지)
    "done",           # 잡 완료
    "error",          # 잡 실패 (file 단위)
]


@dataclass(frozen=True)
class JobEvent:
    """단일 SSE event payload — UI Upload/Verify 진행 표시 1 라인."""

    stage: JobStage
    file_idx: int
    total: int
    filename: str | None = None
    msg: str = ""
    tx_id: int | None = None


@dataclass
class _SessionChannel:
    """per-session backlog + 실시간 listener queue."""

    backlog: list[JobEvent] = field(default_factory=list)
    listeners: list[asyncio.Queue[JobEvent | None]] = field(default_factory=list)


class JobEventBus:
    """단일 process 안에서 per-session event broadcast.

    SSE reconnect 시 backlog replay — Phase 6 의 ``retry: 60000`` + Last-Event-ID
    재시도 지원. 메모리 누수 방지 위해 ``cleanup_session`` 호출 권장 (Job 종료 후).
    """

    def __init__(self) -> None:
        self._channels: dict[int, _SessionChannel] = {}

    def publish(self, *, session_id: int, event: JobEvent) -> None:
        """동기 publish — 새 event 를 backlog + 모든 listener queue 에 enqueue.

        JobRunner 가 OCR/LLM 단계 변화 시점에 호출. listener 가 0 이어도 backlog 누적
        (replay 위해).
        """
        channel = self._channels.setdefault(session_id, _SessionChannel())
        channel.backlog.append(event)
        for q in channel.listeners:
            q.put_nowait(event)

    async def subscribe(
        self,
        *,
        session_id: int,
        replay: bool = False,
        close_on_done: bool = True,
    ) -> AsyncIterator[JobEvent]:
        """SSE endpoint 가 호출 — backlog replay 후 신규 event 실시간 stream.

        ``close_on_done=True`` 시 'done' 또는 'error' stage 수신 후 generator 종료.
        """
        channel = self._channels.setdefault(session_id, _SessionChannel())

        # 1) backlog replay (옵션).
        if replay:
            for past in list(channel.backlog):
                yield past
                if close_on_done and past.stage in ("done", "error"):
                    return

        # 2) 신규 event 실시간 stream.
        queue: asyncio.Queue[JobEvent | None] = asyncio.Queue()
        channel.listeners.append(queue)
        try:
            while True:
                event = await queue.get()
                if event is None:
                    return
                yield event
                if close_on_done and event.stage in ("done", "error"):
                    return
        finally:
            channel.listeners.remove(queue)

    def cleanup_session(self, *, session_id: int) -> None:
        """Job 종료 후 메모리 해제. listener 들에 None sentinel send 후 channel 제거."""
        channel = self._channels.pop(session_id, None)
        if channel is None:
            return
        for q in channel.listeners:
            q.put_nowait(None)
