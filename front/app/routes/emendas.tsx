import { useMemo } from "react"
import { Link, useNavigate } from "react-router"
import type { ColumnDef } from "@tanstack/react-table"
import {
  IconAffiliate,
  IconBuildingBank,
  IconCash,
  IconExternalLink,
  IconPercentage,
} from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import { Badge } from "@/ui/badge"
import { SimpleBarChart } from "~/components/charts/bar-chart"
import { ChartCard } from "~/components/charts/chart-card"
import { DonutChart } from "~/components/charts/pie-chart"
import { DataTable } from "~/components/custom/data-table"
import {
  ExportButton,
  FilterBar,
  SearchFilter,
  SelectFilter,
  yearOptions,
} from "~/components/custom/filters"
import { KpiGrid } from "~/components/custom/kpi"
import { PageHeader } from "~/components/custom/states"
import { useApi } from "~/context/api"
import { usePageTitle } from "~/context/page"
import { toParams, useFilters } from "~/hooks/use-filters"
import { useCursorList, useResource } from "~/hooks/use-resource"
import { UFS, type EmendaOut, type TotalChave } from "~/interface/api"
import { formatBRL, formatDocumento, formatInt, toNumber } from "~/lib/format"

const KEYS = ["ano", "tipo", "uf", "funcao", "autor", "municipio", "politico"] as const
const NUMERIC = ["ano", "municipio", "politico"] as const

const TIPOS = [
  { value: "Finalidade Definida", key: "individual" },
  { value: "Especiais", key: "especial" },
  { value: "Bancada", key: "bancada" },
  { value: "Comissão", key: "comissao" },
  { value: "Relator", key: "relator" },
]

function Ranking({
  titulo,
  itens,
  loading,
  link,
  grafo,
}: {
  titulo: string
  itens: TotalChave[]
  loading: boolean
  link?: (c: string) => string
  grafo?: (c: string) => string
}) {
  const { t } = useTranslation()
  return (
    <ChartCard title={titulo} loading={loading} isEmpty={!itens.length} height={300}>
      <ol className="divide-y text-sm">
        {itens.slice(0, 10).map((item, i) => (
          <li key={`${item.chave}-${i}`} className="flex items-center gap-3 py-2">
            <span className="w-5 text-right text-xs text-muted-foreground">{i + 1}</span>
            <div className="min-w-0 flex-1">
              {item.chave && link ? (
                <Link to={link(item.chave)} className="block truncate font-medium hover:underline">
                  {item.rotulo ?? item.chave}
                </Link>
              ) : (
                <p className="truncate font-medium">{item.rotulo ?? item.chave ?? "—"}</p>
              )}
              <p className="text-[11px] text-muted-foreground">
                {t("emenda.qtd", { count: item.quantidade })}
              </p>
            </div>
            <span className="font-medium tabular-nums">{formatBRL(item.pago, true)}</span>
            {item.chave && grafo && (
              <Link
                to={grafo(item.chave)}
                title={t("grafo.verRede")}
                className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <IconAffiliate className="size-4" />
              </Link>
            )}
          </li>
        ))}
      </ol>
    </ChartCard>
  )
}

export default function Emendas() {
  const { t } = useTranslation()
  const api = useApi()
  const navigate = useNavigate()
  const filters = useFilters(KEYS)
  const params = toParams(filters.values, NUMERIC)
  usePageTitle(t("navigation.emendas"))

  const resumo = useResource(() => api.emendasResumo(params), [filters.key])
  const list = useCursorList((cursor) => api.emendas({ ...params, cursor, limit: 50 }), [filters.key])
  const r = resumo.data
  const brl = (v: number) => formatBRL(v, true)
  const execucao = r && toNumber(r.empenhado) > 0 ? toNumber(r.pago) / toNumber(r.empenhado) : 0

  const columns = useMemo<ColumnDef<EmendaOut>[]>(
    () => [
      {
        id: "codigo",
        accessorKey: "codigo",
        header: t("emenda.codigo"),
        cell: ({ row }) => (
          <div>
            <Link
              to={`/emendas/${row.original.codigo}`}
              className="font-mono text-xs hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              {row.original.codigo}
            </Link>
            <p className="text-[11px] text-muted-foreground">{row.original.ano}</p>
          </div>
        ),
      },
      {
        id: "autor",
        accessorKey: "autor_nome",
        header: t("emenda.autor"),
        cell: ({ row }) =>
          row.original.politico_id ? (
            <Link to={`/politicos/${row.original.politico_id}`} className="font-medium hover:underline">
              {row.original.autor_nome}
            </Link>
          ) : (
            <span className="text-muted-foreground">{row.original.autor_nome}</span>
          ),
      },
      {
        id: "destino",
        accessorFn: (e) => e.municipio_nome ?? e.localidade ?? "",
        header: t("emenda.destino"),
        cell: ({ row }) => (
          <div className="max-w-48">
            <p className="truncate">
              {row.original.municipio_nome
                ? `${row.original.municipio_nome} - ${row.original.uf ?? ""}`
                : (row.original.localidade ?? "—")}
            </p>
          </div>
        ),
      },
      {
        id: "area",
        accessorKey: "funcao",
        header: t("emenda.area"),
        meta: { className: "max-lg:hidden" },
        cell: ({ row }) => (
          <div className="max-w-64">
            <p className="truncate">{row.original.funcao ?? "—"}</p>
            <p className="truncate text-[11px] text-muted-foreground" title={row.original.acao ?? ""}>
              {row.original.acao}
            </p>
          </div>
        ),
      },
      {
        id: "tipo",
        accessorKey: "tipo",
        header: t("emenda.tipo"),
        meta: { className: "max-md:hidden" },
        cell: ({ getValue }) => {
          const tipo = TIPOS.find((x) => getValue<string>().includes(x.value))
          return <Badge variant="outline">{tipo ? t(`emenda.tipos.${tipo.key}`) : getValue<string>()}</Badge>
        },
      },
      {
        id: "empenhado",
        accessorFn: (e) => toNumber(e.valor_empenhado),
        header: t("emenda.empenhado"),
        meta: { className: "text-right" },
        cell: ({ getValue }) => (
          <span className="block text-right tabular-nums">{formatBRL(getValue<number>(), true)}</span>
        ),
      },
      {
        id: "pago",
        accessorFn: (e) => toNumber(e.valor_pago) + toNumber(e.valor_rp_pago),
        header: t("emenda.pago"),
        meta: { className: "text-right" },
        cell: ({ getValue }) => (
          <span className="block text-right font-medium tabular-nums">
            {formatBRL(getValue<number>(), true)}
          </span>
        ),
      },
      {
        id: "fonte",
        header: "",
        enableSorting: false,
        cell: ({ row }) => (
          <a
            href={row.original.fonte_url}
            target="_blank"
            rel="noreferrer"
            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <IconExternalLink className="size-4" />
          </a>
        ),
      },
    ],
    [t],
  )

  return (
    <>
      <PageHeader
        title={t("navigation.emendas")}
        description={t("emenda.listDesc")}
        actions={<ExportButton onExport={() => api.exportCsv("/emendas", params, "emendas")} />}
      />
      <FilterBar onClear={filters.clear} canClear={filters.key !== ""}>
        <SelectFilter
          value={filters.values.ano}
          onChange={(v) => filters.set({ ano: v })}
          placeholder={t("filters.ano")}
          options={yearOptions(2014)}
        />
        <SelectFilter
          value={filters.values.tipo}
          onChange={(v) => filters.set({ tipo: v })}
          placeholder={t("emenda.tipo")}
          options={TIPOS.map((x) => ({ value: x.value, label: t(`emenda.tipos.${x.key}`) }))}
        />
        <SelectFilter
          value={filters.values.uf}
          onChange={(v) => filters.set({ uf: v })}
          placeholder="UF"
          options={UFS.map((u) => ({ value: u, label: u }))}
        />
        <SearchFilter
          value={filters.values.funcao}
          onChange={(v) => filters.set({ funcao: v })}
          placeholder={t("emenda.filtroArea")}
          className="sm:w-44"
        />
        <SearchFilter
          value={filters.values.autor}
          onChange={(v) => filters.set({ autor: v })}
          placeholder={t("emenda.filtroAutor")}
          minLength={3}
        />
      </FilterBar>

      <KpiGrid
        loading={resumo.loading}
        items={[
          { title: t("emenda.quantidade"), value: formatInt(r?.quantidade), icon: IconBuildingBank },
          { title: t("emenda.empenhado"), value: formatBRL(r?.empenhado, true), hint: t("emenda.empenhadoHint"), icon: IconCash },
          { title: t("emenda.pago"), value: formatBRL(r?.pago, true), hint: t("emenda.pagoHint"), icon: IconCash },
          { title: t("emenda.execucao"), value: `${(execucao * 100).toFixed(1)}%`, hint: t("emenda.execucaoHint"), icon: IconPercentage },
        ]}
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard className="lg:col-span-2" title={t("emenda.porAno")} loading={resumo.loading} isEmpty={!r?.por_ano.length}>
          <SimpleBarChart
            label={t("emenda.naoPago")}
            secondaryLabel={t("emenda.pago")}
            valueFormatter={brl}
            onSelect={(item) => filters.set({ ano: item.name })}
            data={(r?.por_ano ?? []).map((a) => ({
              name: a.chave ?? "—",
              value: Math.max(toNumber(a.empenhado), toNumber(a.pago)),
              secondary: toNumber(a.pago),
            }))}
          />
        </ChartCard>
        <ChartCard title={t("emenda.porTipo")} loading={resumo.loading} isEmpty={!r?.por_tipo.length}>
          <DonutChart
            valueFormatter={brl}
            data={(r?.por_tipo ?? []).map((x) => {
              const tipo = TIPOS.find((y) => x.chave?.includes(y.value))
              return { name: tipo ? t(`emenda.tipos.${tipo.key}`) : (x.chave ?? "—"), value: toNumber(x.pago) }
            })}
          />
        </ChartCard>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title={t("emenda.porArea")} loading={resumo.loading} isEmpty={!r?.por_funcao.length} height={340}>
          <SimpleBarChart
            layout="horizontal"
            height={340}
            colorful
            label={t("emenda.pago")}
            valueFormatter={brl}
            onSelect={(item) => filters.set({ funcao: item.name })}
            data={(r?.por_funcao ?? []).slice(0, 10).map((f) => ({ name: f.chave ?? "—", value: toNumber(f.pago) }))}
          />
        </ChartCard>
        <ChartCard title={t("emenda.porUf")} loading={resumo.loading} isEmpty={!r?.por_uf.length} height={340}>
          <SimpleBarChart
            height={340}
            label={t("emenda.pago")}
            valueFormatter={brl}
            onSelect={(item) => item.name !== "—" && filters.set({ uf: item.name })}
            data={(r?.por_uf ?? []).map((u) => ({ name: u.chave ?? "—", value: toNumber(u.pago) }))}
          />
        </ChartCard>
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <Ranking
          titulo={t("emenda.maioresAutores")}
          itens={r?.maiores_autores ?? []}
          loading={resumo.loading}
          link={(c) => `/politicos/${c}`}
          grafo={(c) => `/grafo?no=politico:${c}`}
        />
        <Ranking
          titulo={t("emenda.maioresDestinos")}
          itens={r?.maiores_destinos ?? []}
          loading={resumo.loading}
          grafo={(c) => (/^\d+$/.test(c) ? `/grafo?no=municipio:${c}` : "")}
        />
        <Ranking
          titulo={t("emenda.maioresFavorecidos")}
          itens={(r?.maiores_favorecidos ?? []).map((f) => ({
            ...f,
            rotulo: `${f.rotulo ?? ""} · ${formatDocumento(f.chave)}`,
          }))}
          loading={resumo.loading}
          link={(c) => `/fornecedores/${c}`}
          grafo={(c) => `/grafo?no=doc:${c}`}
        />
      </div>

      <DataTable
        columns={columns}
        data={list.items}
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        hasMore={list.hasMore}
        onLoadMore={list.loadMore}
        onRowClick={(e) => e.politico_id && navigate(`/grafo?no=politico:${e.politico_id}`)}
      />
    </>
  )
}
