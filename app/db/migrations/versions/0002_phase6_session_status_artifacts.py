"""Phase 6 — UploadSession status rename + 신규 컬럼 + GeneratedArtifact + Template.mapping_status

Revision ID: 0002_phase6_session_status_artifacts
Revises: 0001_initial
Create Date: 2026-05-12 16:00:00.000000+00:00

ADR-010 D-3 + 사용자 4-state 동의:
- UploadSession.status enum: 'review' → 'awaiting_user' rename (이름 1개만 변경)
- 신규 컬럼: processing_started_at, processing_completed_at, submitted_at
- Transaction.original_filename 컬럼 (한글 원본명 metadata, ADR-010 추천 7)
- Template.mapping_status enum (mapped/needs_mapping, ADR-011)
- GeneratedArtifact 신규 테이블 (ADR-010 D-4)

양방향 보장 (CLAUDE.md): upgrade + downgrade + 데이터 손실 0.
status='review' 기존 row 가 있으면 'awaiting_user' 로 자동 보정 (downgrade 도 역방향).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_phase6_session_status_artifacts"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 1. UploadSession.status: 'review' → 'awaiting_user' rename ────────────
    # SQLite 는 CHECK constraint 변경에 batch mode 필요 (PostgreSQL 도 호환).
    with op.batch_alter_table("upload_session") as batch_op:
        batch_op.drop_constraint("ck_upload_session_status", type_="check")
    # 기존 데이터 보정 — 'review' 가 있다면 'awaiting_user' 로.
    op.execute(
        "UPDATE upload_session SET status = 'awaiting_user' WHERE status = 'review'"
    )
    with op.batch_alter_table("upload_session") as batch_op:
        batch_op.create_check_constraint(
            "ck_upload_session_status",
            "status IN ('parsing', 'awaiting_user', 'generated', 'failed')",
        )
        # ── 2. 신규 컬럼: 처리 시간 + 제출 시각 ───────────────────────────────
        batch_op.add_column(
            sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("processing_completed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True)
        )

    # ── 3. Transaction.original_filename (한글 원본명 metadata) ───────────────
    with op.batch_alter_table("transaction") as batch_op:
        batch_op.add_column(
            sa.Column("original_filename", sa.String(length=512), nullable=True)
        )

    # ── 4. Template.mapping_status (ADR-011) ──────────────────────────────────
    with op.batch_alter_table("template") as batch_op:
        batch_op.add_column(
            sa.Column(
                "mapping_status",
                sa.String(length=16),
                nullable=False,
                server_default="mapped",
            )
        )
        batch_op.create_check_constraint(
            "ck_template_mapping_status",
            "mapping_status IN ('mapped', 'needs_mapping')",
        )

    # ── 5. GeneratedArtifact 신규 테이블 (ADR-010 D-4) ────────────────────────
    op.create_table(
        "generated_artifact",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(length=8), nullable=False),
        sa.Column("fs_path", sa.String(length=512), nullable=False),
        sa.Column("display_filename", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["upload_session.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "artifact_type IN ('xlsx', 'pdf', 'zip')",
            name="ck_generated_artifact_type",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_generated_artifact_session",
        "generated_artifact",
        ["session_id", "user_id"],
    )


def downgrade() -> None:
    # ── 5. GeneratedArtifact 테이블 제거 ──────────────────────────────────────
    op.drop_index("ix_generated_artifact_session", table_name="generated_artifact")
    op.drop_table("generated_artifact")

    # ── 4. Template.mapping_status 제거 ───────────────────────────────────────
    with op.batch_alter_table("template") as batch_op:
        batch_op.drop_constraint("ck_template_mapping_status", type_="check")
        batch_op.drop_column("mapping_status")

    # ── 3. Transaction.original_filename 제거 ─────────────────────────────────
    with op.batch_alter_table("transaction") as batch_op:
        batch_op.drop_column("original_filename")

    # ── 2/1. UploadSession 신규 컬럼 제거 + status rename 역방향 ──────────────
    with op.batch_alter_table("upload_session") as batch_op:
        batch_op.drop_column("submitted_at")
        batch_op.drop_column("processing_completed_at")
        batch_op.drop_column("processing_started_at")
        batch_op.drop_constraint("ck_upload_session_status", type_="check")
    # 데이터 역보정 — 'awaiting_user' → 'review'.
    op.execute(
        "UPDATE upload_session SET status = 'review' WHERE status = 'awaiting_user'"
    )
    with op.batch_alter_table("upload_session") as batch_op:
        batch_op.create_check_constraint(
            "ck_upload_session_status",
            "status IN ('parsing', 'review', 'generated', 'failed')",
        )
