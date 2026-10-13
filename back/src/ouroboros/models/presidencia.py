from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, Index, Numeric, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ouroboros.models.base import Base, LineageMixin


class GastoPresidencia(LineageMixin, Base):
    """Lançamento do cartão de pagamento (CPGF) da Presidência da República.

    Não guarda político: o presidente responsável é quem exercia o cargo na data (ou no mês do
    extrato, quando a data é sigilosa), cruzado em consulta com `mandato` de presidente.
    Fontes não têm chave por linha: carga substitui a partição (fonte, anos) inteira.
    """

    __tablename__ = "gasto_presidencia"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    data: Mapped[date | None] = mapped_column(Date)
    ano: Mapped[int] = mapped_column(SmallInteger)
    mes: Mapped[int] = mapped_column(SmallInteger)
    unidade_gestora: Mapped[str | None] = mapped_column(String(120))
    # CPF do servidor portador do cartão, mascarado pela fonte
    portador: Mapped[str | None] = mapped_column(String(20))
    # CNPJ completo ou CPF mascarado; nulo quando a fonte perdeu o número
    favorecido_documento: Mapped[str | None] = mapped_column(String(20))
    favorecido_nome: Mapped[str | None] = mapped_column(Text)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    # credito (compra) ou saque (dinheiro vivo)
    tipo: Mapped[str] = mapped_column(String(10))
    # subelemento de despesa (hospedagem, alimentação...); só na planilha 2003-2022
    categoria: Mapped[str | None] = mapped_column(Text)
    transacao: Mapped[str | None] = mapped_column(Text)
    # 2003-2022: era classificado (tem CDIC). 2023+: ainda sigiloso no Portal.
    sigiloso: Mapped[bool] = mapped_column(Boolean)
    classificacao: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_gasto_presidencia_data", "data"),
        Index("ix_gasto_presidencia_fonte_ano", "fonte", "ano"),
        Index("ix_gasto_presidencia_favorecido", "favorecido_documento"),
    )
