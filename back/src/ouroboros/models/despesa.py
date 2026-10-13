from datetime import date
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ouroboros.models.base import Base, LineageMixin


class DespesaGabinete(LineageMixin, Base):
    """Gasto de cota/verba de gabinete (CEAP Câmara, CEAPS Senado; depois verbas estaduais).

    Fontes não têm chave única por linha: carga substitui a partição (fonte, ano) inteira.
    Valores negativos são estornos/compensações publicados pela própria fonte.
    """

    __tablename__ = "despesa_gabinete"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    verba: Mapped[str] = mapped_column(String(20))
    politico_id: Mapped[int | None] = mapped_column(ForeignKey("politico.id", ondelete="SET NULL"))
    # como a fonte identifica o parlamentar (usado para religar quando o político chega depois)
    parlamentar_origem: Mapped[str] = mapped_column(String(20))
    parlamentar_id_externo: Mapped[str | None] = mapped_column(String(40))
    parlamentar_nome: Mapped[str] = mapped_column(String(200))
    parlamentar_nome_normalizado: Mapped[str] = mapped_column(String(200))
    uf: Mapped[str | None] = mapped_column(String(2))
    partido_sigla: Mapped[str | None] = mapped_column(String(30))
    ano: Mapped[int] = mapped_column(SmallInteger)
    mes: Mapped[int] = mapped_column(SmallInteger)
    data_emissao: Mapped[date | None] = mapped_column(Date)
    categoria: Mapped[str] = mapped_column(String(300))
    subcategoria: Mapped[str | None] = mapped_column(Text)
    fornecedor_nome: Mapped[str | None] = mapped_column(Text)
    # CNPJ completo ou CPF mascarado (***.456.789-**)
    fornecedor_documento: Mapped[str | None] = mapped_column(String(20))
    fornecedor_tipo: Mapped[str | None] = mapped_column(String(2))
    documento_numero: Mapped[str | None] = mapped_column(Text)
    documento_url: Mapped[str | None] = mapped_column(Text)
    documento_id_fonte: Mapped[str | None] = mapped_column(String(40))
    valor_documento: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    valor_glosa: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    valor_liquido: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    __table_args__ = (
        Index("ix_despesa_fonte_ano", "fonte", "ano"),
        Index("ix_despesa_ano_id", "ano", "id"),
        Index("ix_despesa_politico_ano", "politico_id", "ano"),
        Index("ix_despesa_fornecedor", "fornecedor_documento"),
        Index("ix_despesa_ano_categoria", "ano", "categoria"),
    )
