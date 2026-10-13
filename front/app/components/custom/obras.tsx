import { useMemo, useState } from "react"
import { Link, useNavigate } from "react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { IconAlertTriangle } from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import { Badge } from "@/ui/badge"
import { DataTable } from "~/components/custom/data-table"
import { useCursorList } from "~/hooks/use-resource"
import { useApi } from "~/context/api"
import type { ObraOut, Params, PontoObra } from "~/interface/api"
import { formatBRL, formatDate, toNumber } from "~/lib/format"
import { cn } from "~/lib/utils"

/** Mesma regra da API (`parada=true`): obra acompanhada, abaixo de 100%, sem medição há 180+
 * dias ou com vigência vencida ainda em execução. */
export function obraParada(o: ObraOut): boolean {
  const acompanhada = o.percentual_execucao !== null || !!o.ultima_medicao || !!o.obra_id
  if (!acompanhada || toNumber(o.percentual_execucao) >= 100) return false
  const hoje = new Date().toISOString().slice(0, 10)
  const vencida = !!o.fim_vigencia && o.fim_vigencia < hoje && /em execu/i.test(o.situacao ?? "")
  return (o.dias_sem_medicao ?? 0) >= 180 || vencida
}

type Tom = "vermelho" | "verde" | "azul" | "roxo" | "neutro"

function tom(situacao: string | null): Tom {
  const s = (situacao ?? "").toLowerCase()
  if (/rejeitad|inadimpl|rescindid|anulad|cancelad/.test(s)) return "vermelho"
  if (/aprovada|conclu/.test(s)) return "verde"
  if (/execu|assinado/.test(s)) return "azul"
  if (/presta/.test(s)) return "roxo"
  return "neutro"
}

// classes literais: o Tailwind só gera o que aparece no código
const BG: Record<Tom, string> = {
  vermelho: "bg-red-500",
  verde: "bg-emerald-500",
  azul: "bg-sky-500",
  roxo: "bg-violet-500",
  neutro: "bg-muted-foreground/50",
}
const FILL: Record<Tom, string> = {
  vermelho: "fill-red-500",
  verde: "fill-emerald-500",
  azul: "fill-sky-500",
  roxo: "fill-violet-500",
  neutro: "fill-muted-foreground/50",
}

export function corSituacao(situacao: string | null): string {
  return BG[tom(situacao)]
}

export function tituloObra(o: Pick<ObraOut, "obra_nome" | "objeto" | "numero">): string {
  return o.obra_nome ?? o.objeto ?? `#${o.numero}`
}

export function ExecucaoBar({ percentual }: { percentual: string | number | null }) {
  if (percentual === null) return <span className="text-xs text-muted-foreground">—</span>
  const pct = Math.min(100, Math.max(0, toNumber(percentual)))
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
        <div
          className={cn("h-full rounded-full", pct >= 100 ? "bg-emerald-500" : "bg-sky-500")}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs tabular-nums">{pct.toFixed(0)}%</span>
    </div>
  )
}

export function SituacaoObra({ obra }: { obra: ObraOut }) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col gap-1">
      <span className="flex items-center gap-1.5 text-xs">
        <span className={cn("size-2 shrink-0 rounded-full", corSituacao(obra.situacao))} />
        <span className="truncate">{obra.situacao ?? t("obra.semSituacao")}</span>
      </span>
      {obraParada(obra) && (
        <Badge variant="outline" className="w-fit gap-1 border-amber-500/50 text-amber-600 dark:text-amber-400">
          <IconAlertTriangle className="size-3" /> {t("obra.parada")}
        </Badge>
      )}
    </div>
  )
}

export function useObraColumns(): ColumnDef<ObraOut>[] {
  const { t } = useTranslation()
  return useMemo<ColumnDef<ObraOut>[]>(
    () => [
      {
        id: "obra",
        accessorFn: tituloObra,
        header: t("obra.obra"),
        cell: ({ row }) => (
          <div className="max-w-80">
            <Link
              to={`/obras/${row.original.numero}`}
              className="line-clamp-2 font-medium hover:underline"
              title={row.original.objeto ?? ""}
              onClick={(e) => e.stopPropagation()}
            >
              {tituloObra(row.original)}
            </Link>
            <p className="text-[11px] text-muted-foreground">
              {t("obra.convenio")} {row.original.numero} · {row.original.ano}
              {row.original.orgao_superior && ` · ${row.original.orgao_superior}`}
            </p>
          </div>
        ),
      },
      {
        id: "local",
        accessorFn: (o) => o.municipio_nome ?? "",
        header: t("obra.local"),
        meta: { className: "max-md:hidden" },
        cell: ({ row }) => (
          <div className="max-w-44">
            {row.original.municipio_codigo_ibge ? (
              <Link
                to={`/entes/${row.original.municipio_codigo_ibge}`}
                className="block truncate hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                {row.original.municipio_nome} - {row.original.uf}
              </Link>
            ) : (
              <p className="truncate">{row.original.uf ?? "—"}</p>
            )}
            <p className="truncate text-[11px] text-muted-foreground" title={row.original.proponente_nome ?? ""}>
              {row.original.proponente_nome}
            </p>
          </div>
        ),
      },
      {
        id: "situacao",
        accessorKey: "situacao",
        header: t("obra.situacao"),
        cell: ({ row }) => (
          <div className="max-w-48">
            <SituacaoObra obra={row.original} />
          </div>
        ),
      },
      {
        id: "execucao",
        accessorFn: (o) => toNumber(o.percentual_execucao),
        header: t("obra.execucao"),
        meta: { className: "max-lg:hidden" },
        cell: ({ row }) => (
          <div>
            <ExecucaoBar percentual={row.original.percentual_execucao} />
            <p className="mt-0.5 text-[11px] text-muted-foreground tabular-nums">
              {formatDate(row.original.inicio_vigencia)} – {formatDate(row.original.fim_vigencia)}
            </p>
          </div>
        ),
      },
      {
        id: "valor",
        accessorFn: (o) => toNumber(o.valor_global),
        header: t("obra.valorGlobal"),
        meta: { className: "text-right" },
        cell: ({ row }) => (
          <div className="text-right tabular-nums">
            <p className="font-medium">{formatBRL(row.original.valor_global, true)}</p>
            <p className="text-[11px] text-muted-foreground">
              {t("obra.liberado")} {formatBRL(row.original.valor_desembolsado, true)}
            </p>
          </div>
        ),
      },
    ],
    [t],
  )
}

/** Tabela paginada de obras com qualquer filtro da API (`politico`, `municipio`, `fornecedor`...). */
export function ObrasTable({ params, deps }: { params: Params; deps: unknown[] }) {
  const api = useApi()
  const navigate = useNavigate()
  const columns = useObraColumns()
  const list = useCursorList((cursor) => api.obras({ ...params, cursor, limit: 50 }), deps)
  return (
    <DataTable
      columns={columns}
      data={list.items}
      loading={list.loading}
      error={list.error}
      onRetry={list.reload}
      hasMore={list.hasMore}
      onLoadMore={list.loadMore}
      onRowClick={(o) => navigate(`/obras/${o.numero}`)}
    />
  )
}

// limites do Brasil (com folga), para projetar lat/long num SVG
const LON = [-74.5, -28.5]
const LAT = [5.5, -34]

/** Mapa de pontos sem dependência de tiles: cada obra é um círculo (área ~ valor, cor ~ situação). */
export function ObrasMapa({ pontos, height = 420 }: { pontos: PontoObra[]; height?: number }) {
  const navigate = useNavigate()
  const [hover, setHover] = useState<PontoObra | null>(null)
  const largura = LON[1] - LON[0]
  const altura = LAT[0] - LAT[1]
  const maior = Math.max(1, ...pontos.map((p) => toNumber(p.valor_global)))
  return (
    <div className="relative" style={{ height }}>
      <svg viewBox={`0 0 ${largura} ${altura}`} className="size-full" preserveAspectRatio="xMidYMid meet">
        <rect width={largura} height={altura} className="fill-muted/30" rx={0.6} />
        {pontos.map((p) => {
          const x = toNumber(p.longitude) - LON[0]
          const y = LAT[0] - toNumber(p.latitude)
          const r = 0.12 + 0.55 * Math.sqrt(toNumber(p.valor_global) / maior)
          return (
            <circle
              key={p.numero}
              cx={x}
              cy={y}
              r={r}
              className={cn(
                "cursor-pointer stroke-background opacity-70 transition-opacity hover:opacity-100",
                FILL[tom(p.situacao)],
              )}
              strokeWidth={0.04}
              onMouseEnter={() => setHover(p)}
              onMouseLeave={() => setHover(null)}
              onClick={() => navigate(`/obras/${p.numero}`)}
            />
          )
        })}
      </svg>
      {hover && (
        <div className="pointer-events-none absolute top-2 left-2 max-w-72 rounded-md border bg-popover p-2 text-xs shadow-md">
          <p className="font-medium">{hover.rotulo}</p>
          <p className="text-muted-foreground">
            {hover.situacao ?? "—"} · {formatBRL(hover.valor_global, true)}
            {hover.percentual_execucao !== null && ` · ${toNumber(hover.percentual_execucao).toFixed(0)}%`}
          </p>
        </div>
      )}
    </div>
  )
}
