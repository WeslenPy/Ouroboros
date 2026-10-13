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
        "municipio, favorecido, autor, obra"
    )
    rotulo: str
    detalhe: str | None = None
    valor: Decimal | None = None
    nivel: int = Field(description="Distância do centro (0 = centro)")
    grupo: str = Field(description="carreira, gastos, emendas, obras, conexoes")
    pai: str | None = Field(None, description="Nó de onde este se ramifica (para o layout)")
    imagem: str | None = None
    chave: str | None = Field(None, description="ID para abrir o nó como centro de outro grafo")


class GrafoAresta(BaseModel):
    id: str
    origem: str
    destino: str
    tipo: str = Field(
        description="filiacao, mandato, candidatura, gasto, pagamento, emenda, destino, "
        "recebimento, conexao, obra, contrato, local"
    )
    valor: Decimal | None = None


class Grafo(BaseModel):
    centro: str
    nos: list[GrafoNo]
    arestas: list[GrafoAresta]


AVISO_ALERTAS = (
    "Alertas são indícios estatísticos ou cruzamentos de dados públicos, não acusação nem prova "
    "de irregularidade. Cada um traz a metodologia e os documentos oficiais para conferência."
)


class AlertaOut(_Out):
    id: int
    detector: str
    severidade: str = Field(description="alta, media, baixa")
    score: float = Field(description="0-100: força do indício dentro do detector")
    peso: float = Field(description="0-1: confiança no detector")
    politico_id: int | None
    politico_nome: str | None = None
    ano_inicio: int | None
    ano_fim: int | None
    entidade_documento: str | None = Field(description="CNPJ (ou CPF mascarado) envolvido")
    entidade_nome: str | None
    valor: Decimal | None = Field(description="Dinheiro envolvido no achado")
    titulo: str
    descricao: str
    evidencias: dict = Field(description="Métricas que dispararam o alerta e documentos")
    gerado_em: datetime


class DetectorOut(BaseModel):
    codigo: str
    titulo: str
    area: str = Field(description="gabinete, emendas, eleicoes")
    peso: float
    metodologia: str
    alertas: int
    alta: int
    media: int
    baixa: int


class DetectorRisco(BaseModel):
    detector: str
    score: float
    alertas: int


class RiscoPolitico(BaseModel):
    politico_id: int
    nome: str
    foto_id: int | None = None
    partido: str | None = None
    uf: str | None = None
    risco: float = Field(description="0-100: combinação (noisy-OR) dos detectores")
    alertas: int
    alertas_alta: int
    valor: Decimal = Field(description="Soma do dinheiro envolvido nos alertas")
    detectores: list[DetectorRisco]


class Detectores(BaseModel):
    aviso: str = AVISO_ALERTAS
    gerado_em: datetime | None
    detectores: list[DetectorOut]


class Ranking(BaseModel):
    aviso: str = AVISO_ALERTAS
    items: list[RiscoPolitico]


# --------------------------------------------------------------------------- obras / convênios


class ObraOut(_Out):
    """Convênio do Transferegov visto como obra: onde, quando, quanto e em que pé está."""

    numero: int = Field(description="Número do convênio (o mesmo do Portal da Transparência)")
    ano: int = Field(description="Ano da proposta")
    situacao: str | None
    modalidade: str | None
    orgao_superior: str | None = Field(description="Ministério que repassa o dinheiro")
    proponente_cnpj: str | None = Field(description="Quem executa: prefeitura, estado, entidade")
    proponente_nome: str | None
    uf: str | None
    municipio_codigo_ibge: int | None
    municipio_nome: str | None
    objeto: str | None
    obra_nome: str | None
    obra_id: str | None = Field(description="ID da obra no Obrasgov (CIPI)")
    endereco: str | None
    cep: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    inicio_vigencia: date | None
    fim_vigencia: date | None
    inicio_obra: date | None = Field(description="Início da obra informado na medição")
    ultima_medicao: date | None
    dias_sem_medicao: int | None
    percentual_execucao: Decimal | None = Field(description="Execução física informada (%)")
    valor_global: Decimal
    valor_repasse: Decimal = Field(description="Parte da União")
    valor_desembolsado: Decimal = Field(description="Já liberado para a conta do convênio")
    valor_executado: Decimal | None


class ObraEmendaOut(_Out):
    emenda_codigo: str | None
    tipo: str | None = Field(description="INDIVIDUAL, BANCADA, COMISSAO, RELATOR GERAL")
    parlamentar_nome: str
    politico_id: int | None
    politico_nome: str | None = None
    impositiva: bool | None
    valor_repasse: Decimal


class ObraMetaOut(_Out):
    numero: int | None
    descricao: str | None
    data_inicio: date | None
    data_fim: date | None
    municipio_nome: str | None
    uf: str | None
    endereco: str | None
    cep: str | None
    quantidade: Decimal | None
    unidade: str | None
    valor: Decimal


class ObraDesembolsoOut(_Out):
    data: date | None
    documento: str | None
    valor: Decimal


class ObraContratoOut(_Out):
    numero: str | None
    modalidade_licitacao: str | None
    objeto: str | None
    tipo_aquisicao: str | None
    fornecedor_documento: str | None
    fornecedor_nome: str | None
    data_assinatura: date | None
    inicio_vigencia: date | None
    fim_vigencia: date | None
    valor: Decimal


class ObraFornecedorOut(_Out):
    documento: str | None = Field(description="CNPJ; nulo = pessoas físicas somadas")
    nome: str
    pagamentos: int
    primeiro_pagamento: date | None
    ultimo_pagamento: date | None
    valor: Decimal


class ObraDetalhe(ObraOut):
    subsituacao: str | None
    orgao: str | None
    natureza_juridica: str | None
    data_proposta: date | None
    data_assinatura: date | None
    data_publicacao: date | None
    fim_vigencia_original: date | None
    limite_prestacao_contas: date | None
    prorrogacoes: int | None
    aditivos: int | None
    valor_contrapartida: Decimal
    valor_empenhado: Decimal
    valor_saldo_conta: Decimal | None
    valor_pago_fornecedores: Decimal = Field(description="Soma dos pagamentos da conta")
    emendas: list[ObraEmendaOut]
    metas: list[ObraMetaOut]
    desembolsos: list[ObraDesembolsoOut]
    contratos: list[ObraContratoOut]
    fornecedores: list[ObraFornecedorOut]
    link_transferegov: str
    link_obrasgov: str | None
    fonte_url: str


class TotalObras(BaseModel):
    chave: str | None
    rotulo: str | None = None
    quantidade: int
    valor_global: Decimal
    valor_desembolsado: Decimal


class ResumoObras(BaseModel):
    quantidade: int
    valor_global: Decimal
    valor_repasse: Decimal
    valor_desembolsado: Decimal
    com_localizacao: int
    paradas: int = Field(
        description="Obras acompanhadas, abaixo de 100%, sem medição há 180+ dias ou com "
        "vigência vencida em execução"
    )
    por_situacao: list[TotalObras]
    por_uf: list[TotalObras]
    por_ano: list[TotalObras]
    por_orgao: list[TotalObras]
    maiores_autores: list[TotalObras] = Field(description="chave = politico_id (ou nome)")
    maiores_fornecedores: list[TotalObras] = Field(
        description="chave = CNPJ; valor_global = contratado, valor_desembolsado = pago"
    )


class PontoObra(BaseModel):
    numero: int
    latitude: Decimal
    longitude: Decimal
    rotulo: str
    situacao: str | None
    percentual_execucao: Decimal | None
    valor_global: Decimal


class TransferenciaEspecialExecutorOut(_Out):
    cnpj: str | None
    nome: str
    objeto: str | None
    areas: list[str]
    valor_custeio: Decimal
    valor_investimento: Decimal


class TransferenciaEspecialOut(_Out):
    """Emenda Pix: o dinheiro cai direto no caixa do ente, com um plano do que será feito."""

    id: int
    codigo: str
    ano: int
    situacao: str | None
    emenda_codigo: str | None
    parlamentar_nome: str
    politico_id: int | None
    beneficiario_cnpj: str | None
    beneficiario_nome: str
    uf: str | None
    municipio_codigo_ibge: int | None
    areas: str | None
    valor_custeio: Decimal
    valor_investimento: Decimal
    valor_pago: Decimal = Decimal("0")
    executores: list[TransferenciaEspecialExecutorOut] = []


class EmendaDetalhe(BaseModel):
    """Uma emenda de ponta a ponta: destinos, quem recebeu e o que virou (convênio/obra ou
    transferência especial)."""

    codigo: str
    ano: int
    tipo: str
    autor_nome: str
    politico_id: int | None
    politico_nome: str | None
    empenhado: Decimal
    pago: Decimal
    destinos: list[EmendaOut]
    favorecidos: list[TotalChave] = Field(description="chave = documento do favorecido")
    obras: list[ObraOut]
    transferencias_especiais: list[TransferenciaEspecialOut]


class GastoPresidenciaOut(_Out):
    id: int
    data: date | None = Field(description="Nula quando o lançamento ainda é sigiloso")
    ano: int
    mes: int
    unidade_gestora: str | None
    portador: str | None = Field(description="CPF mascarado do servidor portador do cartão")
    favorecido_documento: str | None
    favorecido_nome: str | None
    valor: Decimal
    tipo: str = Field(description="credito (compra) ou saque (dinheiro vivo)")
    categoria: str | None
    transacao: str | None
    sigiloso: bool = Field(description="2003-2022: era classificado. 2023+: ainda sigiloso")
    classificacao: str | None = Field(description="CDIC da informação classificada")
    presidente_id: int | None = None
    presidente: str | None = None
    origem: Origem


class MandatoPresidente(BaseModel):
    id_externo: str
    inicio: date
    fim: date
    condicao: str | None
    partidos: list[str]
    dias: int = Field(description="Dias de exercício até hoje")
    total: Decimal
    quantidade: int
    saques: Decimal
    sigiloso: Decimal = Field(description="Valor ainda sem detalhe (só 2023+)")
    por_dia: Decimal = Field(description="Total / dias de exercício: compara períodos desiguais")


class PresidenteGastos(BaseModel):
    politico_id: int
    nome: str
    foto_id: int | None
    total: Decimal
    quantidade: int
    mandatos: list[MandatoPresidente]


class TotalRotulo(BaseModel):
    chave: str | None
    total: Decimal
    quantidade: int


class ResumoPresidencia(BaseModel):
    aviso: str = (
        "Valores nominais (sem correção pela inflação). 2003-2022: planilha da Casa Civil com "
        "os gastos antes sigilosos; 2023 em diante: Portal da Transparência, onde parte ainda é "
        "sigilosa. O cartão é usado por servidores da Presidência, não pelo presidente em pessoa."
    )
    total: Decimal
    quantidade: int
    saques: Decimal
    sigiloso: Decimal
    por_ano: list[TotalRotulo]
    por_categoria: list[TotalRotulo]
    por_unidade: list[TotalRotulo]
    maiores_favorecidos: list[TotalRotulo] = Field(description="Por nome: a fonte perdeu CNPJs")
