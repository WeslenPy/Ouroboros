"""gastos da presidência (cartão de pagamento)

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-13 16:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gasto_presidencia",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("data", sa.Date(), nullable=True),
        sa.Column("ano", sa.SmallInteger(), nullable=False),
        sa.Column("mes", sa.SmallInteger(), nullable=False),
        sa.Column("unidade_gestora", sa.String(length=120), nullable=True),
        sa.Column("portador", sa.String(length=20), nullable=True),
        sa.Column("favorecido_documento", sa.String(length=20), nullable=True),
        sa.Column("favorecido_nome", sa.Text(), nullable=True),
        sa.Column("valor", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("tipo", sa.String(length=10), nullable=False),
        sa.Column("categoria", sa.Text(), nullable=True),
        sa.Column("transacao", sa.Text(), nullable=True),
        sa.Column("sigiloso", sa.Boolean(), nullable=False),
        sa.Column("classificacao", sa.Text(), nullable=True),
        sa.Column("fonte", sa.String(length=40), nullable=False),
        sa.Column("fonte_url", sa.Text(), nullable=False),
        sa.Column("raw_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "ingerido_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gasto_presidencia")),
    )
    op.create_index("ix_gasto_presidencia_data", "gasto_presidencia", ["data"])
    op.create_index("ix_gasto_presidencia_fonte_ano", "gasto_presidencia", ["fonte", "ano"])
    op.create_index(
        "ix_gasto_presidencia_favorecido", "gasto_presidencia", ["favorecido_documento"]
    )


def downgrade() -> None:
    op.drop_index("ix_gasto_presidencia_favorecido", table_name="gasto_presidencia")
    op.drop_index("ix_gasto_presidencia_fonte_ano", table_name="gasto_presidencia")
    op.drop_index("ix_gasto_presidencia_data", table_name="gasto_presidencia")
    op.drop_table("gasto_presidencia")
