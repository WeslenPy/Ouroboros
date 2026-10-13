from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ouroboros.models.ente import Esfera
from ouroboros.models.fonte import StatusExecucao
from ouroboros.models.mandato import Cargo


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Origem(_Out):
    fonte: str
    fonte_url: str
    raw_hash: str
    ingerido_em: datetime


class EnteOut(_Out):
    codigo_ibge: int
    nome: str
    esfera: Esfera
    uf: str | None
    regiao: str | None


class EnteDetalhe(EnteOut):
    uf_codigo: int | None
    origem: Origem


class FonteStatus(_Out):
    fonte: str
    recurso: str
    particao: str
    status: StatusExecucao
    registros: int
    erro: str | None
    iniciado_em: datetime
    finalizado_em: datetime | None
    ultimo_sucesso_em: datetime | None


class Identificador(_Out):
    origem: str
    id_externo: str
    metodo: str = Field(description="Como a ligação foi feita: origem, cpf, nome_nascimento...")


class MandatoOut(_Out):
    cargo: Cargo
    esfera: Esfera
    uf: str | None
    partido_sigla: str | None = Field(description="Nulo se trocou de partido no período")
    partidos: list[str]
    legislatura: int | None
    condicao: str | None
    inicio: date | None
    fim: date | None
    origem: str


class FotoOut(_Out):
    id: int
    url: str = Field(description="Arquivo servido por esta API")
    origem: str
    ano: int | None
    largura: int
    altura: int
    url_origem: str = Field(description="Onde a foto foi obtida")

    @classmethod
    def de(cls, foto) -> "FotoOut":
        return cls(
            id=foto.id,
            url=f"/v1/fotos/{foto.id}",
            origem=foto.origem,
            ano=foto.ano,
            largura=foto.largura,
            altura=foto.altura,
            url_origem=foto.url_origem,
        )


class PoliticoResumo(_Out):
    id: int
    nome: str
    nome_civil: str | None
    foto: FotoOut | None = None
    ultimo_mandato: MandatoOut | None = None


class TotalAno(BaseModel):
    ano: int
    total: Decimal
    quantidade: int


class PoliticoDetalhe(PoliticoResumo):
    data_nascimento: date | None
    genero: str | None
    identificadores: list[Identificador]
    mandatos: list[MandatoOut]
    candidaturas: int
    gastos_gabinete_por_ano: list[TotalAno]


class CandidaturaOut(_Out):
    sq_candidato: int
    politico_id: int
    ano: int
    turno: int
    cargo: str
    uf: str | None
    ue_nome: str
    numero_urna: int | None
    nome_urna: str
    partido_sigla: str | None
    situacao_candidatura: str | None
    situacao_turno: str | None
    eleito: bool


class DespesaOut(_Out):
    id: int
    politico_id: int | None
    verba: str
    parlamentar_nome: str
    uf: str | None
    partido_sigla: str | None
    ano: int
    mes: int
    data_emissao: date | None
    categoria: str
    subcategoria: str | None
    fornecedor_nome: str | None
    fornecedor_documento: str | None = Field(
        description="CNPJ completo; CPF de pessoa física sai mascarado (***.456.789-**)"
    )
    fornecedor_tipo: str | None
    documento_numero: str | None
    documento_url: str | None
    valor_documento: Decimal | None
    valor_glosa: Decimal | None
    valor_liquido: Decimal = Field(description="Valor reembolsado. Negativo = estorno.")
    fonte: str
    fonte_url: str


class TotalCategoria(BaseModel):
    categoria: str
    total: Decimal
    quantidade: int


class TotalFornecedor(BaseModel):
    fornecedor_documento: str | None
    fornecedor_nome: str | None
    total: Decimal
    quantidade: int


class TotalMes(BaseModel):
    ano: int
    mes: int
    total: Decimal
    quantidade: int


class ResumoDespesas(BaseModel):
    total: Decimal
    quantidade: int
    por_ano: list[TotalAno]
    por_mes: list[TotalMes]
    por_categoria: list[TotalCategoria]
    maiores_fornecedores: list[TotalFornecedor]


class Contagem(BaseModel):
    chave: str | None
    quantidade: int


class ContagemEleitos(BaseModel):
    chave: str | None
    quantidade: int
    eleitos: int


class TotalVerba(BaseModel):
    verba: str
    total: Decimal
    quantidade: int


class Estatisticas(BaseModel):
    politicos: int
    politicos_em_exercicio: int
    mandatos: int
    candidaturas: int
    candidaturas_eleitas: int
    despesas: int
    despesas_sem_politico: int
    despesas_total: Decimal
    entes: int
    partidos: int
    fotos: int
    matches_pendentes: int
    em_exercicio_por_cargo: list[Contagem]
    em_exercicio_por_uf: list[Contagem]
    em_exercicio_por_partido: list[Contagem]
    despesas_por_verba: list[TotalVerba]
    ultima_ingestao_em: datetime | None


class PartidoOut(_Out):
    id: int
    sigla: str
    nome: str
    numero_tse: int | None
    ativo: bool


class PartidoDetalhe(PartidoOut):
    politicos_em_exercicio: int
    mandatos: int
    candidaturas: int
    candidaturas_eleitas: int
    despesas_total: Decimal
    despesas_quantidade: int
    origem: Origem


class ResumoCandidaturas(BaseModel):
    total: int
    eleitos: int
    por_ano: list[ContagemEleitos]
    por_cargo: list[ContagemEleitos]
    por_situacao: list[Contagem]
    por_partido: list[ContagemEleitos]


class ExecucaoOut(_Out):
    id: int
    fonte: str
    recurso: str
    particao: str
    status: StatusExecucao
    registros: int
    erro: str | None
    iniciado_em: datetime
    finalizado_em: datetime | None


class MatchPendenteOut(_Out):
    id: int
    origem: str
    id_externo: str
    motivo: str
    politico_ids: list[int]
    resolvido: bool
    criado_em: datetime
