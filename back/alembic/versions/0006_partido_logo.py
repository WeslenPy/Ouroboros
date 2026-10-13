"""partido_logo

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-13 15:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "partido_logo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("partido_id", sa.Integer(), nullable=False),
        sa.Column("origem", sa.String(length=20), nullable=False),
        sa.Column("id_externo", sa.String(length=40), nullable=True),
        sa.Column("url_origem", sa.Text(), nullable=False),
        sa.Column(
            "obtida_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("sha256", sa.CHAR(length=64), nullable=True),
        sa.Column("extensao", sa.String(length=5), nullable=True),
        sa.Column("content_type", sa.String(length=20), nullable=True),
        sa.Column("tamanho_bytes", sa.Integer(), nullable=True),
        sa.Column("largura", sa.SmallInteger(), nullable=True),
        sa.Column("altura", sa.SmallInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["partido_id"],
            ["partido.id"],
            name=op.f("fk_partido_logo_partido_id_partido"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partido_logo")),
        sa.UniqueConstraint("partido_id", "origem", name="uq_partido_logo_origem"),
    )
    op.add_column("partido", sa.Column("logo_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_partido_logo_id_partido_logo"),
        "partido",
        "partido_logo",
        ["logo_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_partido_logo_id_partido_logo"), "partido", type_="foreignkey")
    op.drop_column("partido", "logo_id")
    op.drop_table("partido_logo")
