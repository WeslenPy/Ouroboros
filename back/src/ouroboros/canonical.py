"""Linhas canônicas que os conectores produzem e os loaders gravam.

Cada conector converte o formato bruto da sua fonte nestes modelos; o resto do sistema
(loaders, resolução de entidades, API) só conhece o formato canônico.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ouroboros.models.ente import Esfera
from ouroboros.models.mandato import Cargo


class Lineage(BaseModel):
    model_config = ConfigDict(frozen=True)

    fonte: str
    fonte_url: str
    raw_hash: str


class EnteRow(Lineage):
    codigo_ibge: int
    nome: str
    nome_normalizado: str
    esfera: Esfera
    uf: str | None
    uf_codigo: int | None
    regiao: str | None


class PessoaRow(Lineage):
    """Pessoa como uma fonte a descreve. A resolução decide a qual `politico` ela pertence."""

    origem: str
    id_externo: str
    nome: str
    nome_civil: str | None = None
    data_nascimento: date | None = None
    genero: str | None = None
    cpf_hmac: str | None = None
    foto_url: str | None = None


class CpfPessoaRow(BaseModel):
    """CPF (já em HMAC) visto numa fonte secundária (ex.: CEAP traz o CPF do deputado)."""

    model_config = ConfigDict(frozen=True)

    origem: str
    id_externo: str
    cpf_hmac: str


class MandatoRow(Lineage):
    origem: str
    id_externo: str
    pessoa_id_externo: str
    cargo: Cargo
    esfera: Esfera
    ente_codigo_ibge: int
    uf: str | None
    partidos: list[str]
    legislatura: int | None = None
    condicao: str | None = None
    inicio: date | None = None
    fim: date | None = None


class PartidoRow(Lineage):
    numero_tse: int
    sigla: str
    nome: str


class CandidaturaRow(Lineage):
    sq_candidato: int
    pessoa_id_externo: str
    ano: int
    turno: int
    cargo: str
    cargo_codigo: int
    uf: str | None
    ue_codigo_tse: str
    ue_nome: str
    numero_urna: int | None
    nome_urna: str
    partido_numero: int | None
    partido_sigla: str | None
    situacao_candidatura: str | None
    situacao_turno: str | None
    eleito: bool


class DespesaRow(Lineage):
    verba: str
    parlamentar_origem: str
    parlamentar_id_externo: str | None
    parlamentar_nome: str
    parlamentar_nome_normalizado: str
    uf: str | None
    partido_sigla: str | None
    ano: int
    mes: int
    data_emissao: date | None
    categoria: str
    subcategoria: str | None
    fornecedor_nome: str | None
    fornecedor_documento: str | None
    fornecedor_tipo: str | None
    documento_numero: str | None
    documento_url: str | None
    documento_id_fonte: str | None
    valor_documento: Decimal | None
    valor_glosa: Decimal | None
    valor_liquido: Decimal
