from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, Numeric, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ouroboros.models.base import Base, LineageMixin


class Emenda(LineageMixin, Base):
    """Emenda parlamentar ao orçamento federal (Portal da Transparência / CGU).

    Uma linha por (emenda, localidade, ação orçamentária): a mesma emenda pode se dividir em
    vários destinos. Valores acumulados até a data do arquivo. Fonte não tem chave única por
    linha: carga substitui o ano inteiro.

    Autor vem só como código CGU + nome; `politico_id` é ligado por nome (ver relink_emendas).
    Emendas de bancada, comissão e relator têm autor coletivo e ficam sem político.
    """

    __tablename__ = "emenda"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20))
    ano: Mapped[int] = mapped_column(SmallInteger)
    tipo: Mapped[str] = mapped_column(String(120))
    numero: Mapped[str | None] = mapped_column(String(20))
    autor_codigo: Mapped[str | None] = mapped_column(String(20))
    autor_nome: Mapped[str] = mapped_column(String(200))
    autor_nome_normalizado: Mapped[str] = mapped_column(String(200))
    politico_id: Mapped[int | None] = mapped_column(ForeignKey("politico.id", ondelete="SET NULL"))
    localidade: Mapped[str | None] = mapped_column(String(200))
    # sem FK para ente: a fonte usa códigos que podem não estar carregados (ex.: municípios novos)
    municipio_codigo_ibge: Mapped[int | None] = mapped_column(Integer)
    municipio_nome: Mapped[str | None] = mapped_column(String(120))
    uf: Mapped[str | None] = mapped_column(String(2))
    regiao: Mapped[str | None] = mapped_column(String(30))
    funcao: Mapped[str | None] = mapped_column(String(120))
    subfuncao: Mapped[str | None] = mapped_column(String(200))
    programa: Mapped[str | None] = mapped_column(Text)
    acao: Mapped[str | None] = mapped_column(Text)
    valor_empenhado: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    valor_liquidado: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    valor_pago: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    valor_rp_inscrito: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    valor_rp_cancelado: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    valor_rp_pago: Mapped[Decimal] = mapped_column(Numeric(16, 2))

    __table_args__ = (
        Index("ix_emenda_ano", "ano"),
        Index("ix_emenda_codigo", "codigo"),
        Index("ix_emenda_politico_ano", "politico_id", "ano"),
        Index("ix_emenda_municipio", "municipio_codigo_ibge"),
        Index("ix_emenda_autor", "autor_nome_normalizado"),
    )


class EmendaFavorecido(LineageMixin, Base):
    """Pagamento de emenda a um favorecido (prefeitura, fundo, ONG, empresa) num mês."""

    __tablename__ = "emenda_favorecido"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    emenda_codigo: Mapped[str] = mapped_column(String(20))
    ano: Mapped[int] = mapped_column(SmallInteger)
    mes: Mapped[int] = mapped_column(SmallInteger)
    tipo: Mapped[str] = mapped_column(String(120))
    autor_codigo: Mapped[str | None] = mapped_column(String(20))
    autor_nome: Mapped[str] = mapped_column(String(200))
    autor_nome_normalizado: Mapped[str] = mapped_column(String(200))
    politico_id: Mapped[int | None] = mapped_column(ForeignKey("politico.id", ondelete="SET NULL"))
    # CNPJ completo; CPF mascarado
    favorecido_documento: Mapped[str | None] = mapped_column(String(20))
    favorecido_nome: Mapped[str] = mapped_column(Text)
    favorecido_tipo: Mapped[str | None] = mapped_column(String(40))
    natureza_juridica: Mapped[str | None] = mapped_column(String(200))
    uf: Mapped[str | None] = mapped_column(String(2))
    municipio_nome: Mapped[str | None] = mapped_column(String(120))
    valor: Mapped[Decimal] = mapped_column(Numeric(16, 2))

    __table_args__ = (
        Index("ix_emenda_favorecido_ano", "ano"),
        Index("ix_emenda_favorecido_emenda", "emenda_codigo"),
        Index("ix_emenda_favorecido_politico_ano", "politico_id", "ano"),
        Index("ix_emenda_favorecido_documento", "favorecido_documento"),
        Index("ix_emenda_favorecido_autor", "autor_nome_normalizado"),
    )
