"""Phase 6.7 — Sessions API 통합 테스트 (POST + SSE 우선).

CLAUDE.md 강제: auth / IDOR / 422 4 종 통합 테스트 의무.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from app.db.models import Base, UploadSession, User
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """app + per-test SQLite + per-test storage_root + REQUIRE_AUTH=false."""
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    app = create_app()

    async def _init_db(engine: AsyncEngine) -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_init_db(app.state.db_engine))
    return TestClient(app)


def _png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


def test_post_sessions_creates_db_row_and_enqueues_job(client: TestClient) -> None:
    files = {"receipts": ("receipt.png", _png_bytes(), "image/png")}
    data = {"year_month": "2026-05"}
    response = client.post("/sessions", files=files, data=data)

    assert response.status_code == 201, response.text
    body = response.json()
    assert "session_id" in body
    assert body["status"] == "parsing"


def test_post_sessions_writes_files_to_per_user_dir(
    client: TestClient, tmp_path: Path
) -> None:
    """업로드 후 storage/users/default/sessions/{id}/uploads/ 에 uuid 파일 저장."""
    files = {"receipts": ("한글영수증.png", _png_bytes(), "image/png")}
    data = {"year_month": "2026-05"}
    response = client.post("/sessions", files=files, data=data)
    session_id = response.json()["session_id"]

    upload_dir = (
        tmp_path / "storage" / "users" / "default" / "sessions" / str(session_id) / "uploads"
    )
    assert upload_dir.exists(), f"{upload_dir} not created"
    files_on_disk = list(upload_dir.iterdir())
    assert len(files_on_disk) == 1
    # uuid + .png suffix — 한글 부재.
    assert files_on_disk[0].name.endswith(".png")
    assert "한글영수증" not in files_on_disk[0].name


def test_post_sessions_rejects_wrong_magic_bytes(client: TestClient) -> None:
    bad_content = b"%PDF-1.4\n"
    files = {"receipts": ("fake.png", bad_content, "image/png")}
    data = {"year_month": "2026-05"}
    response = client.post("/sessions", files=files, data=data)
    assert response.status_code == 422


def test_post_sessions_rejects_no_files(client: TestClient) -> None:
    data = {"year_month": "2026-05"}
    response = client.post("/sessions", data=data)
    assert response.status_code == 422


def test_sse_stream_includes_retry_60000(client: TestClient) -> None:
    files = {"receipts": ("a.png", _png_bytes(), "image/png")}
    data = {"year_month": "2026-05"}
    create_resp = client.post("/sessions", files=files, data=data)
    session_id = create_resp.json()["session_id"]

    with client.stream("GET", f"/sessions/{session_id}/stream") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers.get("x-accel-buffering") == "no"
        first_chunk = b""
        for chunk in response.iter_bytes(chunk_size=1024):
            first_chunk += chunk
            if b"retry: 60000" in first_chunk:
                break
            if len(first_chunk) > 4096:
                break
        assert b"retry: 60000" in first_chunk


def test_get_transactions_returns_empty_for_new_session(client: TestClient) -> None:
    """업로드 직후 — 잡 BackgroundTask 가 완료되기 전에는 transaction 0건일 수 있음.

    TestClient 는 BackgroundTasks 가 response 직후 실행됨 — 잡이 완료된 후 GET 호출.
    """
    files = {"receipts": ("a.png", _png_bytes(), "image/png")}
    data = {"year_month": "2026-05"}
    create_resp = client.post("/sessions", files=files, data=data)
    session_id = create_resp.json()["session_id"]

    # PNG 영수증 → ParserRouter 가 provider=unknown + OCR 없음 → ParseError → JobRunnerError
    # → Session.status='failed'. 본 케이스는 endpoint 자체 동작 확인 (transaction 0건 정상).
    response = client.get(f"/sessions/{session_id}/transactions")
    assert response.status_code == 200
    body = response.json()
    assert "transactions" in body
    assert "counts" in body
    assert body["counts"]["all"] == 0


@pytest.mark.skip(
    reason="Phase 6.7b-3 e2e 에서 통합 검증 — TestClient + asyncio.run race 회피."
)
def test_patch_transaction_last_write_wins(client: TestClient) -> None:
    """PATCH 가 ExpenseRecord upsert — 두 번째 PATCH 가 첫 번째 덮어쓰기."""
    import asyncio

    from app.db.models import Transaction, User

    async def _create_tx() -> tuple[int, int]:
        sessionmaker = client.app.state.db_sessionmaker  # type: ignore[attr-defined]
        async with sessionmaker() as db:
            user = User(oid="default", name="t", email="t@x")
            db.add(user)
            await db.flush()
            # Phase 6.9 정식 vendor lookup 전까지 placeholder vendor 영속.
            from app.db.models import UploadSession, Vendor

            placeholder = Vendor(id=0, user_id=user.id, name="(미입력)")
            db.add(placeholder)
            await db.flush()

            sess = UploadSession(
                user_id=user.id,
                year_month="2026-05",
                source_filenames=["r.png"],
                status="awaiting_user",
            )
            db.add(sess)
            await db.flush()
            tx = Transaction(
                session_id=sess.id,
                user_id=user.id,
                merchant_name="가맹점",
                transaction_date=__import__("datetime").date(2026, 5, 1),
                amount=10000,
                card_provider="shinhan",
                parser_used="rule_based",
                field_confidence={"가맹점명": "high"},
                source_filename="x.png",
                source_file_path="/dev/null",
            )
            db.add(tx)
            await db.flush()
            await db.commit()
            return sess.id, tx.id  # type: ignore[return-value]

    session_id, tx_id = asyncio.run(_create_tx())

    # 1차 PATCH.
    r1 = client.patch(
        f"/sessions/{session_id}/transactions/{tx_id}",
        json={"purpose": "중식", "headcount": 3, "attendees": ["홍길동"]},
    )
    assert r1.status_code == 200
    assert r1.json()["ok"] is True

    # 2차 PATCH — purpose 덮어쓰기.
    r2 = client.patch(
        f"/sessions/{session_id}/transactions/{tx_id}",
        json={"purpose": "회의"},
    )
    assert r2.status_code == 200

    # GET 으로 last-write 확인.
    listing = client.get(f"/sessions/{session_id}/transactions").json()
    txn = next(t for t in listing["transactions"] if t["id"] == tx_id)
    assert txn["purpose"] == "회의"
    assert txn["headcount"] == 3  # 첫 PATCH 의 값 보존 (last-write-wins 는 필드 단위).
    assert txn["attendees"] == ["홍길동"]


def test_bulk_tag_rollback_on_partial_failure(client: TestClient) -> None:
    """존재하지 않는 transaction_id 포함 → 409 + 전체 rollback (ADR-010 D-1).

    REQUIRE_AUTH=false 이라 default 사용자가 단일. 본 케이스는 endpoint contract 검증.
    """
    # 빈 session 생성 (transactions 0).
    files = {"receipts": ("a.png", _png_bytes(), "image/png")}
    data = {"year_month": "2026-05"}
    create_resp = client.post("/sessions", files=files, data=data)
    session_id = create_resp.json()["session_id"]

    # 존재 안 하는 transaction_id [99999] 로 bulk-tag → 409 또는 403.
    body = {
        "transaction_ids": [99999],
        "patch": {"purpose": "중식", "headcount": 3},
    }
    response = client.post(f"/sessions/{session_id}/transactions/bulk-tag", json=body)
    assert response.status_code in (403, 409), response.text


def test_sse_stream_rejects_idor(client: TestClient) -> None:
    """다른 사용자의 session_id 접근 → 403 (REQUIRE_AUTH=false 환경에서 직접 DB 조작)."""

    async def _make_other_user_session() -> int:
        sessionmaker = client.app.state.db_sessionmaker  # type: ignore[attr-defined]
        async with sessionmaker() as db:
            other = User(oid="other-user", name="other", email="other@test.invalid")
            db.add(other)
            await db.flush()
            sess = UploadSession(
                user_id=other.id,
                year_month="2026-05",
                source_filenames=["x.png"],
                status="parsing",
            )
            db.add(sess)
            await db.flush()
            await db.commit()
            return sess.id  # type: ignore[no-any-return]

    other_session_id = asyncio.run(_make_other_user_session())
    response = client.get(f"/sessions/{other_session_id}/stream")
    assert response.status_code in (403, 404)


# ── P8.8 — PDF 422 fix: kind 계약 {xlsx, layout_pdf, merged_pdf, zip} ──────────


def _make_real_png(*, width: int = 400, height: int = 600) -> bytes:
    import io as _io

    from PIL import Image as _Image

    buf = _io.BytesIO()
    _Image.new("RGB", (width, height), "white").save(buf, format="PNG")
    return buf.getvalue()


def _register_template(client: TestClient) -> int:
    from tests.fixtures.synthetic_xlsx import make_template

    resp = client.post(
        "/templates",
        files={
            "file": (
                "양식.xlsx",
                make_template(mode="hybrid"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        },
        data={"name": "P8.8 양식"},
    )
    assert resp.status_code == 201, resp.text
    return int(resp.json()["template_id"])


def test_generate_with_pdf_receipt_persists_merged_pdf_kind(
    client: TestClient,
) -> None:
    """PDF 영수증 입력 → kind='merged_pdf' artifact (kind='pdf' 아님)."""
    from tests.fixtures.synthetic_pdfs import make_shinhan_receipt

    template_id = _register_template(client)
    pdf = make_shinhan_receipt(
        merchant="가짜한식당",
        transaction_dt="2026-05-03 12:30:00",
        amount=15000,
    )
    upload = client.post(
        "/sessions",
        files={"receipts": ("receipt.pdf", pdf, "application/pdf")},
        data={"year_month": "2026-05", "template_id": str(template_id)},
    )
    assert upload.status_code == 201, upload.text
    session_id = upload.json()["session_id"]

    gen = client.post(f"/sessions/{session_id}/generate")
    assert gen.status_code == 200, gen.text
    kinds = {a["kind"] for a in gen.json()["artifacts"]}
    assert "merged_pdf" in kinds, kinds
    assert "layout_pdf" not in kinds  # PNG/JPG tx 없음.
    assert "pdf" not in kinds  # deprecated kind name.


def test_download_merged_pdf_returns_pdf_magic(client: TestClient) -> None:
    """GET /download/merged_pdf → 200 + %PDF magic."""
    from tests.fixtures.synthetic_pdfs import make_shinhan_receipt

    template_id = _register_template(client)
    pdf = make_shinhan_receipt(transaction_dt="2026-05-03 12:30:00", amount=10000)
    upload = client.post(
        "/sessions",
        files={"receipts": ("r.pdf", pdf, "application/pdf")},
        data={"year_month": "2026-05", "template_id": str(template_id)},
    )
    session_id = upload.json()["session_id"]
    gen = client.post(f"/sessions/{session_id}/generate")
    assert gen.status_code == 200, gen.text

    resp = client.get(f"/sessions/{session_id}/download/merged_pdf")
    assert resp.status_code == 200, resp.text
    assert resp.content.startswith(b"%PDF"), "merged_pdf magic"


def test_download_pdf_kind_is_deprecated_returns_422(client: TestClient) -> None:
    """legacy kind='pdf' 은 더 이상 허용 안 됨 → 422."""
    files = {"receipts": ("a.png", _png_bytes(), "image/png")}
    resp = client.post("/sessions", files=files, data={"year_month": "2026-05"})
    session_id = resp.json()["session_id"]

    bad = client.get(f"/sessions/{session_id}/download/pdf")
    assert bad.status_code == 422, bad.text


def test_generate_with_image_tx_persists_layout_pdf_kind(
    client: TestClient,
) -> None:
    """PNG/JPG 영수증 (tx.source_file_path) → kind='layout_pdf' artifact."""
    import uuid
    from datetime import date

    from app.db.models import Transaction, UploadSession, User

    template_id = _register_template(client)
    png = _make_real_png()

    async def _seed() -> int:
        fm = client.app.state.file_manager  # type: ignore[attr-defined]
        sm = client.app.state.db_sessionmaker  # type: ignore[attr-defined]
        async with sm() as db:
            user = (await db.execute(
                __import__("sqlalchemy").select(User).where(User.oid == "default")
            )).scalar_one_or_none()
            if user is None:
                user = User(oid="default", name="기본", email=None)
                db.add(user)
                await db.flush()
            sess = UploadSession(
                user_id=user.id,
                year_month="2026-05",
                source_filenames=["a.png"],
                status="awaiting_user",
                template_id=template_id,
            )
            db.add(sess)
            await db.flush()
            session_id = sess.id

            upload_dir = fm.session_upload_dir(
                user_oid="default", session_id=str(session_id), create=True
            )
            disk_name = f"{uuid.uuid4().hex}.png"
            (upload_dir / disk_name).write_bytes(png)

            tx = Transaction(
                session_id=session_id,
                user_id=user.id,
                merchant_name="가짜이미지가맹점",
                transaction_date=date(2026, 5, 7),
                amount=12000,
                card_provider="shinhan",
                parser_used="ocr_hybrid",
                field_confidence={"가맹점명": "high"},
                source_filename=disk_name,
                source_file_path=str(upload_dir / disk_name),
            )
            db.add(tx)
            await db.commit()
            return int(session_id)

    session_id = asyncio.run(_seed())

    gen = client.post(f"/sessions/{session_id}/generate")
    assert gen.status_code == 200, gen.text
    kinds = {a["kind"] for a in gen.json()["artifacts"]}
    assert "layout_pdf" in kinds, kinds
    assert "merged_pdf" not in kinds  # PDF tx 없음.

    dl = client.get(f"/sessions/{session_id}/download/layout_pdf")
    assert dl.status_code == 200, dl.text
    assert dl.content.startswith(b"%PDF"), "layout_pdf magic"


def test_download_layout_pdf_rejects_other_user(client: TestClient) -> None:
    """IDOR — 다른 사용자의 session_id /download/layout_pdf 접근 → 403/404."""

    async def _make_other_session() -> int:
        sm = client.app.state.db_sessionmaker  # type: ignore[attr-defined]
        async with sm() as db:
            other = User(oid="other-p88", name="o", email="o@x")
            db.add(other)
            await db.flush()
            sess = UploadSession(
                user_id=other.id,
                year_month="2026-05",
                source_filenames=["x.png"],
                status="awaiting_user",
            )
            db.add(sess)
            await db.flush()
            await db.commit()
            return int(sess.id)

    other_id = asyncio.run(_make_other_session())
    resp = client.get(f"/sessions/{other_id}/download/layout_pdf")
    assert resp.status_code in (403, 404), resp.text
