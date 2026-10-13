import { useEffect, useMemo, useState } from "react"
import { Link, useSearchParams } from "react-router"
import {
  Background,
  BackgroundVariant,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  useNodesInitialized,
  useReactFlow,
  type Edge,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import {
  IconArrowsMaximize,
  IconArrowsMinimize,
  IconChevronRight,
  IconExternalLink,
  IconFocusCentered,
  IconInfoCircle,
  IconLoader2,
  IconSearch,
  IconX,
} from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import { Avatar, AvatarFallback, AvatarImage } from "@/ui/avatar"
import { Button } from "@/ui/button"
import { Card, CardContent } from "@/ui/card"
import { Input } from "@/ui/input"
import { explicar } from "~/components/grafo/explain"
import { caminho, radialLayout } from "~/components/grafo/layout"
import {
  edgeTypes,
  nodeTypes,
  type EdgeData,
  type GraphNode,
} from "~/components/grafo/nodes"
import { GRUPO, exploravel, iconFor, paginaDe } from "~/components/grafo/style"
import { SelectFilter, yearOptions } from "~/components/custom/filters"
import { PoliticoAvatar } from "~/components/custom/politico-avatar"
import { EmptyState, ErrorState } from "~/components/custom/states"
import { useTheme } from "~/components/provider/theme"
import { useApi } from "~/context/api"
import { usePageTitle } from "~/context/page"
import { useResource } from "~/hooks/use-resource"
import type { Grafo, GrafoGrupo, GrafoNo, PoliticoResumo } from "~/interface/api"
import { formatBRL, initials, toNumber } from "~/lib/format"
import { cn } from "~/lib/utils"

const GRUPOS: GrafoGrupo[] = ["carreira", "gastos", "emendas", "obras", "conexoes"]

// ---------------------------------------------------------------- busca de ponto de partida

function Picker({ onPick, autoFocus }: { onPick: (no: string) => void; autoFocus?: boolean }) {
  const { t } = useTranslation()
  const api = useApi()
  const [termo, setTermo] = useState("")
  const [aberto, setAberto] = useState(false)
  const [itens, setItens] = useState<PoliticoResumo[]>([])
  const cnpj = termo.replace(/\D/g, "")

  useEffect(() => {
    if (termo.trim().length < 3 || cnpj.length === 14) {
      setItens([])
      return
    }
    let ativo = true
    const id = window.setTimeout(() => {
      api
        .politicos({ busca: termo.trim(), limit: 8 })
        .then((p) => ativo && setItens(p.items))
        .catch(() => ativo && setItens([]))
    }, 250)
    return () => {
      ativo = false
      window.clearTimeout(id)
    }
  }, [termo, cnpj, api])

  const escolher = (no: string) => {
    onPick(no)
    setTermo("")
    setAberto(false)
  }

  return (
    <div className="relative w-full sm:w-80">
      <IconSearch className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        autoFocus={autoFocus}
        value={termo}
        onChange={(e) => {
          setTermo(e.target.value)
          setAberto(true)
        }}
        onFocus={() => setAberto(true)}
        onBlur={() => window.setTimeout(() => setAberto(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && cnpj.length === 14) escolher(`doc:${cnpj}`)
        }}
        placeholder={t("grafo.buscar")}
        className="h-9 pl-8"
      />
      {aberto && (itens.length > 0 || cnpj.length === 14) && (
        <div className="absolute top-full z-50 mt-1 w-full overflow-hidden rounded-lg border bg-popover shadow-lg">
          {cnpj.length === 14 && (
            <button
              type="button"
              onMouseDown={() => escolher(`doc:${cnpj}`)}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-accent"
            >
              {t("grafo.abrirCnpj", { cnpj })}
            </button>
          )}
          {itens.map((p) => (
            <button
              key={p.id}
              type="button"
              onMouseDown={() => escolher(`politico:${p.id}`)}
              className="flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-accent"
            >
              <PoliticoAvatar politico={p} className="size-7" />
              <span className="min-w-0 flex-1 truncate">{p.nome}</span>
              <span className="text-xs text-muted-foreground">
                {p.ultimo_mandato?.partido_sigla ?? ""} {p.ultimo_mandato?.uf ?? ""}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- tela inicial

function Inicio({ onPick }: { onPick: (no: string) => void }) {
  const { t } = useTranslation()
  const api = useApi()
  const sugestoes = useResource(() => api.emendasResumo({ ano: new Date().getFullYear() - 1 }), [])
  const autores = (sugestoes.data?.maiores_autores ?? []).filter((a) => a.chave).slice(0, 8)

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col items-center gap-8 py-10 text-center">
      <div className="space-y-3">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("grafo.heroTitulo")}</h1>
        <p className="text-muted-foreground">{t("grafo.heroTexto")}</p>
      </div>
      <Picker onPick={onPick} autoFocus />
      <div className="grid w-full gap-3 text-left sm:grid-cols-2 lg:grid-cols-4">
        {(["gastos", "emendas", "obras", "conexoes"] as const).map((g) => (
          <Card key={g} className="gap-2 py-4 shadow-xs">
            <CardContent className="space-y-1 px-4">
              <p className="flex items-center gap-2 text-sm font-semibold">
                <span className={cn("size-2.5 rounded-full", GRUPO[g].dot)} />
                {t(`grafo.grupos.${g}`)}
              </p>
              <p className="text-xs text-muted-foreground">{t(`grafo.heroGrupos.${g}`)}</p>
            </CardContent>
          </Card>
        ))}
      </div>
      {autores.length > 0 && (
        <div className="w-full space-y-3">
          <p className="text-sm font-medium text-muted-foreground">{t("grafo.sugestoes")}</p>
          <div className="flex flex-wrap justify-center gap-2">
            {autores.map((a) => (
              <Button
                key={a.chave}
                variant="outline"
                size="sm"
                className="rounded-full"
                onClick={() => onPick(`politico:${a.chave}`)}
              >
                {a.rotulo}
                <span className="text-xs text-muted-foreground">{formatBRL(a.pago, true)}</span>
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- painel lateral

function Painel({
  grafo,
  selecionado,
  onSelect,
  onExplore,
}: {
  grafo: Grafo
  selecionado: GrafoNo | undefined
  onSelect: (id: string | null) => void
  onExplore: (no: string, rotulo: string) => void
}) {
  const { t } = useTranslation()
  const api = useApi()
  const byId = useMemo(() => new Map(grafo.nos.map((n) => [n.id, n])), [grafo])
  const centro = byId.get(grafo.centro)!

  if (selecionado) {
    const Icon = iconFor(selecionado)
    const alvo = exploravel(selecionado)
    const pagina = paginaDe(selecionado)
    const filhos = grafo.nos
      .filter((n) => n.pai === selecionado.id)
      .sort((a, b) => toNumber(b.valor) - toNumber(a.valor))
    return (
      <div className="flex flex-col gap-4">
        <div className="flex items-start gap-3">
          {selecionado.imagem ? (
            <Avatar className="size-12">
              <AvatarImage src={api.url(selecionado.imagem)} className="object-cover" />
              <AvatarFallback>{initials(selecionado.rotulo)}</AvatarFallback>
            </Avatar>
          ) : (
            <span
              className={cn(
                "flex size-12 shrink-0 items-center justify-center rounded-xl",
                GRUPO[selecionado.grupo].chip,
              )}
            >
              <Icon className="size-6" />
            </span>
          )}
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              {t(`grafo.tipos.${selecionado.tipo}`)}
            </p>
            <p className="leading-tight font-semibold">{selecionado.rotulo}</p>
            {selecionado.detalhe && (
              <p className="text-xs text-muted-foreground">{selecionado.detalhe}</p>
            )}
          </div>
          <Button size="icon" variant="ghost" className="size-7" onClick={() => onSelect(null)}>
            <IconX />
          </Button>
        </div>
        {selecionado.valor !== null && (
          <p className="text-3xl font-bold tracking-tight tabular-nums">
            {formatBRL(selecionado.valor)}
          </p>
        )}
        <p className="rounded-lg bg-muted/60 p-3 text-sm leading-relaxed">
          {explicar(selecionado, grafo, t)}
        </p>
        <div className="flex flex-wrap gap-2">
          {alvo && alvo !== grafo.centro && (
            <Button size="sm" onClick={() => onExplore(alvo, selecionado.rotulo)}>
              <IconArrowsMaximize /> {t("grafo.explorar")}
            </Button>
          )}
          {pagina && (
            <Button size="sm" variant="outline" asChild>
              <Link to={pagina}>
                <IconExternalLink /> {t("grafo.abrirPagina")}
              </Link>
            </Button>
          )}
        </div>
        {filhos.length > 0 && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">{t("grafo.ligacoes")}</p>
            {filhos.map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => onSelect(f.id)}
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-accent"
              >
                <span className={cn("size-2 shrink-0 rounded-full", GRUPO[f.grupo].dot)} />
                <span className="min-w-0 flex-1 truncate">{f.rotulo}</span>
                {f.valor !== null && (
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {formatBRL(f.valor, true)}
                  </span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>
    )
  }

  // Sem seleção: resumo em frases + como ler
  const hubs = grafo.nos.filter((n) => n.tipo === "hub")
  return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {t("grafo.resumo")}
        </p>
        <p className="mt-1 text-sm leading-relaxed">{explicar(centro, grafo, t)}</p>
      </div>
      {hubs.map((h) => {
        const destaques = grafo.nos
          .filter((n) => caminho(byId, n.id).includes(h.id) && n.id !== h.id && n.valor !== null)
          .filter((n) => n.tipo !== "categoria" && n.tipo !== "area")
          .sort((a, b) => toNumber(b.valor) - toNumber(a.valor))
          .slice(0, 3)
        return (
          <div key={h.id} className="space-y-1.5">
            <button
              type="button"
              onClick={() => onSelect(h.id)}
              className="flex w-full items-center gap-2 text-left text-sm font-semibold hover:underline"
            >
              <span className={cn("size-2.5 rounded-full", GRUPO[h.grupo].dot)} />
              {h.rotulo}
              {h.valor !== null && (
                <span className="ml-auto text-xs font-medium text-muted-foreground tabular-nums">
                  {formatBRL(h.valor, true)}
                </span>
              )}
            </button>
            {destaques.map((d) => (
              <button
                key={d.id}
                type="button"
                onClick={() => onSelect(d.id)}
                className="block w-full rounded-md px-2 py-1 text-left text-xs leading-relaxed text-muted-foreground hover:bg-accent hover:text-foreground"
              >
                {explicar(d, grafo, t)}
              </button>
            ))}
          </div>
        )
      })}
      <div className="rounded-lg border border-dashed p-3 text-xs leading-relaxed text-muted-foreground">
        <p className="mb-1 flex items-center gap-1 font-medium text-foreground">
          <IconInfoCircle className="size-4" /> {t("grafo.comoLer")}
        </p>
        <ul className="list-disc space-y-0.5 pl-4">
          <li>{t("grafo.dica1")}</li>
          <li>{t("grafo.dica2")}</li>
          <li>{t("grafo.dica3")}</li>
        </ul>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- canvas

function Canvas({
  grafo,
  ocultos,
  abertos,
  selecionado,
  onSelect,
  onToggle,
  onExplore,
}: {
  grafo: Grafo
  ocultos: Set<GrafoGrupo>
  abertos: Set<string>
  selecionado: string | null
  onSelect: (id: string | null) => void
  onToggle: (id: string) => void
  onExplore: (no: string, rotulo: string) => void
}) {
  const api = useApi()
  const { theme } = useTheme()
  const flow = useReactFlow()
  const [hover, setHover] = useState<string | null>(null)

  const byId = useMemo(() => new Map(grafo.nos.map((n) => [n.id, n])), [grafo])

  // visível: grupo ligado, ancestrais visíveis e, do nível 2 em diante, pai aberto
  const visiveis = useMemo(() => {
    const ok = new Set<string>([grafo.centro])
    for (const n of [...grafo.nos].sort((a, b) => a.nivel - b.nivel)) {
      if (n.id === grafo.centro || ocultos.has(n.grupo)) continue
      const pai = n.pai ?? grafo.centro
      if (!ok.has(pai)) continue
      if (n.nivel >= 2 && !abertos.has(pai)) continue
      ok.add(n.id)
    }
    return grafo.nos.filter((n) => ok.has(n.id))
  }, [grafo, ocultos, abertos])

  // quantos filhos cada nó esconde (badge "+N")
  const escondidos = useMemo(() => {
    const vis = new Set(visiveis.map((n) => n.id))
    const out = new Map<string, number>()
    for (const n of grafo.nos) {
      if (!n.pai || vis.has(n.id) || ocultos.has(n.grupo)) continue
      out.set(n.pai, (out.get(n.pai) ?? 0) + 1)
    }
    return out
  }, [grafo, visiveis, ocultos])
  const temFilhos = useMemo(() => new Set(grafo.nos.map((n) => n.pai)), [grafo])

  const posicoes = useMemo(() => radialLayout(visiveis, grafo.centro), [visiveis, grafo.centro])

  const foco = hover ?? selecionado
  const realce = useMemo(() => {
    if (!foco) return null
    const s = new Set(caminho(byId, foco))
    for (const n of visiveis) if (n.pai === foco) s.add(n.id)
    return s
  }, [foco, byId, visiveis])

  const nodes = useMemo<GraphNode[]>(
    () =>
      visiveis.map((n) => ({
        id: n.id,
        type: n.id === grafo.centro ? "center" : n.tipo === "hub" ? "hub" : "entity",
        position: posicoes.get(n.id) ?? { x: 0, y: 0 },
        data: {
          no: n,
          imagem: n.imagem ? api.url(n.imagem) : null,
          centro: n.id === grafo.centro,
          dim: !!realce && !realce.has(n.id),
          selected: n.id === selecionado,
          mais: escondidos.get(n.id) ?? 0,
        },
      })),
    [visiveis, posicoes, realce, selecionado, grafo.centro, api, escondidos],
  )

  const edges = useMemo<Edge[]>(() => {
    const ids = new Set(visiveis.map((n) => n.id))
    const maxValor = Math.max(1, ...grafo.arestas.map((a) => Math.abs(toNumber(a.valor))))
    return grafo.arestas
      .filter((a) => ids.has(a.origem) && ids.has(a.destino))
      .map((a) => {
        const v = a.valor !== null ? Math.abs(toNumber(a.valor)) : null
        const destino = byId.get(a.destino)!
        const destaque = !!realce && realce.has(a.origem) && realce.has(a.destino)
        const data: EdgeData = {
          valor: v,
          cor: GRUPO[destino.grupo].stroke,
          largura: v ? 1.5 + 7 * (Math.log1p(v) / Math.log1p(maxValor)) ** 3 : 1.5,
          dim: !!realce && !destaque,
          destaque,
          rotulo: a.valor !== null ? formatBRL(a.valor, true) : null,
        }
        return { id: a.id, source: a.origem, target: a.destino, type: "money", data }
      })
  }, [grafo, visiveis, realce, byId])

  // enquadra quando os nós já têm tamanho medido (grafo novo ou grupos ligados/desligados)
  const medidos = useNodesInitialized()
  useEffect(() => {
    if (!medidos) return
    const id = window.setTimeout(() => flow.fitView({ padding: 0.08, duration: 500 }), 30)
    return () => window.clearTimeout(id)
  }, [medidos, grafo, ocultos, abertos, flow])

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      nodeOrigin={[0.5, 0.5]}
      fitView
      fitViewOptions={{ padding: 0.08 }}
      colorMode={theme}
      minZoom={0.1}
      maxZoom={2}
      nodesConnectable={false}
      proOptions={{ hideAttribution: true }}
      onNodeMouseEnter={(_, n) => setHover(n.id)}
      onNodeMouseLeave={() => setHover(null)}
      onNodeClick={(_, n) => {
        onSelect(n.id)
        if (n.id !== grafo.centro && temFilhos.has(n.id)) {
          onToggle(n.id)
        }
      }}
      onNodeDoubleClick={(_, n) => {
        const no = byId.get(n.id)
        const alvo = no && exploravel(no)
        if (no && alvo && alvo !== grafo.centro) onExplore(alvo, no.rotulo)
      }}
      onPaneClick={() => onSelect(null)}
    >
      <Background variant={BackgroundVariant.Dots} gap={24} size={1.2} />
      <Controls showInteractive={false} />
    </ReactFlow>
  )
}

// ---------------------------------------------------------------- página

interface Passo {
  no: string
  rotulo: string
}

export default function GrafoPage() {
  const { t } = useTranslation()
  const api = useApi()
  const [params, setParams] = useSearchParams()
  const no = params.get("no") ?? ""
  const ano = params.get("ano") ?? ""
  const [ocultos, setOcultos] = useState<Set<GrafoGrupo>>(new Set())
  const [selecionado, setSelecionado] = useState<string | null>(null)
  const [abertos, setAbertos] = useState<Set<string>>(new Set())
  const [trilha, setTrilha] = useState<Passo[]>([])

  const grafo = useResource(() => api.grafo(no, { ano: ano || undefined }), [no, ano], {
    enabled: !!no,
  })
  const g = grafo.data
  const centro = g?.nos.find((n) => n.id === g.centro)
  usePageTitle(t("navigation.grafo"), centro?.rotulo)

  // começa com os temas de dinheiro abertos; carreira e detalhes abrem com um clique
  useEffect(() => setSelecionado(null), [no])
  useEffect(() => {
    if (!g) return
    setAbertos(new Set(g.nos.filter((n) => n.tipo === "hub" && n.grupo !== "carreira").map((n) => n.id)))
  }, [g])

  const alternar = (id: string) =>
    setAbertos((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  // seleciona pelo painel: abre os ancestrais para o nó aparecer no mapa
  const revelar = (id: string | null) => {
    setSelecionado(id)
    if (!id || !g) return
    const byId = new Map(g.nos.map((n) => [n.id, n]))
    setAbertos((prev) => new Set([...prev, ...caminho(byId, id).slice(1)]))
  }
  const tudoAberto = !!g && g.nos.every((n) => !n.pai || n.nivel < 2 || abertos.has(n.pai))
  // trilha: adiciona o centro atual quando o grafo chega
  useEffect(() => {
    if (!centro || !g) return
    setTrilha((prev) => {
      const i = prev.findIndex((p) => p.no === no)
      if (i >= 0) return prev.slice(0, i + 1)
      return [...prev, { no, rotulo: centro.rotulo }].slice(-8)
    })
  }, [centro, g, no])

  const abrir = (alvo: string) => {
    const next = new URLSearchParams(params)
    next.set("no", alvo)
    setParams(next)
  }
  const set = (patch: Record<string, string>) => {
    const next = new URLSearchParams(params)
    for (const [k, v] of Object.entries(patch)) (v ? next.set(k, v) : next.delete(k))
    setParams(next, { replace: true })
  }
  const toggle = (grupo: GrafoGrupo) =>
    setOcultos((prev) => {
      const next = new Set(prev)
      if (next.has(grupo)) next.delete(grupo)
      else next.add(grupo)
      return next
    })

  if (!no) return <Inicio onPick={abrir} />

  const presentes = new Set(g?.nos.map((n) => n.grupo))

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Picker onPick={abrir} />
        <SelectFilter
          value={ano}
          onChange={(v) => set({ ano: v })}
          placeholder={t("filters.ano")}
          options={yearOptions(2014)}
        />
        <div className="flex flex-wrap items-center gap-1.5">
          {GRUPOS.filter((gr) => presentes.has(gr)).map((gr) => (
            <button
              key={gr}
              type="button"
              onClick={() => toggle(gr)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                ocultos.has(gr) ? "text-muted-foreground opacity-60" : "bg-card shadow-xs",
              )}
            >
              <span className={cn("size-2 rounded-full", ocultos.has(gr) ? "bg-muted-foreground" : GRUPO[gr].dot)} />
              {t(`grafo.grupos.${gr}`)}
            </button>
          ))}
        </div>
        {g && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() =>
              setAbertos(tudoAberto ? new Set() : new Set(g.nos.map((n) => n.pai ?? "")))
            }
          >
            {tudoAberto ? <IconArrowsMinimize /> : <IconArrowsMaximize />}
            {tudoAberto ? t("grafo.recolher") : t("grafo.expandirTudo")}
          </Button>
        )}
        {grafo.loading && <IconLoader2 className="size-4 animate-spin text-muted-foreground" />}
      </div>

      {trilha.length > 1 && (
        <nav className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
          {trilha.map((p, i) => (
            <span key={p.no} className="inline-flex items-center gap-1">
              {i > 0 && <IconChevronRight className="size-3" />}
              <button
                type="button"
                onClick={() => abrir(p.no)}
                className={cn("hover:text-foreground hover:underline", p.no === no && "font-semibold text-foreground")}
              >
                {p.rotulo}
              </button>
            </span>
          ))}
        </nav>
      )}

      {grafo.error ? (
        <ErrorState error={grafo.error} onRetry={grafo.reload} />
      ) : (
        <div className="grid gap-3 lg:grid-cols-[1fr_22rem]">
          <div className="relative h-[calc(100svh-var(--header-height)-11rem)] min-h-[520px] overflow-hidden rounded-xl border bg-card/40">
            {g ? (
              <ReactFlowProvider>
                <Canvas
                  grafo={g}
                  ocultos={ocultos}
                  abertos={abertos}
                  selecionado={selecionado}
                  onSelect={setSelecionado}
                  onToggle={alternar}
                  onExplore={(alvo) => abrir(alvo)}
                />
              </ReactFlowProvider>
            ) : (
              <div className="flex h-full items-center justify-center">
                <IconLoader2 className="size-8 animate-spin text-muted-foreground" />
              </div>
            )}
            {g && (
              <div className="pointer-events-none absolute top-3 left-3 flex items-center gap-1.5 rounded-full border bg-background/90 px-3 py-1 text-[11px] text-muted-foreground shadow-xs backdrop-blur">
                <IconFocusCentered className="size-3.5" /> {t("grafo.dicaCanvas")}
              </div>
            )}
          </div>
          <Card className="gap-0 py-4 shadow-xs lg:max-h-[calc(100svh-var(--header-height)-11rem)] lg:overflow-y-auto">
            <CardContent className="px-4">
              {g ? (
                <Painel
                  grafo={g}
                  selecionado={selecionado ? g.nos.find((n) => n.id === selecionado) : undefined}
                  onSelect={revelar}
                  onExplore={(alvo) => abrir(alvo)}
                />
              ) : (
                <EmptyState title={t("common.loading")} className="border-none" />
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
