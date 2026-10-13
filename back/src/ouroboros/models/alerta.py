from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ouroboros.models.base import Base


class Alerta(Base):
    """Indício de irregularidade apontado por um detector (ver `analises/detectores.py`).

    Indício não é acusação: cada alerta diz o que foi medido (`evidencias`) e como (`detector`),
    com links para os documentos oficiais. A tabela é recalculada inteira a cada execução do
    job `analises`; `chave` é estável entre execuções (mesmo achado, mesma chave).
    """

    __tablename__ = "alerta"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chave: Mapped[str] = mapped_column(String(300), unique=True)
    detector: Mapped[str] = mapped_column(String(40))
    # alta, media, baixa (derivada de `score`)
    severidade: Mapped[str] = mapped_column(String(10))
    # 0-100: força do indício dentro do detector
    score: Mapped[float] = mapped_column(Float)
    # 0-1: confiança do detector (quanto um achado dele pesa no risco do político)
    peso: Mapped[float] = mapped_column(Float)
    politico_id: Mapped[int | None] = mapped_column(ForeignKey("politico.id", ondelete="CASCADE"))
    ano_inicio: Mapped[int | None] = mapped_column(SmallInteger)
    ano_fim: Mapped[int | None] = mapped_column(SmallInteger)
    # CNPJ (ou CPF mascarado) da empresa/entidade envolvida
    entidade_documento: Mapped[str | None] = mapped_column(String(20))
    entidade_nome: Mapped[str | None] = mapped_column(Text)
    valor: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    titulo: Mapped[str] = mapped_column(Text)
    descricao: Mapped[str] = mapped_column(Text)
    evidencias: Mapped[dict] = mapped_column(JSONB)
    gerado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_alerta_score", "score", "id"),
        Index("ix_alerta_politico", "politico_id"),
        Index("ix_alerta_detector", "detector"),
        Index("ix_alerta_entidade", "entidade_documento"),
    )
