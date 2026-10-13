import { useMemo } from "react"
import { Link } from "react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { IconExternalLink, IconFileInvoice } from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import { SimpleBarChart } from "~/components/charts/bar-chart"
import { TimeAreaChart } from "~/components/charts/area-chart"
import { ChartCard } from "~/components/charts/chart-card"
import { DataTable } from "~/components/custom/data-table"
import { VerbaBadge } from "~/components/custom/labels"
import type { DespesaOut, Page, ResumoDespesas } from "~/interface/api"
import { useCursorList, type Resource } from "~/hooks/use-resource"
import { formatBRL, formatDate, formatDocumento, monthLabel, toNumber } from "~/lib/format"
import { cn } from "~/lib/utils"

export function useDespesaColumns({ showParlamentar = true }: { showParlamentar?: boolean } = {}) {
  const { t } = useTranslation()
  return useMemo<ColumnDef<DespesaOut>[]>(() => {
    const cols: ColumnDef<DespesaOut>[] = [
      {
        id: "data",
        accessorFn: (d) => d.data_emissao ?? `${d.ano}-${String(d.mes).padStart(2, "0")}`,
        header: t("despesa.data"),
        cell: ({ row }) => (
          <span className="text-xs whitespace-nowrap tabular-nums">
            {row.original.data_emissao
              ? formatDate(row.original.data_emissao)
              : `${String(row.original.mes).padStart(2, "0")}/${row.original.ano}`}
          </span>
        ),
      },
    ]
    if (showParlamentar) {
      cols.push({
        id: "parlamentar",
        accessorKey: "parlamentar_nome",
        header: t("despesa.parlamentar"),
        cell: ({ row }) => {
          const d = row.original
          const label = (
            <span className="font-medium">
              {d.parlamentar_nome}
              <span className="ml-1 text-xs font-normal text-muted-foreground">
                {d.partido_sigla ?? ""}
                {d.uf ? `/${d.uf}` : ""}
              </span>
            </span>
          )
          return d.politico_id ? (
            <Link
              to={`/politicos/${d.politico_id}`}
              className="hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              {label}
            </Link>
          ) : (
            label
          )
        },
      })
    }
    cols.push(
      {
        id: "categoria",
        accessorKey: "categoria",
        header: t("despesa.categoria"),
        cell: ({ row }) => (
          <div className="max-w-64">
            <p className="truncate text-sm" title={row.original.categoria}>
              {row.original.categoria}
            </p>
            {row.original.subcategoria && (
              <p className="truncate text-xs text-muted-foreground">{row.original.subcategoria}</p>
            )}
          </div>
        ),
      },
      {
        id: "fornecedor",
        accessorKey: "fornecedor_nome",
        header: t("despesa.fornecedor"),
        meta: { className: "max-lg:hidden" },
        cell: ({ row }) => {
          const d = row.original
          return (
            <div className="max-w-60">
              {d.fornecedor_documento && !d.fornecedor_documento.includes("*") ? (
                <Link
                  to={`/fornecedores/${encodeURIComponent(d.fornecedor_documento)}`}
                  className="block truncate text-sm hover:underline"
                  onClick={(e) => e.stopPropagation()}
                >
                  {d.fornecedor_nome ?? "—"}
                </Link>
              ) : (
                <p className="truncate text-sm">{d.fornecedor_nome ?? "—"}</p>
              )}
              <p className="truncate font-mono text-[11px] text-muted-foreground">
                {formatDocumento(d.fornecedor_documento)}
              </p>
            </div>
          )
        },
      },
      {
        id: "verba",
        accessorKey: "verba",
        header: t("despesa.verba"),
        meta: { className: "max-md:hidden" },
        cell: ({ getValue }) => <VerbaBadge verba={getValue<string>()} />,
      },
      {
        id: "valor",
        accessorFn: (d) => toNumber(d.valor_liquido),
        header: t("despesa.valor"),
        meta: { className: "text-right" },
        cell: ({ row }) => {
          const v = toNumber(row.original.valor_liquido)
          const glosa = toNumber(row.original.valor_glosa)
          return (
            <div className="text-right whitespace-nowrap tabular-nums">
              <p className={cn("font-medium", v < 0 && "text-emerald-600 dark:text-emerald-400")}>
                {formatBRL(v)}
              </p>
              {v < 0 && <p className="text-[11px] text-muted-foreground">{t("despesa.estorno")}</p>}
              {glosa > 0 && (
                <p className="text-[11px] text-amber-600">
                  {t("despesa.glosa")} {formatBRL(glosa)}
                </p>
              )}
            </div>
          )
        },
      },
      {
        id: "links",
        header: "",
        enableSorting: false,
        cell: ({ row }) => (
          <div className="flex justify-end gap-1">
            {row.original.documento_url && (
              <a
                href={row.original.documento_url}
                target="_blank"
                rel="noreferrer"
                title={t("despesa.documento")}
                className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                onClick={(e) => e.stopPropagation()}
              >
                <IconFileInvoice className="size-4" />
              </a>
            )}
            <a
              href={row.original.fonte_url}
              target="_blank"
              rel="noreferrer"
              title={t("despesa.fonte")}
              className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              onClick={(e) => e.stopPropagation()}
            >
              <IconExternalLink className="size-4" />
            </a>
          </div>
        ),
      },
    )
    return cols
  }, [t, showParlamentar])
}

/** Gráficos do resumo de despesas (série mensal/anual, categorias). */
export function ResumoCharts({
  resumo,
  onCategoria,
}: {
  resumo: Resource<ResumoDespesas>
  onCategoria?: (categoria: string) => void
}) {
  const { t } = useTranslation()
  const r = resumo.data
  const brl = (v: number) => formatBRL(v, true)
  // Mais de um ano: série anual; um ano só: mensal.
  const anual = (r?.por_ano.length ?? 0) > 1
  const serie = anual
    ? (r?.por_ano ?? []).map((a) => ({ label: String(a.ano), value: toNumber(a.total) }))
    : (r?.por_mes ?? []).map((m) => ({ label: monthLabel(m.ano, m.mes), value: toNumber(m.total) }))

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <ChartCard
        title={anual ? t("despesa.porAno") : t("despesa.porMes")}
        loading={resumo.loading}
        isEmpty={!serie.length}
      >
        <TimeAreaChart data={serie} label={t("common.valor")} valueFormatter={brl} />
      </ChartCard>
      <ChartCard
        title={t("despesa.porCategoria")}
        loading={resumo.loading}
        isEmpty={!r?.por_categoria.length}
      >
        <SimpleBarChart
          layout="horizontal"
          label={t("common.valor")}
          valueFormatter={brl}
          onSelect={onCategoria ? (item) => onCategoria(item.name) : undefined}
          data={(r?.por_categoria ?? []).slice(0, 8).map((c) => ({
            name: c.categoria,
            value: toNumber(c.total),
          }))}
        />
      </ChartCard>
    </div>
  )
}

export function FornecedoresList({ resumo }: { resumo: Resource<ResumoDespesas> }) {
  const { t } = useTranslation()
  return (
    <ChartCard
      title={t("despesa.maioresFornecedores")}
      loading={resumo.loading}
      isEmpty={!resumo.data?.maiores_fornecedores.length}
    >
      <div className="grid gap-x-8 md:grid-cols-2">
        {(resumo.data?.maiores_fornecedores ?? []).map((f, i) => (
          <div key={`${f.fornecedor_documento}-${i}`} className="flex items-center gap-3 border-b py-2 text-sm">
            <span className="w-5 text-right text-xs text-muted-foreground">{i + 1}</span>
            <div className="min-w-0 flex-1">
              {f.fornecedor_documento && !f.fornecedor_documento.includes("*") ? (
                <Link
                  to={`/fornecedores/${encodeURIComponent(f.fornecedor_documento)}`}
                  className="block truncate font-medium hover:underline"
                >
                  {f.fornecedor_nome ?? "—"}
                </Link>
              ) : (
                <p className="truncate font-medium">{f.fornecedor_nome ?? "—"}</p>
              )}
              <p className="font-mono text-[11px] text-muted-foreground">
                {formatDocumento(f.fornecedor_documento)}
              </p>
            </div>
            <div className="text-right tabular-nums">
              <p className="font-medium">{formatBRL(f.total, true)}</p>
              <p className="text-[11px] text-muted-foreground">{t("common.docs", { count: f.quantidade })}</p>
            </div>
          </div>
        ))}
      </div>
    </ChartCard>
  )
}

export function DespesasTable({
  fetcher,
  deps,
  showParlamentar,
  enabled = true,
}: {
  fetcher: (cursor: string | null) => Promise<Page<DespesaOut>>
  deps: unknown[]
  showParlamentar?: boolean
  enabled?: boolean
}) {
  const columns = useDespesaColumns({ showParlamentar })
  const list = useCursorList(fetcher, deps, { enabled })
  return (
    <DataTable
      columns={columns}
      data={list.items}
      loading={list.loading}
      error={list.error}
      onRetry={list.reload}
      hasMore={list.hasMore}
      onLoadMore={list.loadMore}
    />
  )
}
