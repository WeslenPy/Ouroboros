import { HOST_API } from "~/constants/url"
import type {
  AlertaOut,
  CandidaturaOut,
  Detectores,
  DespesaOut,
  EmendaDetalhe,
  EmendaOut,
  EnteDetalhe,
  EnteOut,
  Estatisticas,
  ExecucaoOut,
  FavorecidoOut,
  FiltroDespesa,
  FonteStatus,
  FotoOut,
  GastoPresidenciaOut,
  Grafo,
  Health,
  MandatoOut,
  MatchPendenteOut,
  ObraDetalhe,
  ObraOut,
  Page,
  Params,
  PartidoDetalhe,
  PartidoOut,
  PoliticoDetalhe,
  PoliticoResumo,
  PontoObra,
  PresidenteGastos,
  Ranking,
  ResumoPresidencia,
  ResumoCandidaturas,
  ResumoDespesas,
  ResumoEmendas,
  ResumoObras,
  TransferenciaEspecialOut,
} from "~/interface/api"

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail)
  }
}

function query(params?: Params): string {
  if (!params) return ""
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue
    qs.set(key, String(value))
  }
  const s = qs.toString()
  return s ? `?${s}` : ""
}

/** Cliente da API Ouroboros (somente leitura, sem auth). Mesmo molde do WAConnect. */
export class OuroborosApi {
  readonly host = HOST_API
  readonly base = `${HOST_API}/v1`

  /** Converte caminho relativo devolvido pela API (ex.: /v1/fotos/1) em URL absoluta. */
  url(path: string): string {
    return path.startsWith("http") ? path : `${this.host}${path}`
  }

  private async pre_process(response: Response): Promise<void> {
    if (response.ok) return
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail)
    } catch {
      // corpo não-JSON
    }
    throw new ApiError(response.status, detail)
  }

  async get<T>(path: string, params?: Params, init?: RequestInit): Promise<T> {
    let response: Response
    try {
      response = await fetch(`${this.base}${path}${query(params)}`, {
        ...init,
        headers: { Accept: "application/json", ...init?.headers },
      })
    } catch {
      throw new ApiError(0, "API indisponível")
    }
    await this.pre_process(response)
    return response.json() as Promise<T>
  }

  /** Baixa a listagem como CSV, percorrendo até `maxPages` páginas pelo header X-Next-Cursor. */
  async exportCsv(path: string, params: Params, filename: string, maxPages = 20): Promise<number> {
    const parts: string[] = []
    let cursor: string | null = null
    let pages = 0
    do {
      const response: Response = await fetch(
        `${this.base}${path}${query({ ...params, limit: 500, cursor })}`,
        { headers: { Accept: "text/csv" } },
      )
      await this.pre_process(response)
      let text = (await response.text()).replace(/^﻿/, "")
      if (parts.length) text = text.slice(text.indexOf("\n") + 1) // header só uma vez
      parts.push(text)
      cursor = response.headers.get("X-Next-Cursor")
      pages++
    } while (cursor && pages < maxPages)
    const blob = new Blob(["﻿", ...parts], { type: "text/csv;charset=utf-8" })
    const a = document.createElement("a")
    a.href = URL.createObjectURL(blob)
    a.download = `${filename}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
    return pages
  }

  health(): Promise<Health> {
    return fetch(`${this.host}/health`).then((r) => r.json())
  }

  stats() {
    return this.get<Estatisticas>("/stats")
  }

  // políticos
  politicos(params: Params) {
    return this.get<Page<PoliticoResumo>>("/politicos", params)
  }
  politico(id: number | string) {
    return this.get<PoliticoDetalhe>(`/politicos/${id}`)
  }
  politicoMandatos(id: number | string) {
    return this.get<MandatoOut[]>(`/politicos/${id}/mandatos`)
  }
  politicoCandidaturas(id: number | string) {
    return this.get<CandidaturaOut[]>(`/politicos/${id}/candidaturas`)
  }
  politicoFotos(id: number | string) {
    return this.get<FotoOut[]>(`/politicos/${id}/fotos`)
  }
  politicoDespesas(id: number | string, params: Params) {
    return this.get<Page<DespesaOut>>(`/politicos/${id}/despesas`, params)
  }
  politicoDespesasResumo(id: number | string, filtro: FiltroDespesa) {
    return this.get<ResumoDespesas>(`/politicos/${id}/despesas/resumo`, filtro as Params)
  }

  // despesas
  despesas(params: Params) {
    return this.get<Page<DespesaOut>>("/despesas", params)
  }
  despesasResumo(filtro: FiltroDespesa) {
    return this.get<ResumoDespesas>("/despesas/resumo", filtro as Params)
  }

  // candidaturas
  candidaturas(params: Params) {
    return this.get<Page<CandidaturaOut>>("/candidaturas", params)
  }
  candidaturasResumo(params: Params) {
    return this.get<ResumoCandidaturas>("/candidaturas/resumo", params)
  }

  // partidos
  partidos(params?: Params) {
    return this.get<PartidoOut[]>("/partidos", params)
  }
  partido(sigla: string) {
    return this.get<PartidoDetalhe>(`/partidos/${encodeURIComponent(sigla)}`)
  }

  // entes
  entes(params: Params) {
    return this.get<Page<EnteOut>>("/entes", params)
  }
  ente(codigo: number | string) {
    return this.get<EnteDetalhe>(`/entes/${codigo}`)
  }

  // fontes / qualidade
  fontes() {
    return this.get<FonteStatus[]>("/fontes")
  }
  execucoes(params: Params) {
    return this.get<Page<ExecucaoOut>>("/fontes/execucoes", params)
  }
  matches(params: Params) {
    return this.get<Page<MatchPendenteOut>>("/matches-pendentes", params)
  }

  // emendas
  emendas(params: Params) {
    return this.get<Page<EmendaOut>>("/emendas", params)
  }
  emendasResumo(params: Params) {
    return this.get<ResumoEmendas>("/emendas/resumo", params)
  }
  emendasFavorecidos(params: Params) {
    return this.get<Page<FavorecidoOut>>("/emendas/favorecidos", params)
  }
  emenda(codigo: string) {
    return this.get<EmendaDetalhe>(`/emendas/${encodeURIComponent(codigo)}`)
  }
  transferenciasEspeciais(params: Params) {
    return this.get<Page<TransferenciaEspecialOut>>("/emendas/transferencias-especiais", params)
  }

  // obras e convênios
  obras(params: Params) {
    return this.get<Page<ObraOut>>("/obras", params)
  }
  obrasResumo(params: Params) {
    return this.get<ResumoObras>("/obras/resumo", params)
  }
  obrasMapa(params: Params) {
    return this.get<PontoObra[]>("/obras/mapa", params)
  }
  obra(numero: number | string) {
    return this.get<ObraDetalhe>(`/obras/${numero}`)
  }

  // alertas
  alertas(params: Params) {
    return this.get<Page<AlertaOut>>("/alertas", params)
  }
  alerta(id: number | string) {
    return this.get<AlertaOut>(`/alertas/${id}`)
  }
  alertasDetectores() {
    return this.get<Detectores>("/alertas/detectores")
  }
  alertasRanking(params: Params) {
    return this.get<Ranking>("/alertas/ranking", params)
  }

  // presidência
  presidentes() {
    return this.get<PresidenteGastos[]>("/presidencia/presidentes")
  }
  presidenciaGastos(params: Params) {
    return this.get<Page<GastoPresidenciaOut>>("/presidencia/gastos", params)
  }
  presidenciaResumo(params: Params) {
    return this.get<ResumoPresidencia>("/presidencia/resumo", params)
  }

  /** Grafo centrado num nó: "politico:ID", "doc:CNPJ", "municipio:CODIGO_IBGE" ou "obra:NUMERO". */
  grafo(no: string, params: Params) {
    const i = no.indexOf(":")
    const rota = (
      { politico: "politico", doc: "documento", municipio: "municipio", obra: "obra" } as const
    )[no.slice(0, i) as "politico" | "doc" | "municipio" | "obra"]
    if (!rota) return Promise.reject(new ApiError(400, "nó inválido"))
    return this.get<Grafo>(`/grafo/${rota}/${encodeURIComponent(no.slice(i + 1))}`, params)
  }
}

export const api = new OuroborosApi()
