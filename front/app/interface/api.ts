// Espelha back/src/ouroboros/api/schemas.py. Decimal chega como string.

export type Decimal = string

export type Esfera = "federal" | "estadual" | "municipal"
export type Cargo =
  | "presidente"
  | "governador"
  | "prefeito"
  | "senador"
  | "deputado_federal"
  | "deputado_estadual"
  | "vereador"
export type StatusExecucao = "rodando" | "sucesso" | "falha"

export const CARGOS: Cargo[] = [
  "presidente",
  "governador",
  "prefeito",
  "senador",
  "deputado_federal",
  "deputado_estadual",
  "vereador",
]
export const ESFERAS: Esfera[] = ["federal", "estadual", "municipal"]
export const UFS = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
  "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]

export interface Page<T> {
  items: T[]
  next_cursor: string | null
}

export interface Origem {
  fonte: string
  fonte_url: string
  raw_hash: string
  ingerido_em: string
}

export interface EnteOut {
  codigo_ibge: number
  nome: string
  esfera: Esfera
  uf: string | null
  regiao: string | null
}

export interface EnteDetalhe extends EnteOut {
  uf_codigo: number | null
  origem: Origem
}

export interface FonteStatus {
  fonte: string
  recurso: string
  particao: string
  status: StatusExecucao
  registros: number
  erro: string | null
  iniciado_em: string
  finalizado_em: string | null
  ultimo_sucesso_em: string | null
}

export interface ExecucaoOut {
  id: number
  fonte: string
  recurso: string
  particao: string
  status: StatusExecucao
  registros: number
  erro: string | null
  iniciado_em: string
  finalizado_em: string | null
}

export interface Identificador {
  origem: string
  id_externo: string
  metodo: string
}

export interface MandatoOut {
  cargo: Cargo
  esfera: Esfera
  uf: string | null
  partido_sigla: string | null
  partidos: string[]
  legislatura: number | null
  condicao: string | null
  inicio: string | null
  fim: string | null
  origem: string
}

export interface FotoOut {
  id: number
  url: string
  origem: string
  ano: number | null
  largura: number
  altura: number
  url_origem: string
}

export interface PoliticoResumo {
  id: number
  nome: string
  nome_civil: string | null
  foto: FotoOut | null
  ultimo_mandato: MandatoOut | null
}

export interface TotalAno {
  ano: number
  total: Decimal
  quantidade: number
}

export interface TotalMes extends TotalAno {
  mes: number
}

export interface PoliticoDetalhe extends PoliticoResumo {
  data_nascimento: string | null
  genero: string | null
  identificadores: Identificador[]
  mandatos: MandatoOut[]
  candidaturas: number
  gastos_gabinete_por_ano: TotalAno[]
}

export interface CandidaturaOut {
  sq_candidato: number
  politico_id: number
  ano: number
  turno: number
  cargo: string
  uf: string | null
  ue_nome: string
  numero_urna: number | null
  nome_urna: string
  partido_sigla: string | null
  situacao_candidatura: string | null
  situacao_turno: string | null
  motivos_situacao: string[]
  eleito: boolean
}

export interface DespesaOut {
  id: number
  politico_id: number | null
  verba: string
  parlamentar_nome: string
  uf: string | null
  partido_sigla: string | null
  ano: number
  mes: number
  data_emissao: string | null
  categoria: string
  subcategoria: string | null
  fornecedor_nome: string | null
  fornecedor_documento: string | null
  fornecedor_tipo: string | null
  documento_numero: string | null
  documento_url: string | null
  valor_documento: Decimal | null
  valor_glosa: Decimal | null
  valor_liquido: Decimal
  fonte: string
  fonte_url: string
}

export interface TotalCategoria {
  categoria: string
  total: Decimal
  quantidade: number
}

export interface TotalFornecedor {
  fornecedor_documento: string | null
  fornecedor_nome: string | null
  total: Decimal
  quantidade: number
}

export interface ResumoDespesas {
  total: Decimal
  quantidade: number
  por_ano: TotalAno[]
  por_mes: TotalMes[]
  por_categoria: TotalCategoria[]
  maiores_fornecedores: TotalFornecedor[]
}

export interface Contagem {
  chave: string | null
  quantidade: number
}

export interface ContagemEleitos extends Contagem {
  eleitos: number
}

export interface TotalVerba {
  verba: string
  total: Decimal
  quantidade: number
}

export interface Estatisticas {
  politicos: number
  politicos_em_exercicio: number
  mandatos: number
  candidaturas: number
  candidaturas_eleitas: number
  despesas: number
  despesas_sem_politico: number
  despesas_total: Decimal
  entes: number
  partidos: number
  fotos: number
  matches_pendentes: number
  em_exercicio_por_cargo: Contagem[]
  em_exercicio_por_uf: Contagem[]
  em_exercicio_por_partido: Contagem[]
  despesas_por_verba: TotalVerba[]
  ultima_ingestao_em: string | null
}

export interface LogoOut {
  id: number
  url: string
  origem: string
  largura: number | null
  altura: number | null
  url_origem: string
}

export interface PartidoOut {
  id: number
  sigla: string
  nome: string
  numero_tse: number | null
  ativo: boolean
  logo: LogoOut | null
}

export interface PartidoDetalhe extends PartidoOut {
  politicos_em_exercicio: number
  mandatos: number
  candidaturas: number
  candidaturas_eleitas: number
  despesas_total: Decimal
  despesas_quantidade: number
  origem: Origem
}

export interface ResumoCandidaturas {
  total: number
  eleitos: number
  por_ano: ContagemEleitos[]
  por_cargo: ContagemEleitos[]
  por_situacao: Contagem[]
  por_partido: ContagemEleitos[]
}

export interface MatchPendenteOut {
  id: number
  origem: string
  id_externo: string
  motivo: string
  politico_ids: number[]
  resolvido: boolean
  criado_em: string
}

export interface Health {
  status: string
  db: string
}

// Filtros de query string
export type Params = Record<string, string | number | boolean | null | undefined>

export interface FiltroDespesa {
  ano?: number
  mes?: number
  verba?: string
  uf?: string
  categoria?: string
  fornecedor?: string
  politico?: number
  data_inicio?: string
  data_fim?: string
}

// Emendas parlamentares (Portal da Transparência)
export interface EmendaOut {
  id: number
  codigo: string
  ano: number
  tipo: string
  numero: string | null
  autor_nome: string
  politico_id: number | null
  localidade: string | null
  municipio_codigo_ibge: number | null
  municipio_nome: string | null
  uf: string | null
  funcao: string | null
  subfuncao: string | null
  programa: string | null
  acao: string | null
  valor_empenhado: Decimal
  valor_liquidado: Decimal
  valor_pago: Decimal
  valor_rp_pago: Decimal
  fonte_url: string
}

export interface FavorecidoOut {
  id: number
  emenda_codigo: string
  ano: number
  mes: number
  tipo: string
  autor_nome: string
  politico_id: number | null
  favorecido_documento: string | null
  favorecido_nome: string
  favorecido_tipo: string | null
  natureza_juridica: string | null
  uf: string | null
  municipio_nome: string | null
  valor: Decimal
}

export interface TotalChave {
  chave: string | null
  rotulo: string | null
  empenhado: Decimal
  pago: Decimal
  quantidade: number
}

export interface ResumoEmendas {
  quantidade: number
  empenhado: Decimal
  pago: Decimal
  por_ano: TotalChave[]
  por_tipo: TotalChave[]
  por_funcao: TotalChave[]
  por_uf: TotalChave[]
  maiores_autores: TotalChave[]
  maiores_destinos: TotalChave[]
  maiores_favorecidos: TotalChave[]
}

// Grafo de relações
export type GrafoTipo =
  | "politico"
  | "hub"
  | "partido"
  | "cargo"
  | "eleicao"
  | "categoria"
  | "fornecedor"
  | "area"
  | "municipio"
  | "favorecido"
  | "autor"
  | "obra"
export type GrafoGrupo = "centro" | "carreira" | "gastos" | "emendas" | "obras" | "conexoes"

export interface GrafoNo {
  id: string
  tipo: GrafoTipo
  rotulo: string
  detalhe: string | null
  valor: Decimal | null
  nivel: number
  grupo: GrafoGrupo
  pai: string | null
  imagem: string | null
  chave: string | null
}

export interface GrafoAresta {
  id: string
  origem: string
  destino: string
  tipo: string
  valor: Decimal | null
}

export interface Grafo {
  centro: string
  nos: GrafoNo[]
  arestas: GrafoAresta[]
}

// alertas (análise de indícios)
export type Severidade = "alta" | "media" | "baixa"
export const SEVERIDADES: Severidade[] = ["alta", "media", "baixa"]

export interface AlertaDocumento {
  url?: string | null
  despesa_id?: number
  politico_id?: number | null
  parlamentar?: string
  ano?: number
  mes?: number
  data_emissao?: string
  valor?: number
  fornecedor?: string | null
  categoria?: string
}

export interface AlertaOut {
  id: number
  detector: string
  severidade: Severidade
  score: number
  peso: number
  politico_id: number | null
  politico_nome: string | null
  ano_inicio: number | null
  ano_fim: number | null
  entidade_documento: string | null
  entidade_nome: string | null
  valor: Decimal | null
  titulo: string
  descricao: string
  evidencias: {
    metricas?: Record<string, unknown>
    documentos?: AlertaDocumento[]
    emendas?: string[]
    [k: string]: unknown
  }
  gerado_em: string
}

export interface DetectorOut {
  codigo: string
  titulo: string
  area: "gabinete" | "emendas" | "eleicoes"
  peso: number
  metodologia: string
  alertas: number
  alta: number
  media: number
  baixa: number
}

export interface Detectores {
  aviso: string
  gerado_em: string | null
  detectores: DetectorOut[]
}

export interface RiscoPolitico {
  politico_id: number
  nome: string
  foto_id: number | null
  partido: string | null
  uf: string | null
  risco: number
  alertas: number
  alertas_alta: number
  valor: Decimal
  detectores: { detector: string; score: number; alertas: number }[]
}

export interface Ranking {
  aviso: string
  items: RiscoPolitico[]
}

// Obras e convênios (Transferegov)
export interface ObraOut {
  numero: number
  ano: number
  situacao: string | null
  modalidade: string | null
  orgao_superior: string | null
  proponente_cnpj: string | null
  proponente_nome: string | null
  uf: string | null
  municipio_codigo_ibge: number | null
  municipio_nome: string | null
  objeto: string | null
  obra_nome: string | null
  obra_id: string | null
  endereco: string | null
  cep: string | null
  latitude: Decimal | null
  longitude: Decimal | null
  inicio_vigencia: string | null
  fim_vigencia: string | null
  inicio_obra: string | null
  ultima_medicao: string | null
  dias_sem_medicao: number | null
  percentual_execucao: Decimal | null
  valor_global: Decimal
  valor_repasse: Decimal
  valor_desembolsado: Decimal
  valor_executado: Decimal | null
}

export interface ObraEmendaOut {
  emenda_codigo: string | null
  tipo: string | null
  parlamentar_nome: string
  politico_id: number | null
  politico_nome: string | null
  impositiva: boolean | null
  valor_repasse: Decimal
}

export interface ObraMetaOut {
  numero: number | null
  descricao: string | null
  data_inicio: string | null
  data_fim: string | null
  municipio_nome: string | null
  uf: string | null
  endereco: string | null
  cep: string | null
  quantidade: Decimal | null
  unidade: string | null
  valor: Decimal
}

export interface ObraContratoOut {
  numero: string | null
  modalidade_licitacao: string | null
  objeto: string | null
  tipo_aquisicao: string | null
  fornecedor_documento: string | null
  fornecedor_nome: string | null
  data_assinatura: string | null
  inicio_vigencia: string | null
  fim_vigencia: string | null
  valor: Decimal
}

export interface ObraFornecedorOut {
  documento: string | null
  nome: string
  pagamentos: number
  primeiro_pagamento: string | null
  ultimo_pagamento: string | null
  valor: Decimal
}

export interface ObraDetalhe extends ObraOut {
  subsituacao: string | null
  orgao: string | null
  natureza_juridica: string | null
  data_proposta: string | null
  data_assinatura: string | null
  data_publicacao: string | null
  fim_vigencia_original: string | null
  limite_prestacao_contas: string | null
  prorrogacoes: number | null
  aditivos: number | null
  valor_contrapartida: Decimal
  valor_empenhado: Decimal
  valor_saldo_conta: Decimal | null
  valor_pago_fornecedores: Decimal
  emendas: ObraEmendaOut[]
  metas: ObraMetaOut[]
  desembolsos: { data: string | null; documento: string | null; valor: Decimal }[]
  contratos: ObraContratoOut[]
  fornecedores: ObraFornecedorOut[]
  link_transferegov: string
  link_obrasgov: string | null
  fonte_url: string
}

export interface TotalObras {
  chave: string | null
  rotulo: string | null
  quantidade: number
  valor_global: Decimal
  valor_desembolsado: Decimal
}

export interface ResumoObras {
  quantidade: number
  valor_global: Decimal
  valor_repasse: Decimal
  valor_desembolsado: Decimal
  com_localizacao: number
  paradas: number
  por_situacao: TotalObras[]
  por_uf: TotalObras[]
  por_ano: TotalObras[]
  por_orgao: TotalObras[]
  maiores_autores: TotalObras[]
  maiores_fornecedores: TotalObras[]
}

export interface PontoObra {
  numero: number
  latitude: Decimal
  longitude: Decimal
  rotulo: string
  situacao: string | null
  percentual_execucao: Decimal | null
  valor_global: Decimal
}

export interface TransferenciaEspecialOut {
  id: number
  codigo: string
  ano: number
  situacao: string | null
  emenda_codigo: string | null
  parlamentar_nome: string
  politico_id: number | null
  beneficiario_cnpj: string | null
  beneficiario_nome: string
  uf: string | null
  municipio_codigo_ibge: number | null
  areas: string | null
  valor_custeio: Decimal
  valor_investimento: Decimal
  valor_pago: Decimal
  executores: {
    cnpj: string | null
    nome: string
    objeto: string | null
    areas: string[]
    valor_custeio: Decimal
    valor_investimento: Decimal
  }[]
}

export interface EmendaDetalhe {
  codigo: string
  ano: number
  tipo: string
  autor_nome: string
  politico_id: number | null
  politico_nome: string | null
  empenhado: Decimal
  pago: Decimal
  destinos: EmendaOut[]
  favorecidos: TotalChave[]
  obras: ObraOut[]
  transferencias_especiais: TransferenciaEspecialOut[]
}

// presidência (cartão de pagamento)
export interface GastoPresidenciaOut {
  id: number
  data: string | null
  ano: number
  mes: number
  unidade_gestora: string | null
  portador: string | null
  favorecido_documento: string | null
  favorecido_nome: string | null
  valor: Decimal
  tipo: "credito" | "saque"
  categoria: string | null
  transacao: string | null
  sigiloso: boolean
  classificacao: string | null
  presidente_id: number | null
  presidente: string | null
  origem: Origem
}

export interface MandatoPresidente {
  id_externo: string
  inicio: string
  fim: string
  condicao: string | null
  partidos: string[]
  dias: number
  total: Decimal
  quantidade: number
  saques: Decimal
  sigiloso: Decimal
  por_dia: Decimal
}

export interface PresidenteGastos {
  politico_id: number
  nome: string
  foto_id: number | null
  total: Decimal
  quantidade: number
  mandatos: MandatoPresidente[]
}

export interface TotalRotulo {
  chave: string | null
  total: Decimal
  quantidade: number
}

export interface ResumoPresidencia {
  aviso: string
  total: Decimal
  quantidade: number
  saques: Decimal
  sigiloso: Decimal
  por_ano: TotalRotulo[]
  por_categoria: TotalRotulo[]
  por_unidade: TotalRotulo[]
  maiores_favorecidos: TotalRotulo[]
}
