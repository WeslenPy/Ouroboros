"""alertas

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-13 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alerta",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("chave", sa.String(length=300), nullable=False),
        sa.Column("detector", sa.String(length=40), nullable=False),
        sa.Column("severidade", sa.String(length=10), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("peso", sa.Float(), nullable=False),
        sa.Column("politico_id", sa.Integer(), nullable=True),
        sa.Column("ano_inicio", sa.SmallInteger(), nullable=True),
        sa.Column("ano_fim", sa.SmallInteger(), nullable=True),
        sa.Column("entidade_documento", sa.String(length=20), nullable=True),
        sa.Column("entidade_nome", sa.Text(), nullable=True),
        sa.Column("valor", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("titulo", sa.Text(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("evidencias", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "gerado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["politico_id"],
            ["politico.id"],
            name=op.f("fk_alerta_politico_id_politico"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alerta")),
        sa.UniqueConstraint("chave", name=op.f("uq_alerta_chave")),
    )
    op.create_index("ix_alerta_score", "alerta", ["score", "id"])
    op.create_index("ix_alerta_politico", "alerta", ["politico_id"])
    op.create_index("ix_alerta_detector", "alerta", ["detector"])
    op.create_index("ix_alerta_entidade", "alerta", ["entidade_documento"])


def downgrade() -> None:
    op.drop_index("ix_alerta_entidade", table_name="alerta")
    op.drop_index("ix_alerta_detector", table_name="alerta")
    op.drop_index("ix_alerta_politico", table_name="alerta")
    op.drop_index("ix_alerta_score", table_name="alerta")
    op.drop_table("alerta")
