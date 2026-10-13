"""candidatura motivos_situacao

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-13 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "candidatura",
        sa.Column(
            "motivos_situacao",
            postgresql.ARRAY(sa.String(length=120)),
            server_default="{}",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("candidatura", "motivos_situacao")
