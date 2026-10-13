from datetime import date, datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from ouroboros.models.base import Base


class Politico(Base):
    """Pessoa. Agrega identidades de várias fontes (Câmara, Senado, TSE...) numa linha só."""

    __tablename__ = "politico"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    nome_normalizado: Mapped[str] = mapped_column(String(200))
    # fonte que definiu `nome` (nome parlamentar tem prioridade sobre nome de urna)
    nome_origem: Mapped[str] = mapped_column(String(20))
    nome_civil: Mapped[str | None] = mapped_column(String(200))
    nome_civil_normalizado: Mapped[str | None] = mapped_column(String(200))
    data_nascimento: Mapped[date | None] = mapped_column(Date)
    genero: Mapped[str | None] = mapped_column(CHAR(1))
    cpf_hmac: Mapped[str | None] = mapped_column(CHAR(64), unique=True)
    foto_url: Mapped[str | None] = mapped_column(Text)  # URL na fonte (informativo)
    # foto principal escolhida entre politico_foto (ver pipelines/fotos.py)
    foto_id: Mapped[int | None] = mapped_column(
        ForeignKey("politico_foto.id", ondelete="SET NULL", use_alter=True)
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_politico_civil_nascimento", "nome_civil_normalizado", "data_nascimento"),
        Index(
            "ix_politico_nome_trgm",
            "nome_normalizado",
            postgresql_using="gin",
            postgresql_ops={"nome_normalizado": "gin_trgm_ops"},
        ),
        Index(
            "ix_politico_nome_civil_trgm",
            "nome_civil_normalizado",
            postgresql_using="gin",
            postgresql_ops={"nome_civil_normalizado": "gin_trgm_ops"},
        ),
    )


class PoliticoIdentificador(Base):
    """ID de uma pessoa numa fonte (id Câmara, código Senado, SQ_CANDIDATO TSE) -> politico."""

    __tablename__ = "politico_identificador"

    origem: Mapped[str] = mapped_column(String(20), primary_key=True)
    id_externo: Mapped[str] = mapped_column(String(40), primary_key=True)
    politico_id: Mapped[int] = mapped_column(ForeignKey("politico.id", ondelete="CASCADE"))
    # como a ligação foi feita: origem (criou o político), cpf, nome_nascimento
    metodo: Mapped[str] = mapped_column(String(20))
    nome_na_fonte: Mapped[str] = mapped_column(String(200))
    nome_na_fonte_normalizado: Mapped[str] = mapped_column(String(200))
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_politico_identificador_politico_id", "politico_id"),
        Index("ix_politico_identificador_nome", "origem", "nome_na_fonte_normalizado"),
    )


class MatchPendente(Base):
    """Ligações que a resolução automática não decidiu sozinha. Revisão manual."""

    __tablename__ = "match_pendente"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    origem: Mapped[str] = mapped_column(String(20))
    id_externo: Mapped[str] = mapped_column(String(40))
    motivo: Mapped[str] = mapped_column(String(40))
    politico_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger))
    resolvido: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("origem", "id_externo", "motivo", name="uq_match_pendente"),)
