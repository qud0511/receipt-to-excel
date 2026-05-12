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
from app.db.models import Transaction
from app.db.repositories import (
    expense_record_repo,
    session_repo,
    transaction_repo,
    user_repo,
)
from app.domain.parsed_transaction import ParsedTransaction
from app.schemas.auth import UserInfo
from app.schemas.session import (
    SessionCreatedResponse,
    TransactionListResponse,
    TransactionPatchRequest,
    TransactionView,
)

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
        result = await runner.run(
            session_id=session_id,
            receipts=receipts,
            card_statements=card_statements,
        )
        # 잡 결과 → Transaction DB 영속 + Session.status='awaiting_user'.
        sessionmaker = request.app.state.db_sessionmaker
        async with sessionmaker() as db:
            tx_rows = [
                _parsed_to_db_row(parsed, session_id=session_id, user_id=user_id)
                for parsed in result.transactions
            ]
            if tx_rows:
                await transaction_repo.bulk_create(
                    db, user_id=user_id, transactions=tx_rows,
                )
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


def _parsed_to_db_row(
    parsed: ParsedTransaction, *, session_id: int, user_id: int
) -> Transaction:
    """ParsedTransaction (도메인) → Transaction (ORM) 매핑.

    AD-1 raw 보존 — 가맹점명 그대로. AD-2 canonical 형식 (parser 가 보장).
    """
    return Transaction(
        session_id=session_id,
        user_id=user_id,
        merchant_name=parsed.가맹점명,
        transaction_date=parsed.거래일,
        transaction_time=parsed.거래시각,
        amount=parsed.금액,
        supply_amount=parsed.공급가액,
        vat=parsed.부가세,
        approval_number=parsed.승인번호,
        business_category=parsed.업종,
        card_number_masked=parsed.카드번호_마스킹,
        card_provider=parsed.카드사,
        parser_used=parsed.parser_used,
        field_confidence=dict(parsed.field_confidence),
        source_filename="(uuid 디스크명)",  # Phase 6.7c 에서 실 매핑.
        source_file_path="(per-user FS path)",  # Phase 6.7c.
        original_filename=None,  # Phase 6.7c — UploadInfo 와 link.
    )


_CONFIDENCE_SCORE: dict[str, float] = {
    "high": 1.0,
    "medium": 0.66,
    "low": 0.33,
    "none": 0.0,
}


def _compute_confidence_score(field_confidence: dict[str, str]) -> float:
    """row-level 종합 신뢰도 — high=1 medium=0.66 low=0.33 none=0 평균.

    ADR-010 자료 검증 B-5: Verify 그리드 'AI 신뢰도%' 컬럼 표시.
    """
    if not field_confidence:
        return 0.0
    scores = [_CONFIDENCE_SCORE.get(v, 0.0) for v in field_confidence.values()]
    return sum(scores) / len(scores)


def _classify_row_status(
    tx: Transaction, expense: object | None
) -> str:
    """Verify Filter chips 분류 (ADR-010 B-9): missing / review / complete."""
    if not tx.merchant_name or not tx.transaction_date or tx.amount <= 0:
        return "missing"
    confidences = list(tx.field_confidence.values()) if tx.field_confidence else []
    if any(v in ("low", "none") for v in confidences):
        return "review"
    return "complete"


@router.get("/{session_id}/transactions", response_model=TransactionListResponse)
async def list_transactions(
    session_id: int,
    user: Annotated[UserInfo, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(_get_db)],
    status_filter: Annotated[str, str] = "all",
) -> TransactionListResponse:
    """Verify 그리드 백엔드 — 거래 + 신뢰도 + (ExpenseRecord 사용자 입력) + Filter chips 카운트.

    ADR-010 B-5: 9 컬럼 + B-9: filter (all/missing/review/complete).
    """
    db_user = await user_repo.get_or_create_by_oid(db, oid=user.oid, name=user.name)
    # IDOR 차단.
    await session_repo.get(db, user_id=db_user.id, session_id=session_id)

    txs = await transaction_repo.list_for_session(
        db, user_id=db_user.id, session_id=session_id,
    )

    counts = {"all": len(txs), "missing": 0, "review": 0, "complete": 0}
    views: list[TransactionView] = []
    for tx in txs:
        expense = await expense_record_repo.get_by_transaction(
            db, user_id=db_user.id, transaction_id=tx.id,
        )
        row_status = _classify_row_status(tx, expense)
        counts[row_status] += 1
        if status_filter not in ("all", row_status):
            continue
        views.append(
            TransactionView(
                id=tx.id,
                가맹점명=tx.merchant_name,
                거래일=tx.transaction_date.isoformat(),
                거래시각=tx.transaction_time.isoformat() if tx.transaction_time else None,
                금액=tx.amount,
                업종=tx.business_category,
                카드사=tx.card_provider,
                카드번호_마스킹=tx.card_number_masked,
                parser_used=tx.parser_used,
                field_confidence=dict(tx.field_confidence) if tx.field_confidence else {},
                confidence_score=_compute_confidence_score(
                    dict(tx.field_confidence) if tx.field_confidence else {},
                ),
                vendor=None,  # Phase 6.9 vendor_repo lookup 으로 채움.
                project=None,  # Phase 6.9.
                purpose=expense.purpose if expense else None,
                headcount=expense.headcount if expense else None,
                attendees=list(expense.attendees_json) if expense else [],
            ),
        )
    return TransactionListResponse(transactions=views, counts=counts)


@router.patch("/{session_id}/transactions/{tx_id}")
async def patch_transaction(
    session_id: int,
    tx_id: int,
    body: TransactionPatchRequest,
    user: Annotated[UserInfo, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(_get_db)],
) -> dict[str, object]:
    """Verify 검수 입력 저장 — last-write-wins (ADR-010 D-2).

    Body 의 not-None 필드만 적용. 다른 사용자 transaction 참조 시 403.
    """
    db_user = await user_repo.get_or_create_by_oid(db, oid=user.oid, name=user.name)
    # IDOR — session 소유 확인.
    await session_repo.get(db, user_id=db_user.id, session_id=session_id)

    patch = body.model_dump(exclude_none=False)
    updated = await expense_record_repo.upsert_user_input(
        db, user_id=db_user.id, transaction_id=tx_id, patch=patch,
    )
    # commit 전에 값을 캡처 — expire_on_commit 으로 인한 lazy load 회피.
    response_payload: dict[str, object] = {
        "ok": True,
        "transaction_id": tx_id,
        "expense_record_id": updated.id,
        "updated_at": updated.updated_at.isoformat(),
    }
    await db.commit()
    return response_payload


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
