"""fundacao: extensões, ente, partido, fonte_execucao

Revision ID: 0001
Revises:
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _lineage() -> list[sa.Column]:
    return [
        sa.Column("fonte", sa.String(40), nullable=False),
        sa.Column("fonte_url", sa.Text(), nullable=False),
        sa.Column("raw_hash", sa.String(64), nullable=False),
        sa.Column(
            "ingerido_em",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

    esfera = postgresql.ENUM("federal", "estadual", "municipal", name="esfera")
    status = postgresql.ENUM("rodando", "sucesso", "falha", name="status_execucao")

    op.create_table(
        "ente",
        sa.Column("codigo_ibge", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("nome_normalizado", sa.String(120), nullable=False),
        sa.Column("esfera", esfera, nullable=False),
        sa.Column("uf", sa.CHAR(2), nullable=True),
        sa.Column("uf_codigo", sa.SmallInteger(), nullable=True),
        sa.Column("regiao", sa.String(20), nullable=True),
        *_lineage(),
        sa.PrimaryKeyConstraint("codigo_ibge", name="pk_ente"),
    )
    op.create_index("ix_ente_esfera_uf", "ente", ["esfera", "uf"])
    op.create_index(
        "ix_ente_nome_trgm",
        "ente",
        ["nome_normalizado"],
        postgresql_using="gin",
        postgresql_ops={"nome_normalizado": "gin_trgm_ops"},
    )

    op.create_table(
        "partido",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sigla", sa.String(30), nullable=False),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("numero_tse", sa.SmallInteger(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        *_lineage(),
        sa.PrimaryKeyConstraint("id", name="pk_partido"),
        sa.UniqueConstraint("numero_tse", name="uq_partido_numero_tse"),
    )
    op.create_index("ix_partido_sigla", "partido", ["sigla"])

    op.create_table(
        "fonte_execucao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fonte", sa.String(40), nullable=False),
        sa.Column("recurso", sa.String(60), nullable=False),
        sa.Column("particao", sa.String(40), nullable=False),
        sa.Column("status", status, nullable=False),
        sa.Column("registros", sa.Integer(), nullable=False),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.Column(
            "iniciado_em",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finalizado_em", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_fonte_execucao"),
    )
    op.create_index(
        "ix_fonte_execucao_fonte_recurso",
        "fonte_execucao",
        ["fonte", "recurso", "iniciado_em"],
    )


def downgrade() -> None:
    op.drop_table("fonte_execucao")
    op.drop_table("partido")
    op.drop_table("ente")
    op.execute("DROP TYPE IF EXISTS status_execucao")
    op.execute("DROP TYPE IF EXISTS esfera")
