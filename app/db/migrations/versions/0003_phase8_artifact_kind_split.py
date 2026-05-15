"""Phase 8.8 — GeneratedArtifact.artifact_type kind 분리: pdf → layout_pdf | merged_pdf

Revision ID: 0003_phase8_artifact_kind_split
Revises: 0002_phase6_session_status_artifacts
Create Date: 2026-05-15 07:20:00.000000+00:00

FE/BE 계약 정렬: FE 는 4 kinds (xlsx/layout_pdf/merged_pdf/zip), BE 는 3 kinds 였음.
- column length 8 → 16 (longest 'merged_pdf' = 10)
- CHECK constraint 갱신: pdf → layout_pdf, merged_pdf 추가
- 기존 row 'pdf' 가 있으면 'layout_pdf' 로 자동 변환 (downgrade 시 역방향)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_phase8_artifact_kind_split"
down_revision: str | None = "0002_phase6_session_status_artifacts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE generated_artifact SET artifact_type='layout_pdf' WHERE artifact_type='pdf'"
    )
    with op.batch_alter_table("generated_artifact") as batch_op:
        batch_op.drop_constraint("ck_generated_artifact_type", type_="check")
        batch_op.alter_column(
            "artifact_type",
            existing_type=sa.String(length=8),
            type_=sa.String(length=16),
        )
        batch_op.create_check_constraint(
            "ck_generated_artifact_type",
            "artifact_type IN ('xlsx', 'layout_pdf', 'merged_pdf', 'zip')",
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM generated_artifact WHERE artifact_type='merged_pdf'"
    )
    op.execute(
        "UPDATE generated_artifact SET artifact_type='pdf' WHERE artifact_type='layout_pdf'"
    )
    with op.batch_alter_table("generated_artifact") as batch_op:
        batch_op.drop_constraint("ck_generated_artifact_type", type_="check")
        batch_op.alter_column(
            "artifact_type",
            existing_type=sa.String(length=16),
            type_=sa.String(length=8),
        )
        batch_op.create_check_constraint(
            "ck_generated_artifact_type",
            "artifact_type IN ('xlsx', 'pdf', 'zip')",
        )
