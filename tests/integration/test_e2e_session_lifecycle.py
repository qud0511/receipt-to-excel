"""Phase 6.10 — e2e 통합 테스트.

영수증 업로드 → 잡 파싱 → transactions 조회 → PATCH 검수 → Template 등록 →
generate → download 까지 단일 흐름. ADR-010 자료 검증 + 모든 ADR 통합 검증.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from app.db.models import Base
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.fixtures.synthetic_pdfs import make_shinhan_receipt
from tests.fixtures.synthetic_xlsx import make_template


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    app = create_app()

    async def _init_db(engine: AsyncEngine) -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_init_db(app.state.db_engine))
    return TestClient(app)


def test_full_lifecycle_upload_parse_generate_download(
    client: TestClient, tmp_path: Path,
) -> None:
    """전체 흐름 e2e — 합성 영수증 1 + 합성 양식 1 → 다운로드.

    1. POST /templates (양식 등록)
    2. POST /sessions (영수증 업로드 + 잡 큐) → BackgroundTask 가 동기 실행
    3. GET /sessions/{id}/transactions (추출 검증)
    4. POST /sessions/{id}/generate (XLSX + PDF + ZIP 생성)
    5. GET /sessions/{id}/download/{kind} (다운로드 검증)
    """
    # ── Step 1: 양식 등록 ───────────────────────────────────────────────────
    template_xlsx = make_template(mode="hybrid")
    template_resp = client.post(
        "/templates",
        files={"file": (
            "양식.xlsx",
            template_xlsx,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )},
        data={"name": "테스트 양식"},
    )
    assert template_resp.status_code == 201, template_resp.text
    template_id = template_resp.json()["template_id"]

    # ── Step 2: 영수증 업로드 + template_id 지정 ──────────────────────────
    receipt_pdf = make_shinhan_receipt(
        merchant="가짜한식당",
        transaction_dt="2026-05-03 12:30:00",
        amount=15000,
    )
    upload_resp = client.post(
        "/sessions",
        files={"receipts": ("receipt.pdf", receipt_pdf, "application/pdf")},
        data={"year_month": "2026-05", "template_id": str(template_id)},
    )
    assert upload_resp.status_code == 201, upload_resp.text
    session_id = upload_resp.json()["session_id"]

    # TestClient 의 BackgroundTasks 는 response 직후 동기 실행 — 잡 완료 대기 0.

    # ── Step 3: transactions 조회 ──────────────────────────────────────────
    txs_resp = client.get(f"/sessions/{session_id}/transactions")
    assert txs_resp.status_code == 200
    txs = txs_resp.json()["transactions"]
    # 합성 영수증 → shinhan rule_based parser → 1 건 추출.
    assert len(txs) == 1
    assert txs[0]["가맹점명"] == "가짜한식당"
    assert txs[0]["금액"] == 15000
    assert txs[0]["카드사"] == "shinhan"

    # ── Step 4: generate (XLSX + PDF + ZIP) ─────────────────────────────────
    gen_resp = client.post(f"/sessions/{session_id}/generate")
    assert gen_resp.status_code == 200, gen_resp.text
    artifacts = gen_resp.json()["artifacts"]
    kinds = {a["kind"] for a in artifacts}
    # XLSX 는 항상 생성. PDF 는 영수증 사진 (PNG/JPG) 부재라 skip 가능. ZIP 은 항상.
    assert "xlsx" in kinds
    assert "zip" in kinds

    # ── Step 5: download xlsx + zip ───────────────────────────────────────
    xlsx_resp = client.get(f"/sessions/{session_id}/download/xlsx")
    assert xlsx_resp.status_code == 200
    assert xlsx_resp.content.startswith(b"PK\x03\x04")  # XLSX 매직.

    zip_resp = client.get(f"/sessions/{session_id}/download/zip")
    assert zip_resp.status_code == 200
    assert zip_resp.content.startswith(b"PK\x03\x04")  # ZIP 매직.

    # ── Step 6: stats ───────────────────────────────────────────────────────
    stats_resp = client.get(f"/sessions/{session_id}/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["transaction_count"] == 1
    # baseline 15분/거래 x 1 = 900s.
    assert stats["baseline_s"] == 900

    # ── Step 7: dashboard 반영 ────────────────────────────────────────────
    dash_resp = client.get("/dashboard/summary")
    assert dash_resp.status_code == 200
    body = dash_resp.json()
    assert body["this_month"]["transaction_count"] == 1
    assert body["this_month"]["total_amount"] == 15000
    assert len(body["recent_expense_reports"]) == 1
    assert body["recent_expense_reports"][0]["session_id"] == session_id
