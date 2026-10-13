"""Convênios e contratos de repasse (Transferegov / antigo Siconv): onde a emenda vira obra.

O dinheiro da União sai da emenda (tabela `emenda`), é empenhado para um convênio com um
estado, município ou entidade (o convenente), cai numa conta específica (desembolso) e é gasto
com fornecedores contratados por licitação. Aqui fica cada passo desse caminho, mais o que a
fonte diz da obra física: endereço, coordenadas, início, medições e percentual executado.

Ligações (todas por chave natural, sem FK, porque cada fonte carrega no seu ritmo):

- convenio_emenda.emenda_codigo = emenda.codigo (e emenda_convenio.numero = convenio.numero)
- convenio.municipio_codigo_ibge = ente.codigo_ibge
- convenio.proponente_cnpj = emenda_favorecido.favorecido_documento (prefeitura que recebeu)
- convenio_contrato.fornecedor_documento / convenio_fornecedor.documento =
  despesa_gabinete.fornecedor_documento (empreiteira que também vende para gabinetes)

`ano` em todas as tabelas = ano da proposta: é a partição de carga.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ouroboros.models.base import Base, LineageMixin


class Convenio(LineageMixin, Base):
    """Convênio (ou contrato de repasse) com dados da proposta e da obra."""

    __tablename__ = "convenio"

    # NR_CONVENIO: o mesmo número que o Portal da Transparência mostra em "Número Convênio"
    numero: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    proposta_id: Mapped[int] = mapped_column(Integer)
    ano: Mapped[int] = mapped_column(SmallInteger)
    situacao: Mapped[str | None] = mapped_column(String(80))
    subsituacao: Mapped[str | None] = mapped_column(String(80))
    modalidade: Mapped[str | None] = mapped_column(String(60))
    orgao_superior: Mapped[str | None] = mapped_column(String(200))
    orgao: Mapped[str | None] = mapped_column(String(200))
    proponente_cnpj: Mapped[str | None] = mapped_column(String(14))
    proponente_nome: Mapped[str | None] = mapped_column(Text)
    natureza_juridica: Mapped[str | None] = mapped_column(String(80))
    uf: Mapped[str | None] = mapped_column(String(2))
    # sem FK para ente (mesmo motivo de emenda.municipio_codigo_ibge)
    municipio_codigo_ibge: Mapped[int | None] = mapped_column(Integer)
    municipio_nome: Mapped[str | None] = mapped_column(String(120))
    objeto: Mapped[str | None] = mapped_column(Text)
    data_proposta: Mapped[date | None] = mapped_column(Date)
    data_assinatura: Mapped[date | None] = mapped_column(Date)
    data_publicacao: Mapped[date | None] = mapped_column(Date)
    inicio_vigencia: Mapped[date | None] = mapped_column(Date)
    fim_vigencia: Mapped[date | None] = mapped_column(Date)
    fim_vigencia_original: Mapped[date | None] = mapped_column(Date)
    limite_prestacao_contas: Mapped[date | None] = mapped_column(Date)
    prorrogacoes: Mapped[int | None] = mapped_column(SmallInteger)
    aditivos: Mapped[int | None] = mapped_column(SmallInteger)
    valor_global: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    valor_repasse: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    valor_contrapartida: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    valor_empenhado: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    valor_desembolsado: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    valor_saldo_conta: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    # obra: só preenchido quando a fonte acompanha a execução física
    obra_id: Mapped[str | None] = mapped_column(String(20))  # id único no Obrasgov (CIPI)
    obra_nome: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    endereco: Mapped[str | None] = mapped_column(Text)
    cep: Mapped[str | None] = mapped_column(String(9))
    percentual_execucao: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    valor_executado: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    inicio_obra: Mapped[date | None] = mapped_column(Date)
    ultima_medicao: Mapped[date | None] = mapped_column(Date)
    dias_sem_medicao: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        Index("ix_convenio_ano", "ano"),
        Index("ix_convenio_municipio", "municipio_codigo_ibge"),
        Index("ix_convenio_uf", "uf"),
        Index("ix_convenio_proponente", "proponente_cnpj"),
        Index("ix_convenio_situacao", "situacao"),
        Index("ix_convenio_obra", "obra_id"),
    )


class ConvenioEmenda(LineageMixin, Base):
    """Emenda que financia o convênio (um convênio pode juntar várias emendas)."""

    __tablename__ = "convenio_emenda"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    convenio_numero: Mapped[int] = mapped_column(Integer)
    ano: Mapped[int] = mapped_column(SmallInteger)
    # ano do orçamento + NR_EMENDA: mesmo formato de emenda.codigo (Portal da Transparência)
    emenda_codigo: Mapped[str | None] = mapped_column(String(20))
    emenda_numero: Mapped[str | None] = mapped_column(String(20))
    tipo: Mapped[str | None] = mapped_column(String(40))
    parlamentar_nome: Mapped[str] = mapped_column(String(200))
    parlamentar_nome_normalizado: Mapped[str] = mapped_column(String(200))
    politico_id: Mapped[int | None] = mapped_column(ForeignKey("politico.id", ondelete="SET NULL"))
    impositiva: Mapped[bool | None] = mapped_column(Boolean)
    valor_repasse: Mapped[Decimal] = mapped_column(Numeric(16, 2))

    __table_args__ = (
        Index("ix_convenio_emenda_ano", "ano"),
        Index("ix_convenio_emenda_convenio", "convenio_numero"),
        Index("ix_convenio_emenda_emenda", "emenda_codigo"),
        Index("ix_convenio_emenda_politico", "politico_id"),
        Index("ix_convenio_emenda_autor", "parlamentar_nome_normalizado"),
    )


class ConvenioMeta(LineageMixin, Base):
    """Meta do cronograma físico: o que será feito, onde e quando (plano, não execução)."""

    __tablename__ = "convenio_meta"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    convenio_numero: Mapped[int] = mapped_column(Integer)
    ano: Mapped[int] = mapped_column(SmallInteger)
    numero: Mapped[int | None] = mapped_column(SmallInteger)
    descricao: Mapped[str | None] = mapped_column(Text)
    data_inicio: Mapped[date | None] = mapped_column(Date)
    data_fim: Mapped[date | None] = mapped_column(Date)
    uf: Mapped[str | None] = mapped_column(String(2))
    municipio_nome: Mapped[str | None] = mapped_column(String(120))
    endereco: Mapped[str | None] = mapped_column(Text)
    cep: Mapped[str | None] = mapped_column(String(9))
    quantidade: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    unidade: Mapped[str | None] = mapped_column(String(60))
    valor: Mapped[Decimal] = mapped_column(Numeric(16, 2))

    __table_args__ = (
        Index("ix_convenio_meta_ano", "ano"),
        Index("ix_convenio_meta_convenio", "convenio_numero"),
    )


class ConvenioDesembolso(LineageMixin, Base):
    """Liberação de dinheiro da União para a conta do convênio."""

    __tablename__ = "convenio_desembolso"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    convenio_numero: Mapped[int] = mapped_column(Integer)
    ano: Mapped[int] = mapped_column(SmallInteger)
    data: Mapped[date | None] = mapped_column(Date)
    documento: Mapped[str | None] = mapped_column(String(20))  # ordem bancária no SIAFI
    valor: Mapped[Decimal] = mapped_column(Numeric(16, 2))

    __table_args__ = (
        Index("ix_convenio_desembolso_ano", "ano"),
        Index("ix_convenio_desembolso_convenio", "convenio_numero"),
    )


class ConvenioContrato(LineageMixin, Base):
    """Contrato que o convenente assinou com o vencedor da licitação (a empreiteira)."""

    __tablename__ = "convenio_contrato"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    convenio_numero: Mapped[int] = mapped_column(Integer)
    ano: Mapped[int] = mapped_column(SmallInteger)
    numero: Mapped[str | None] = mapped_column(String(60))
    modalidade_licitacao: Mapped[str | None] = mapped_column(String(80))
    objeto: Mapped[str | None] = mapped_column(Text)
    tipo_aquisicao: Mapped[str | None] = mapped_column(String(60))
    # CNPJ completo; CPF já vem mascarado pela fonte
    fornecedor_documento: Mapped[str | None] = mapped_column(String(20))
    fornecedor_nome: Mapped[str | None] = mapped_column(Text)
    data_assinatura: Mapped[date | None] = mapped_column(Date)
    inicio_vigencia: Mapped[date | None] = mapped_column(Date)
    fim_vigencia: Mapped[date | None] = mapped_column(Date)
    valor: Mapped[Decimal] = mapped_column(Numeric(16, 2))

    __table_args__ = (
        Index("ix_convenio_contrato_ano", "ano"),
        Index("ix_convenio_contrato_convenio", "convenio_numero"),
        Index("ix_convenio_contrato_fornecedor", "fornecedor_documento"),
    )


class ConvenioFornecedor(LineageMixin, Base):
    """Pagamentos da conta do convênio somados por fornecedor (o que de fato foi gasto).

    Pessoas físicas (CPF mascarado) somam numa linha só por convênio, com documento nulo.
    """

    __tablename__ = "convenio_fornecedor"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    convenio_numero: Mapped[int] = mapped_column(Integer)
    documento: Mapped[str | None] = mapped_column(String(14))
    nome: Mapped[str] = mapped_column(Text)
    pagamentos: Mapped[int] = mapped_column(Integer)
    primeiro_pagamento: Mapped[date | None] = mapped_column(Date)
    ultimo_pagamento: Mapped[date | None] = mapped_column(Date)
    valor: Mapped[Decimal] = mapped_column(Numeric(16, 2))

    __table_args__ = (
        Index("ix_convenio_fornecedor_convenio", "convenio_numero"),
        Index("ix_convenio_fornecedor_documento", "documento"),
    )
