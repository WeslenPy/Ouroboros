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
    url: str = Field(
        description="URL para exibir: link oficial da fonte (Câmara, Senado) ou arquivo servido "
        "por esta API (/v1/fotos/{id}, fotos do TSE)"
    )
    origem: str
    ano: int | None
    largura: int | None = Field(description="Só para fotos armazenadas")
    altura: int | None
    url_origem: str = Field(description="Onde a foto foi obtida")

    @classmethod
    def de(cls, foto) -> "FotoOut":
        return cls(
            id=foto.id,
            url=f"/v1/fotos/{foto.id}" if foto.armazenada else foto.url_origem,
            origem=foto.origem,
            ano=foto.ano,
            largura=foto.largura,
            altura=foto.altura,
            url_origem=foto.url_origem,
        )


class LogoOut(_Out):
    id: int
    url: str = Field(
        description="URL para exibir: arquivo servido por esta API (/v1/partidos/logos/{id}) "
        "ou, para logo manual só com link, a URL de origem"
    )
    origem: str = Field(description="wikidata (coletada) ou manual")
    largura: int | None = Field(description="Só para logos armazenadas")
    altura: int | None
    url_origem: str = Field(description="Onde a logo foi obtida (página do arquivo no Commons)")

    @classmethod
    def de(cls, logo) -> "LogoOut":
        return cls(
            id=logo.id,
            url=f"/v1/partidos/logos/{logo.id}" if logo.armazenada else logo.url_origem,
            origem=logo.origem,
            largura=logo.largura,
            altura=logo.altura,
            url_origem=logo.url_origem,
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
    motivos_situacao: list[str]
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
    logo: LogoOut | None = None


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


class EmendaOut(_Out):
    id: int
    codigo: str
    ano: int
    tipo: str
    numero: str | None
    autor_nome: str
    politico_id: int | None
    localidade: str | None
    municipio_codigo_ibge: int | None
    municipio_nome: str | None
    uf: str | None
    funcao: str | None
    subfuncao: str | None
    programa: str | None
    acao: str | None
    valor_empenhado: Decimal
    valor_liquidado: Decimal
    valor_pago: Decimal = Field(description="Pago no ano da emenda")
    valor_rp_pago: Decimal = Field(description="Restos a pagar pagos em anos seguintes")
    fonte_url: str


class FavorecidoOut(_Out):
    id: int
    emenda_codigo: str
    ano: int
    mes: int
    tipo: str
    autor_nome: str
    politico_id: int | None
    favorecido_documento: str | None
    favorecido_nome: str
    favorecido_tipo: str | None
    natureza_juridica: str | None
    uf: str | None
    municipio_nome: str | None
    valor: Decimal


class TotalChave(BaseModel):
    chave: str | None
    rotulo: str | None = None
    empenhado: Decimal
    pago: Decimal
    quantidade: int


class ResumoEmendas(BaseModel):
    quantidade: int
    empenhado: Decimal
    pago: Decimal = Field(description="Pago no ano + restos a pagar pagos")
    por_ano: list[TotalChave]
    por_tipo: list[TotalChave]
    por_funcao: list[TotalChave]
    por_uf: list[TotalChave]
    maiores_autores: list[TotalChave] = Field(description="chave = politico_id (ou nome)")
    maiores_destinos: list[TotalChave] = Field(description="chave = código IBGE (ou localidade)")
    maiores_favorecidos: list[TotalChave] = Field(description="chave = documento do favorecido")


class GrafoNo(BaseModel):
    id: str = Field(description="tipo:chave, único no grafo")
    tipo: str = Field(
        description="politico, hub, partido, cargo, eleicao, categoria, fornecedor, area, "
        "municipio, favorecido"
    )
    rotulo: str
    detalhe: str | None = None
    valor: Decimal | None = None
    nivel: int = Field(description="Distância do centro (0 = centro)")
    grupo: str = Field(description="carreira, gastos, emendas, conexoes")
    pai: str | None = Field(None, description="Nó de onde este se ramifica (para o layout)")
    imagem: str | None = None
    chave: str | None = Field(None, description="ID para abrir o nó como centro de outro grafo")


class GrafoAresta(BaseModel):
    id: str
    origem: str
    destino: str
    tipo: str = Field(
        description="filiacao, mandato, candidatura, gasto, pagamento, emenda, destino, "
        "recebimento, conexao"
    )
    valor: Decimal | None = None


class Grafo(BaseModel):
    centro: str
    nos: list[GrafoNo]
    arestas: list[GrafoAresta]
