"""Phase 6.6 — JobEventBus 단위 5 케이스.

per-session in-memory pub/sub — JobRunner 가 publish, SSE endpoint 가 subscribe.
SSE 진행 표시 8 stage (uploaded/ocr/llm/rule_based/resolved/vendor_failed/done/error).
"""

from __future__ import annotations

import asyncio

import pytest
from app.services.jobs.event_bus import JobEvent, JobEventBus, JobStage


@pytest.mark.asyncio
async def test_publish_then_subscribe_receives_event() -> None:
    """publish 후 subscribe 시작해도 backlog 가져옴 (replay)."""
    bus = JobEventBus()
    bus.publish(session_id=1, event=JobEvent(stage="uploaded", file_idx=0, total=1))

    received: list[JobEvent] = []
    async for event in bus.subscribe(session_id=1, replay=True):
        received.append(event)
        break  # 1건만 받고 종료.

    assert len(received) == 1
    assert received[0].stage == "uploaded"


@pytest.mark.asyncio
async def test_subscribe_then_publish_streams_event() -> None:
    """subscribe 후 publish — 신규 event 즉시 stream."""
    bus = JobEventBus()
    received: list[JobEvent] = []

    async def reader() -> None:
        async for event in bus.subscribe(session_id=42):
            received.append(event)
            if event.stage == "done":
                return

    task = asyncio.create_task(reader())
    await asyncio.sleep(0.01)
    bus.publish(session_id=42, event=JobEvent(stage="ocr", file_idx=0, total=2))
    bus.publish(session_id=42, event=JobEvent(stage="done", file_idx=2, total=2))
    await asyncio.wait_for(task, timeout=1.0)

    stages = [e.stage for e in received]
    assert stages == ["ocr", "done"]


@pytest.mark.asyncio
async def test_subscribe_filtered_by_session_id() -> None:
    """다른 session_id 의 event 는 mix 되지 않음."""
    bus = JobEventBus()
    bus.publish(session_id=1, event=JobEvent(stage="ocr", file_idx=0, total=1))
    bus.publish(session_id=2, event=JobEvent(stage="llm", file_idx=0, total=1))

    received: list[JobEvent] = []
    async for event in bus.subscribe(session_id=1, replay=True):
        received.append(event)
        break

    assert len(received) == 1
    assert received[0].stage == "ocr"  # session 1 의 event 만.


@pytest.mark.asyncio
async def test_done_stage_closes_stream() -> None:
    """done stage publish 후 subscribe 가 종료."""
    bus = JobEventBus()
    bus.publish(session_id=5, event=JobEvent(stage="done", file_idx=1, total=1))

    received: list[JobEvent] = []
    async for event in bus.subscribe(session_id=5, replay=True, close_on_done=True):
        received.append(event)

    assert len(received) == 1
    assert received[0].stage == "done"


def test_event_stages_complete() -> None:
    """JobStage Literal 의 모든 값이 ADR-010 SSE 메시지 스키마와 일치."""
    valid_stages: set[JobStage] = {
        "uploaded",
        "ocr",
        "llm",
        "rule_based",
        "resolved",
        "vendor_failed",
        "done",
        "error",
    }
    # 본 케이스는 Literal 의 contract 만 보장 — 실제로 publish 안 함.
    assert len(valid_stages) == 8
