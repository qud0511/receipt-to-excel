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
from fastapi.responses import FileResponse, StreamingResponse
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
    BulkTagRequest,
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

    # 디스크 저장 — uuid 파일명 (보안). original_filename → disk_filename 매핑 보관.
    upload_dir = file_manager.session_upload_dir(
        user_oid=user.oid, session_id=str(session_id), create=True,
    )
    receipts_payload: list[tuple[str, bytes]] = []
    card_payload: list[tuple[str, bytes]] = []
    disk_map: dict[str, str] = {}
    for idx, info in enumerate(validated):
        content = all_items[idx][1]
        (upload_dir / info.disk_filename).write_bytes(content)
        original = info.original_filename
        disk_map[original] = info.disk_filename
        if idx < len(receipts):
            receipts_payload.append((original, content))
        else:
            card_payload.append((original, content))
    # _run_job_background 에서 retrieval. dict-of-dicts 로 session_id 별 격리.
    if not hasattr(request.app.state, "_disk_filename_map"):
        request.app.state._disk_filename_map = {}
    request.app.state._disk_filename_map[session_id] = disk_map

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
        # original_filename → disk_filename 매핑은 Sessions API 의 _disk_filename_map 보유.
        disk_map = request.app.state._disk_filename_map.pop(session_id, {})
        sessionmaker = request.app.state.db_sessionmaker
        async with sessionmaker() as db:
            tx_rows = [
                _parsed_to_db_row(
                    parsed,
                    session_id=session_id,
                    user_id=user_id,
                    original_filename=source,
                    disk_filename=disk_map.get(source, ""),
                )
                for parsed, source in zip(
                    result.transactions, result.source_filenames, strict=True,
                )
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
    parsed: ParsedTransaction,
    *,
    session_id: int,
    user_id: int,
    original_filename: str,
    disk_filename: str,
) -> Transaction:
    """ParsedTransaction (도메인) → Transaction (ORM) 매핑.

    AD-1 raw 보존 — 가맹점명 그대로. AD-2 canonical 형식 (parser 가 보장).
    source_filename = uuid 디스크명 (보안), original_filename = 한글 원본명 (UX).
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
        source_filename=disk_filename,
        source_file_path=disk_filename,  # session_upload_dir + disk_filename 으로 재구성 가능.
        original_filename=original_filename,
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


@router.get("/{session_id}/preview-xlsx")
async def preview_session_xlsx(
    session_id: int,
    user: Annotated[UserInfo, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(_get_db)],
) -> dict[str, object]:
    """Verify '엑셀 미리보기' 토글 — 본 Session 의 거래가 양식의 어느 셀에 들어갈지 JSON.

    Phase 6.7b-4 단순 버전: 현 Transaction list + (matched) ExpenseRecord 의 row 값만
    JSON 으로 반환. Template 매핑 적용은 Phase 6.7b-5 (generate) 와 동일 로직 공유.
    """
    db_user = await user_repo.get_or_create_by_oid(db, oid=user.oid, name=user.name)
    upload_session = await session_repo.get(
        db, user_id=db_user.id, session_id=session_id,
    )
    txs = await transaction_repo.list_for_session(
        db, user_id=db_user.id, session_id=session_id,
    )

    rows: list[dict[str, object]] = []
    for tx in txs:
        expense = await expense_record_repo.get_by_transaction(
            db, user_id=db_user.id, transaction_id=tx.id,
        )
        rows.append(
            {
                "거래일": tx.transaction_date.isoformat(),
                "가맹점": tx.merchant_name,
                "금액": tx.amount,
                "용도": expense.purpose if expense else None,
                "인원": expense.headcount if expense else None,
                "동석자": list(expense.attendees_json) if expense else [],
                "비고": expense.auto_note if expense else "",
            },
        )

    return {
        "session_id": session_id,
        "template_id": upload_session.template_id,
        "year_month": upload_session.year_month,
        "row_count": len(rows),
        "rows": rows,
    }


@router.get("/{session_id}/transactions/{tx_id}/receipt")
async def get_transaction_receipt(
    session_id: int,
    tx_id: int,
    request: Request,
    user: Annotated[UserInfo, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(_get_db)],
) -> FileResponse:
    """Verify 좌 panel — 원본 영수증 이미지/PDF 반환.

    Transaction.source_filename (uuid disk name) 을 FileSystemManager 경로로 변환 →
    FileResponse. per-user FS scope 강제 (IDOR + path traversal 차단).
    """
    db_user = await user_repo.get_or_create_by_oid(db, oid=user.oid, name=user.name)
    # IDOR.
    await session_repo.get(db, user_id=db_user.id, session_id=session_id)
    tx = await db.get(Transaction, tx_id)
    if tx is None or tx.user_id != db_user.id or tx.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    if not tx.source_filename:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="original receipt unavailable",
        )

    file_manager = request.app.state.file_manager
    upload_dir = file_manager.session_upload_dir(
        user_oid=user.oid, session_id=str(session_id),
    )
    target = upload_dir / tx.source_filename
    # path traversal 차단 — 정규화 후 upload_dir 의 prefix 안에 있는지.
    resolved = target.resolve(strict=False)
    if not str(resolved).startswith(str(upload_dir.resolve(strict=False))):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="path escape")
    if not resolved.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file missing")

    return FileResponse(
        path=resolved,
        filename=tx.original_filename or tx.source_filename,
    )


@router.post("/{session_id}/transactions/bulk-tag")
async def bulk_tag_transactions(
    session_id: int,
    body: BulkTagRequest,
    user: Annotated[UserInfo, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(_get_db)],
) -> dict[str, object]:
    """다중 거래 일괄 태그 적용 — transactional rollback (ADR-010 D-1).

    한 row 라도 실패 시 전체 롤백 + 409 + failed_tx_ids[]. patch 본문 형식은
    PATCH endpoint 와 동일 (variable subset).
    """
    db_user = await user_repo.get_or_create_by_oid(db, oid=user.oid, name=user.name)
    # IDOR — session 소유 확인.
    await session_repo.get(db, user_id=db_user.id, session_id=session_id)

    patch = body.patch.model_dump(exclude_none=False)
    failed: list[int] = []
    updated_count = 0
    try:
        for tx_id in body.transaction_ids:
            try:
                await expense_record_repo.upsert_user_input(
                    db, user_id=db_user.id, transaction_id=tx_id, patch=patch,
                )
                updated_count += 1
            except Exception:
                failed.append(tx_id)
                # ADR-010 D-1: 전체 롤백 — 첫 실패에서 break.
                raise
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"failed_tx_ids": failed, "updated_count": 0},
        ) from None

    return {"ok": True, "updated_count": updated_count}


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
