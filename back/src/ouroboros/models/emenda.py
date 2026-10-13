from datetime import date
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY
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


class EmendaConvenio(LineageMixin, Base):
    """Convênio firmado com recurso de emenda: quem executa (convenente) e o objeto (o que vai
    ser feito). Fonte não traz CNPJ do convenente; o autor vem da emenda (`politico_id`)."""

    __tablename__ = "emenda_convenio"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    emenda_codigo: Mapped[str] = mapped_column(String(20))
    # ano da emenda (4 primeiros dígitos do código)
    ano: Mapped[int] = mapped_column(SmallInteger)
    tipo: Mapped[str | None] = mapped_column(String(120))
    politico_id: Mapped[int | None] = mapped_column(ForeignKey("politico.id", ondelete="SET NULL"))
    funcao: Mapped[str | None] = mapped_column(String(120))
    subfuncao: Mapped[str | None] = mapped_column(String(200))
    localidade: Mapped[str | None] = mapped_column(String(200))
    data_publicacao: Mapped[date | None] = mapped_column(Date)
    convenente: Mapped[str | None] = mapped_column(Text)
    objeto: Mapped[str | None] = mapped_column(Text)
    numero: Mapped[str | None] = mapped_column(String(20))
    valor: Mapped[Decimal] = mapped_column(Numeric(16, 2))

    __table_args__ = (
        Index("ix_emenda_convenio_ano", "ano"),
        Index("ix_emenda_convenio_emenda", "emenda_codigo"),
        Index("ix_emenda_convenio_politico_ano", "politico_id", "ano"),
    )


class TransferenciaEspecial(LineageMixin, Base):
    """Transferência especial ("emenda Pix", EC 105/2019): plano de ação no Transferegov.

    O dinheiro vai direto ao caixa de estado/município; o plano diz quem recebe, quanto e para
    quais áreas. `emenda_codigo` é o mesmo código do Portal da Transparência (tabela emenda).
    """

    __tablename__ = "transferencia_especial"

    # id_plano_acao da fonte
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    codigo: Mapped[str] = mapped_column(String(20))
    ano: Mapped[int] = mapped_column(SmallInteger)
    situacao: Mapped[str | None] = mapped_column(String(60))
    emenda_codigo: Mapped[str | None] = mapped_column(String(20))
    parlamentar_codigo: Mapped[str | None] = mapped_column(String(20))
    parlamentar_nome: Mapped[str] = mapped_column(String(200))
    parlamentar_nome_normalizado: Mapped[str] = mapped_column(String(200))
    politico_id: Mapped[int | None] = mapped_column(ForeignKey("politico.id", ondelete="SET NULL"))
    beneficiario_cnpj: Mapped[str | None] = mapped_column(String(14))
    beneficiario_nome: Mapped[str] = mapped_column(Text)
    uf: Mapped[str | None] = mapped_column(String(2))
    # ligado por nome do beneficiário ("MUNICIPIO DE X") contra ente; nulo para estados
    municipio_codigo_ibge: Mapped[int | None] = mapped_column(Integer)
    areas: Mapped[str | None] = mapped_column(Text)
    funcao: Mapped[str | None] = mapped_column(String(120))
    motivo_impedimento: Mapped[str | None] = mapped_column(Text)
    valor_custeio: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    valor_investimento: Mapped[Decimal] = mapped_column(Numeric(16, 2))

    __table_args__ = (
        Index("ix_transferencia_especial_ano", "ano"),
        Index("ix_transferencia_especial_politico_ano", "politico_id", "ano"),
        Index("ix_transferencia_especial_emenda", "emenda_codigo"),
        Index("ix_transferencia_especial_beneficiario", "beneficiario_cnpj"),
        Index("ix_transferencia_especial_municipio", "municipio_codigo_ibge"),
        Index("ix_transferencia_especial_autor", "parlamentar_nome_normalizado"),
    )


class TransferenciaEspecialExecutor(LineageMixin, Base):
    """Quem executa o plano (a própria prefeitura ou outro órgão) e o objeto: o que será feito."""

    __tablename__ = "transferencia_especial_executor"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    plano_id: Mapped[int] = mapped_column(BigInteger)
    cnpj: Mapped[str | None] = mapped_column(String(14))
    nome: Mapped[str] = mapped_column(Text)
    objeto: Mapped[str | None] = mapped_column(Text)
    areas: Mapped[list[str]] = mapped_column(ARRAY(String))
    valor_custeio: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    valor_investimento: Mapped[Decimal] = mapped_column(Numeric(16, 2))

    __table_args__ = (
        Index("ix_transferencia_especial_executor_plano", "plano_id"),
        Index("ix_transferencia_especial_executor_cnpj", "cnpj"),
    )


class TransferenciaEspecialMeta(LineageMixin, Base):
    """Meta física do executor (ex.: "pavimentar 2 km", "2 shows"), com o valor da emenda."""

    __tablename__ = "transferencia_especial_meta"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    executor_id: Mapped[int] = mapped_column(BigInteger)
    sequencial: Mapped[int | None] = mapped_column(SmallInteger)
    nome: Mapped[str | None] = mapped_column(Text)
    descricao: Mapped[str | None] = mapped_column(Text)
    unidade: Mapped[str | None] = mapped_column(String(40))
    quantidade: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    meses: Mapped[int | None] = mapped_column(SmallInteger)
    valor_custeio: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    valor_investimento: Mapped[Decimal] = mapped_column(Numeric(16, 2))

    __table_args__ = (Index("ix_transferencia_especial_meta_executor", "executor_id"),)


class TransferenciaEspecialEmpenho(LineageMixin, Base):
    """Empenho (reserva do dinheiro no orçamento) de um plano de ação."""

    __tablename__ = "transferencia_especial_empenho"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    plano_id: Mapped[int | None] = mapped_column(BigInteger)
    numero: Mapped[str | None] = mapped_column(String(20))
    situacao: Mapped[str | None] = mapped_column(String(60))
    data_emissao: Mapped[date | None] = mapped_column(Date)
    valor: Mapped[Decimal] = mapped_column(Numeric(16, 2))

    __table_args__ = (Index("ix_transferencia_especial_empenho_plano", "plano_id"),)


class TransferenciaEspecialPagamento(LineageMixin, Base):
    """Documento hábil (TF): a transferência efetiva do dinheiro ao beneficiário."""

    __tablename__ = "transferencia_especial_pagamento"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    empenho_id: Mapped[int | None] = mapped_column(BigInteger)
    plano_id: Mapped[int | None] = mapped_column(BigInteger)
    numero: Mapped[str | None] = mapped_column(String(20))
    situacao: Mapped[str | None] = mapped_column(String(60))
    data_emissao: Mapped[date | None] = mapped_column(Date)
    valor: Mapped[Decimal] = mapped_column(Numeric(16, 2))

    __table_args__ = (Index("ix_transferencia_especial_pagamento_plano", "plano_id"),)
