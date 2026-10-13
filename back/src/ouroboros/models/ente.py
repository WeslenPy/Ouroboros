import enum

from sqlalchemy import CHAR, Enum, Index, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from ouroboros.models.base import Base, LineageMixin


class Esfera(enum.StrEnum):
    FEDERAL = "federal"
    ESTADUAL = "estadual"
    MUNICIPAL = "municipal"


esfera_enum = Enum(Esfera, name="esfera", values_callable=lambda e: [m.value for m in e])

# Código usado pelo SICONFI/Tesouro para a União; estados e municípios usam o código IBGE.
CODIGO_UNIAO = 1


class Ente(LineageMixin, Base):
    """Ente federativo: União, 27 UFs e municípios. Chave = código IBGE."""

    __tablename__ = "ente"

    codigo_ibge: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    nome: Mapped[str] = mapped_column(String(120))
    nome_normalizado: Mapped[str] = mapped_column(String(120))
    esfera: Mapped[Esfera] = mapped_column(esfera_enum)
    uf: Mapped[str | None] = mapped_column(CHAR(2))
    uf_codigo: Mapped[int | None] = mapped_column(SmallInteger)
    regiao: Mapped[str | None] = mapped_column(String(20))

    __table_args__ = (
        Index("ix_ente_esfera_uf", "esfera", "uf"),
        Index(
            "ix_ente_nome_trgm",
            "nome_normalizado",
            postgresql_using="gin",
            postgresql_ops={"nome_normalizado": "gin_trgm_ops"},
        ),
    )
