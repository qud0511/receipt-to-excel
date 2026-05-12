"""Phase 6.7 — Sessions API.

UI 흐름 (ADR-010): Upload → Verify → Result. 본 라우터가 백엔드 entry point.

CLAUDE.md 강제:
- 모든 변경 라우터에 ``Depends(get_current_user)``.
- user_id WHERE 모든 쿼리.
- UploadGuard 3중 검증 (확장자 + MIME + 매직바이트).
- 디스크 파일명 uuid + 한글 원본명 metadata.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import UploadGuard, UploadValidationError
from app.db.repositories import session_repo, user_repo
from app.schemas.auth import UserInfo
from app.schemas.session import SessionCreatedResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])


async def _get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """app.state.db_sessionmaker → AsyncSession context."""
    sessionmaker = request.app.state.db_sessionmaker
    async with sessionmaker() as session:
        yield session


@router.post("", response_model=SessionCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: Request,
    background_tasks: BackgroundTasks,
    user: Annotated[UserInfo, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(_get_db)],
    receipts: Annotated[list[UploadFile], File()] = [],  # noqa: B006
    card_statements: Annotated[list[UploadFile], File()] = [],  # noqa: B006
    year_month: Annotated[str, Form()] = "",
    template_id: Annotated[int | None, Form()] = None,
) -> SessionCreatedResponse:
    """업로드 + 잡 큐 등록.

    ADR-010 자료 검증 B-4: 영수증 (PNG/JPG/PDF) + 카드 사용내역 (XLSX/CSV) 동시 업로드.
    UploadGuard 가 3중 검증 후 FileSystemManager 가 uuid 디스크명으로 저장.
    """
    if not receipts and not card_statements:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="receipts 또는 card_statements 중 최소 1 건 필요",
        )

    guard: UploadGuard = request.app.state.upload_guard
    file_manager = request.app.state.file_manager

    # UploadGuard 3중 검증 batch.
    all_items: list[tuple[str, bytes, str]] = []
    for uf in (*receipts, *card_statements):
        content = await uf.read()
        all_items.append((uf.filename or "unknown", content, uf.content_type or ""))
    try:
        validated = guard.validate_batch(all_items)
    except UploadValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)) from e

    # 사용자 row 보장.
    db_user = await user_repo.get_or_create_by_oid(db, oid=user.oid, name=user.name)
    source_filenames = [info.original_filename for info in validated]

    # Session DB row 생성 (status=parsing + processing_started_at).
    upload_session = await session_repo.create(
        db,
        user_id=db_user.id,
        year_month=year_month,
        source_filenames=source_filenames,
        status="parsing",
        template_id=template_id,
    )
    upload_session.processing_started_at = datetime.now(UTC)
    await db.commit()
    session_id = upload_session.id

    # 디스크 저장 — uuid 파일명 (보안).
    upload_dir = file_manager.session_upload_dir(
        user_oid=user.oid, session_id=str(session_id), create=True,
    )
    receipts_payload: list[tuple[str, bytes]] = []
    card_payload: list[tuple[str, bytes]] = []
    for idx, info in enumerate(validated):
        content = all_items[idx][1]
        (upload_dir / info.disk_filename).write_bytes(content)
        original = info.original_filename
        if idx < len(receipts):
            receipts_payload.append((original, content))
        else:
            card_payload.append((original, content))

    # JobRunner 등록 — BackgroundTasks (FastAPI 자체 worker).
    background_tasks.add_task(
        _run_job_background,
        request=request,
        session_id=session_id,
        user_id=db_user.id,
        receipts=receipts_payload,
        card_statements=card_payload,
    )

    return SessionCreatedResponse(session_id=session_id, status="parsing")


async def _run_job_background(
    *,
    request: Request,
    session_id: int,
    user_id: int,
    receipts: list[tuple[str, bytes]],
    card_statements: list[tuple[str, bytes]],
) -> None:
    """BackgroundTasks worker — JobRunner 호출 + DB 영속.

    Phase 6.6 JobRunner 가 publish 한 event 는 app.state.event_bus 에 누적 →
    SSE endpoint 가 실시간 stream.
    """
    runner = request.app.state.job_runner
    try:
        await runner.run(
            session_id=session_id,
            receipts=receipts,
            card_statements=card_statements,
        )
        # 완료 시 Session.status = awaiting_user.
        sessionmaker = request.app.state.db_sessionmaker
        async with sessionmaker() as db:
            upload_session = await session_repo.get(
                db, user_id=user_id, session_id=session_id,
            )
            upload_session.status = "awaiting_user"
            upload_session.processing_completed_at = datetime.now(UTC)
            await db.commit()
    except Exception:  # JobRunnerError 포함.
        sessionmaker = request.app.state.db_sessionmaker
        async with sessionmaker() as db:
            upload_session = await session_repo.get(
                db, user_id=user_id, session_id=session_id,
            )
            upload_session.status = "failed"
            upload_session.processing_completed_at = datetime.now(UTC)
            await db.commit()


@router.get("/{session_id}/stream")
async def stream_session_events(
    session_id: int,
    request: Request,
    user: Annotated[UserInfo, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(_get_db)],
) -> StreamingResponse:
    """SSE stream — ADR-010 자료 검증 SSE 스키마 (8 stage event).

    Headers:
    - ``Cache-Control: no-cache``, ``X-Accel-Buffering: no`` (CLAUDE.md 성능).
    - ``retry: 60000`` 본문 (재연결 권고 60s).
    """
    # IDOR 차단 — session_id 가 사용자 소유여야 함.
    db_user = await user_repo.get_or_create_by_oid(db, oid=user.oid, name=user.name)
    await session_repo.get(db, user_id=db_user.id, session_id=session_id)

    event_bus = request.app.state.event_bus

    async def event_generator() -> AsyncIterator[bytes]:
        yield b"retry: 60000\n\n"
        async for event in event_bus.subscribe(session_id=session_id, replay=True):
            payload = json.dumps(
                {
                    "stage": event.stage,
                    "file_idx": event.file_idx,
                    "total": event.total,
                    "filename": event.filename,
                    "msg": event.msg,
                    "tx_id": event.tx_id,
                },
                ensure_ascii=False,
            )
            yield f"data: {payload}\n\n".encode()
            # 1 초 간격 throttle (CLAUDE.md 성능: SSE 1s).
            await asyncio.sleep(0.01)  # test/dev: 짧게. 운영 client throttle 별도.

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
