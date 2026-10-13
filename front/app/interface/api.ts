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

export interface PartidoOut {
  id: number
  sigla: string
  nome: string
  numero_tse: number | null
  ativo: boolean
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
