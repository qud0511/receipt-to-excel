"""Phase 8.7 — baseline EMA 컬럼.

신규: user.baseline_s_per_tx, upload_session.counted_in_baseline,
upload_session.baseline_ref_s_per_tx. CLAUDE.md: upgrade+downgrade,
SQLite batch_alter_table.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_phase8_baseline_columns"
down_revision = "0003_phase8_artifact_kind_split"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("baseline_s_per_tx", sa.Float(), nullable=True))
    with op.batch_alter_table("upload_session") as batch_op:
        batch_op.add_column(
            sa.Column(
                "counted_in_baseline",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(sa.Column("baseline_ref_s_per_tx", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("upload_session") as batch_op:
        batch_op.drop_column("baseline_ref_s_per_tx")
        batch_op.drop_column("counted_in_baseline")
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("baseline_s_per_tx")
