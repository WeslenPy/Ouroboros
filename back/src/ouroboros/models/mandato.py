import enum
from datetime import date

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from ouroboros.models.base import Base, LineageMixin
from ouroboros.models.ente import Esfera, esfera_enum


class Cargo(enum.StrEnum):
    PRESIDENTE = "presidente"
    GOVERNADOR = "governador"
    PREFEITO = "prefeito"
    SENADOR = "senador"
    DEPUTADO_FEDERAL = "deputado_federal"
    DEPUTADO_ESTADUAL = "deputado_estadual"
    VEREADOR = "vereador"


class Mandato(LineageMixin, Base):
    """Período em que a pessoa exerceu (ou foi diplomada para) um cargo, segundo a casa/órgão."""

    __tablename__ = "mandato"

    id: Mapped[int] = mapped_column(primary_key=True)
    origem: Mapped[str] = mapped_column(String(20))
    id_externo: Mapped[str] = mapped_column(String(60))
    politico_id: Mapped[int] = mapped_column(ForeignKey("politico.id", ondelete="CASCADE"))
    cargo: Mapped[Cargo] = mapped_column(
        Enum(Cargo, name="cargo", values_callable=lambda e: [m.value for m in e])
    )
    esfera: Mapped[Esfera] = mapped_column(esfera_enum)
    ente_codigo_ibge: Mapped[int] = mapped_column(ForeignKey("ente.codigo_ibge"))
    uf: Mapped[str | None] = mapped_column(CHAR(2))
    # sigla única quando a pessoa não trocou de partido no período; senão None e ver `partidos`
    partido_sigla: Mapped[str | None] = mapped_column(String(30))
    partidos: Mapped[list[str]] = mapped_column(ARRAY(String(30)), default=list)
    legislatura: Mapped[int | None] = mapped_column(SmallInteger)
    condicao: Mapped[str | None] = mapped_column(String(40))
    inicio: Mapped[date | None] = mapped_column(Date)
    fim: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (
        Index("uq_mandato_origem_id", "origem", "id_externo", unique=True),
        Index("ix_mandato_politico", "politico_id", "inicio"),
        Index("ix_mandato_cargo_uf", "cargo", "uf"),
    )


class Candidatura(LineageMixin, Base):
    """Registro de candidatura no TSE (uma por SQ_CANDIDATO; guarda o último turno)."""

    __tablename__ = "candidatura"

    sq_candidato: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    politico_id: Mapped[int] = mapped_column(ForeignKey("politico.id", ondelete="CASCADE"))
    ano: Mapped[int] = mapped_column(SmallInteger)
    turno: Mapped[int] = mapped_column(SmallInteger)
    cargo: Mapped[str] = mapped_column(String(40))
    cargo_codigo: Mapped[int] = mapped_column(SmallInteger)
    uf: Mapped[str | None] = mapped_column(CHAR(2))
    ue_codigo_tse: Mapped[str] = mapped_column(String(10))
    ue_nome: Mapped[str] = mapped_column(String(120))
    numero_urna: Mapped[int | None] = mapped_column(Integer)
    nome_urna: Mapped[str] = mapped_column(String(200))
    partido_numero: Mapped[int | None] = mapped_column(SmallInteger)
    partido_sigla: Mapped[str | None] = mapped_column(String(30))
    situacao_candidatura: Mapped[str | None] = mapped_column(String(60))
    situacao_turno: Mapped[str | None] = mapped_column(String(60))
    # motivo_cassacao do TSE: por que a candidatura foi indeferida/cassada
    motivos_situacao: Mapped[list[str]] = mapped_column(
        ARRAY(String(120)), default=list, server_default="{}"
    )
    eleito: Mapped[bool] = mapped_column(Boolean)

    __table_args__ = (
        Index("ix_candidatura_politico", "politico_id", "ano"),
        Index("ix_candidatura_ano_cargo_uf", "ano", "cargo_codigo", "uf"),
    )
