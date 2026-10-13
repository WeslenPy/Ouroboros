import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ouroboros.models.base import Base


class StatusExecucao(enum.StrEnum):
    RODANDO = "rodando"
    SUCESSO = "sucesso"
    FALHA = "falha"


class FonteExecucao(Base):
    """Histórico de cada ingestão (fonte + partição). Alimenta GET /v1/fontes."""

    __tablename__ = "fonte_execucao"

    id: Mapped[int] = mapped_column(primary_key=True)
    fonte: Mapped[str] = mapped_column(String(40))
    recurso: Mapped[str] = mapped_column(String(60))
    particao: Mapped[str] = mapped_column(String(40))
    status: Mapped[StatusExecucao] = mapped_column(
        Enum(StatusExecucao, name="status_execucao", values_callable=lambda e: [m.value for m in e])
    )
    registros: Mapped[int] = mapped_column(Integer, default=0)
    erro: Mapped[str | None] = mapped_column(Text)
    iniciado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finalizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_fonte_execucao_fonte_recurso", "fonte", "recurso", "iniciado_em"),)
