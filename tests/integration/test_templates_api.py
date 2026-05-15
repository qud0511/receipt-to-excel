"""Phase 6.8 — Templates API 통합 테스트.

CLAUDE.md 강제: auth / IDOR / 422 4 종.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from app.db.models import Base
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine

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


# 1) POST /templates/analyze — 영속 X 미리보기.
def test_analyze_template_returns_sheets(client: TestClient) -> None:
    xlsx = make_template(mode="hybrid")
    files = {
        "file": (
            "양식.xlsx",
            xlsx,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    }
    response = client.post("/templates/analyze", files=files)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "sheets" in body
    assert body["mapping_status"] == "mapped"
    # 합성 양식은 26.05_법인 / 26.05_개인 2 시트.
    assert any("법인" in name for name in body["sheets"])


# 2) POST /templates/analyze — 잘못된 양식 → 422.
def test_analyze_template_rejects_empty_xlsx(client: TestClient) -> None:
    from openpyxl import Workbook

    wb = Workbook()  # A2 마커 없는 빈 양식.
    import io as _io

    buf = _io.BytesIO()
    wb.save(buf)
    files = {
        "file": (
            "empty.xlsx",
            buf.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    }
    response = client.post("/templates/analyze", files=files)
    assert response.status_code == 422


# 3) POST /templates — 등록 후 GET list 노출.
def test_register_template_then_list(client: TestClient, tmp_path: Path) -> None:
    xlsx = make_template(mode="hybrid")
    files = {
        "file": (
            "A사 파견용.xlsx",
            xlsx,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    }
    data = {"name": "A사 파견용 양식"}
    create_resp = client.post("/templates", files=files, data=data)
    assert create_resp.status_code == 201, create_resp.text
    template_id = create_resp.json()["template_id"]
    assert create_resp.json()["mapping_status"] == "mapped"

    # FS 저장 확인.
    template_path = (
        tmp_path
        / "storage"
        / "users"
        / "default"
        / "templates"
        / str(template_id)
        / "template.xlsx"
    )
    assert template_path.exists(), f"{template_path} not created"

    # list 에 노출.
    list_resp = client.get("/templates")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert any(t["id"] == template_id for t in items)


# 4) GET /templates/{id}/grid — 셀 grid JSON.
def test_grid_returns_cells_with_coords(client: TestClient) -> None:
    xlsx = make_template(mode="hybrid")
    files = {
        "file": (
            "t.xlsx",
            xlsx,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    }
    create_resp = client.post("/templates", files=files, data={"name": "t"})
    template_id = create_resp.json()["template_id"]

    grid_resp = client.get(f"/templates/{template_id}/grid")
    assert grid_resp.status_code == 200
    body = grid_resp.json()
    assert "sheets" in body
    # 첫 시트의 cells 가 1+ row.
    first_sheet = next(iter(body["sheets"].values()))
    assert first_sheet["cells"], "grid cells empty"
    # row 7 헤더가 cell 에 포함되어야.
    has_row_7 = any(c["row"] == 7 for c in first_sheet["cells"])
    assert has_row_7


# 5) PATCH /templates/{id}/cells — 셀 값 수정.
def test_patch_cells_updates_values(client: TestClient) -> None:
    xlsx = make_template(mode="hybrid")
    create_resp = client.post(
        "/templates",
        files={
            "file": (
                "t.xlsx",
                xlsx,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={"name": "t"},
    )
    template_id = create_resp.json()["template_id"]

    # 첫 시트 (실제 시트명 grid 로 확인).
    grid = client.get(f"/templates/{template_id}/grid").json()
    actual_sheet = next(iter(grid["sheets"]))

    patch_body = {
        "cells": [
            {"sheet": actual_sheet, "row": 4, "col": 1, "value": "신규 회사명"},
        ],
    }
    patch_resp = client.patch(
        f"/templates/{template_id}/cells",
        json=patch_body,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["updated_count"] == 1

    # 재조회 시 셀 값 변경 확인.
    grid2 = client.get(f"/templates/{template_id}/grid").json()
    cells = grid2["sheets"][actual_sheet]["cells"]
    a4 = next((c for c in cells if c["row"] == 4 and c["col"] == 1), None)
    assert a4 is not None
    assert a4["value"] == "신규 회사명"


# 6) DELETE /templates/{id} — 204.
def test_delete_template(client: TestClient) -> None:
    xlsx = make_template(mode="hybrid")
    create_resp = client.post(
        "/templates",
        files={
            "file": (
                "t.xlsx",
                xlsx,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={"name": "t"},
    )
    template_id = create_resp.json()["template_id"]

    del_resp = client.delete(f"/templates/{template_id}")
    assert del_resp.status_code == 204

    # list 에서 사라짐.
    list_resp = client.get("/templates")
    items = list_resp.json()
    assert all(t["id"] != template_id for t in items)


# 7) GET /templates/{id}/raw — 원본 다운로드.
def test_download_template_raw(client: TestClient) -> None:
    xlsx = make_template(mode="hybrid")
    create_resp = client.post(
        "/templates",
        files={
            "file": (
                "t.xlsx",
                xlsx,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={"name": "t"},
    )
    template_id = create_resp.json()["template_id"]

    raw_resp = client.get(f"/templates/{template_id}/raw")
    assert raw_resp.status_code == 200
    # XLSX 매직바이트 PK\x03\x04.
    assert raw_resp.content.startswith(b"PK\x03\x04")
