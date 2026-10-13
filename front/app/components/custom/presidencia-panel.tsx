import { useMemo } from "react"
import type { ColumnDef } from "@tanstack/react-table"
import { useTranslation } from "react-i18next"

import { Badge } from "@/ui/badge"
import { SimpleBarChart } from "~/components/charts/bar-chart"
import { ChartCard } from "~/components/charts/chart-card"
import { DataTable } from "~/components/custom/data-table"
import { ExportButton } from "~/components/custom/filters"
import { KpiGrid } from "~/components/custom/kpi"
import { useApi } from "~/context/api"
import { useCursorList, useResource } from "~/hooks/use-resource"
import type { GastoPresidenciaOut, Params, TotalRotulo } from "~/interface/api"
import { formatBRL, formatDate, formatInt, monthLabel, toNumber } from "~/lib/format"

const brl = (v: number) => formatBRL(v, true)

function Ranking({ titulo, itens, loading }: { titulo: string; itens: TotalRotulo[]; loading: boolean }) {
  return (
    <ChartCard title={titulo} loading={loading} isEmpty={!itens.length} height={340}>
      <ol className="divide-y text-sm">
        {itens.slice(0, 12).map((item, i) => (
          <li key={`${item.chave}-${i}`} className="flex items-center gap-3 py-1.5">
            <span className="w-5 text-right text-xs text-muted-foreground">{i + 1}</span>
            <span className="min-w-0 flex-1 truncate" title={item.chave ?? ""}>
              {item.chave ?? "—"}
            </span>
            <span className="text-xs text-muted-foreground">{formatInt(item.quantidade)}x</span>
            <span className="w-24 text-right font-medium tabular-nums">{formatBRL(item.total, true)}</span>
          </li>
        ))}
      </ol>
    </ChartCard>
  )
}

/** Resumo + lançamentos do cartão da Presidência para os filtros dados. */
export function PresidenciaPanel({ params, mostrarPresidente = true }: { params: Params; mostrarPresidente?: boolean }) {
  const { t } = useTranslation()
  const api = useApi()
  const chave = JSON.stringify(params)
  const resumo = useResource(() => api.presidenciaResumo(params), [chave])
  const list = useCursorList((cursor) => api.presidenciaGastos({ ...params, cursor, limit: 50 }), [chave])
  const r = resumo.data

  const columns = useMemo<ColumnDef<GastoPresidenciaOut>[]>(
    () => [
      {
        id: "data",
        accessorFn: (g) => g.data ?? `${g.ano}-${String(g.mes).padStart(2, "0")}`,
        header: t("presidencia.data"),
        cell: ({ row }) => (
          <span className="whitespace-nowrap text-xs">
            {row.original.data ? formatDate(row.original.data) : monthLabel(row.original.ano, row.original.mes)}
          </span>
        ),
      },
      ...(mostrarPresidente
        ? [
            {
              id: "presidente",
              accessorKey: "presidente",
              header: t("presidencia.presidente"),
              cell: ({ getValue }) => <span className="text-xs">{getValue<string>() ?? "—"}</span>,
            } satisfies ColumnDef<GastoPresidenciaOut>,
          ]
        : []),
      {
        id: "favorecido",
        accessorKey: "favorecido_nome",
        header: t("presidencia.favorecido"),
        cell: ({ row }) =>
          row.original.favorecido_nome ?? <span className="text-muted-foreground">{t("presidencia.sigiloso")}</span>,
      },
      {
        id: "categoria",
        accessorFn: (g) => g.categoria ?? g.transacao,
        header: t("presidencia.categoria"),
        cell: ({ getValue }) => <span className="text-xs text-muted-foreground">{getValue<string>() ?? "—"}</span>,
      },
      {
        id: "tipo",
        accessorKey: "tipo",
        header: t("presidencia.tipo"),
        cell: ({ row }) => (
          <div className="flex gap-1">
            {row.original.tipo === "saque" && (
              <Badge variant="outline" className="border-amber-500/50 text-amber-700 dark:text-amber-400">
                {t("presidencia.saque")}
              </Badge>
            )}
            {row.original.sigiloso && !row.original.data && (
              <Badge variant="outline">{t("presidencia.sigiloso")}</Badge>
            )}
          </div>
        ),
      },
      {
        id: "valor",
        accessorFn: (g) => toNumber(g.valor),
        header: t("common.valor"),
        cell: ({ row }) => <span className="whitespace-nowrap tabular-nums">{formatBRL(row.original.valor)}</span>,
      },
    ],
    [t, mostrarPresidente],
  )

  return (
    <div className="flex flex-col gap-4">
      <KpiGrid
        loading={resumo.loading}
        items={[
          { title: t("presidencia.total"), value: formatBRL(r?.total, true), hint: t("presidencia.lancamentos", { count: r?.quantidade ?? 0 }) },
          { title: t("presidencia.saques"), value: formatBRL(r?.saques, true), hint: t("presidencia.saquesHint") },
          { title: t("presidencia.aindaSigiloso"), value: formatBRL(r?.sigiloso, true), hint: t("presidencia.aindaSigilosoHint") },
          {
            title: t("presidencia.maiorCategoria"),
            value: <span className="text-base">{r?.por_categoria[0]?.chave ?? "—"}</span>,
            hint: r?.por_categoria[0] ? formatBRL(r.por_categoria[0].total, true) : undefined,
          },
        ]}
      />
      {r && <p className="text-xs text-muted-foreground">{r.aviso}</p>}
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title={t("presidencia.porAno")} loading={resumo.loading} isEmpty={!r?.por_ano.length}>
          <SimpleBarChart
            label={t("common.valor")}
            valueFormatter={brl}
            data={(r?.por_ano ?? []).map((a) => ({ name: a.chave ?? "—", value: toNumber(a.total) }))}
          />
        </ChartCard>
        <ChartCard title={t("presidencia.porCategoria")} loading={resumo.loading} isEmpty={!r?.por_categoria.length}>
          <SimpleBarChart
            layout="horizontal"
            colorful
            label={t("common.valor")}
            valueFormatter={brl}
            data={(r?.por_categoria ?? [])
              .filter((c) => c.chave)
              .slice(0, 10)
              .map((c) => ({ name: c.chave ?? "—", value: toNumber(c.total) }))}
          />
        </ChartCard>
        <Ranking titulo={t("presidencia.maioresFavorecidos")} itens={r?.maiores_favorecidos ?? []} loading={resumo.loading} />
        <Ranking
          titulo={t("presidencia.porUnidade")}
          itens={(r?.por_unidade ?? []).map((u) => ({ ...u, chave: u.chave ?? t("presidencia.semUnidade") }))}
          loading={resumo.loading}
        />
      </div>
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">{t("presidencia.lancamentosTitulo")}</h2>
        <ExportButton onExport={() => api.exportCsv("/presidencia/gastos", params, "gastos_presidencia")} />
      </div>
      <DataTable
        columns={columns}
        data={list.items}
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        hasMore={list.hasMore}
        onLoadMore={list.loadMore}
      />
    </div>
  )
}
