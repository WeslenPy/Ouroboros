import { useMemo } from "react"
import { Link } from "react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { IconTicket, IconTrophy, IconPercentage } from "@tabler/icons-react"
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
  boolOptions,
  yearOptions,
} from "~/components/custom/filters"
import { KpiGrid } from "~/components/custom/kpi"
import { PageHeader } from "~/components/custom/states"
import { useApi } from "~/context/api"
import { usePageTitle } from "~/context/page"
import { toParams, useFilters } from "~/hooks/use-filters"
import { useCursorList, useResource } from "~/hooks/use-resource"
import { UFS, type CandidaturaOut } from "~/interface/api"
import { formatInt } from "~/lib/format"
import { cn } from "~/lib/utils"

const KEYS = ["ano", "cargo", "uf", "partido", "eleito", "turno"] as const
const NUMERIC = ["ano", "turno"] as const

export default function Candidaturas() {
  const { t } = useTranslation()
  const api = useApi()
  const filters = useFilters(KEYS)
  const params = toParams(filters.values, NUMERIC)
  usePageTitle(t("navigation.candidaturas"))

  const partidos = useResource(() => api.partidos(), [])
  const resumo = useResource(() => api.candidaturasResumo(params), [filters.key])
  const list = useCursorList((cursor) => api.candidaturas({ ...params, cursor, limit: 50 }), [filters.key])
  const r = resumo.data

  const columns = useMemo<ColumnDef<CandidaturaOut>[]>(
    () => [
      {
        id: "nome",
        accessorKey: "nome_urna",
        header: t("candidatura.nomeUrna"),
        cell: ({ row }) => (
          <Link
            to={`/politicos/${row.original.politico_id}`}
            className="font-medium hover:underline"
          >
            {row.original.nome_urna}
            {row.original.numero_urna && (
              <span className="ml-1.5 font-mono text-xs text-muted-foreground">
                {row.original.numero_urna}
              </span>
            )}
          </Link>
        ),
      },
      {
        id: "ano",
        accessorKey: "ano",
        header: t("candidatura.ano"),
        cell: ({ row }) => (
          <span className="tabular-nums">
            {row.original.ano} <span className="text-xs text-muted-foreground">{row.original.turno}º</span>
          </span>
        ),
      },
      { id: "cargo", accessorKey: "cargo", header: t("candidatura.cargo") },
      {
        id: "local",
        accessorKey: "ue_nome",
        header: t("candidatura.local"),
        meta: { className: "max-md:hidden" },
      },
      {
        id: "partido",
        accessorKey: "partido_sigla",
        header: t("candidatura.partido"),
        cell: ({ getValue }) => getValue<string>() ?? "—",
      },
      {
        id: "situacao",
        accessorFn: (c) => c.situacao_turno ?? c.situacao_candidatura ?? "",
        header: t("candidatura.situacao"),
        cell: ({ row }) => (
          <Badge
            variant={row.original.eleito ? "default" : "outline"}
            className={cn(row.original.eleito && "bg-emerald-600 text-white")}
          >
            {row.original.situacao_turno ?? row.original.situacao_candidatura ?? "—"}
          </Badge>
        ),
      },
    ],
    [t],
  )

  return (
    <>
      <PageHeader
        title={t("navigation.candidaturas")}
        description={t("candidatura.listDesc")}
        actions={
          <ExportButton onExport={() => api.exportCsv("/candidaturas", params, "candidaturas")} />
        }
      />
      <FilterBar onClear={filters.clear} canClear={filters.key !== ""}>
        <SelectFilter
          value={filters.values.ano}
          onChange={(v) => filters.set({ ano: v })}
          placeholder={t("filters.ano")}
          options={yearOptions(1994).filter((y) => Number(y.value) % 2 === 0)}
        />
        <SearchFilter
          value={filters.values.cargo}
          onChange={(v) => filters.set({ cargo: v })}
          placeholder={t("filters.cargo")}
          className="sm:w-48"
        />
        <SelectFilter
          value={filters.values.uf}
          onChange={(v) => filters.set({ uf: v })}
          placeholder="UF"
          options={UFS.map((u) => ({ value: u, label: u }))}
        />
        <SelectFilter
          value={filters.values.partido}
          onChange={(v) => filters.set({ partido: v })}
          placeholder={t("filters.partido")}
          options={(partidos.data ?? []).map((p) => ({ value: p.sigla, label: p.sigla }))}
        />
        <SelectFilter
          value={filters.values.eleito}
          onChange={(v) => filters.set({ eleito: v })}
          placeholder={t("filters.eleito")}
          options={boolOptions(t)}
        />
        <SelectFilter
          value={filters.values.turno}
          onChange={(v) => filters.set({ turno: v })}
          placeholder={t("filters.turno")}
          options={[
            { value: "1", label: "1º" },
            { value: "2", label: "2º" },
          ]}
        />
      </FilterBar>

      <KpiGrid
        className="xl:grid-cols-3"
        loading={resumo.loading}
        items={[
          { title: t("kpi.candidaturas"), value: formatInt(r?.total), icon: IconTicket },
          { title: t("candidatura.eleitos"), value: formatInt(r?.eleitos), icon: IconTrophy },
          {
            title: t("candidatura.taxa"),
            value: r?.total ? `${((r.eleitos / r.total) * 100).toFixed(1)}%` : "—",
            icon: IconPercentage,
          },
        ]}
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard
          className="lg:col-span-2"
          title={t("candidatura.porAno")}
          loading={resumo.loading}
          isEmpty={!r?.por_ano.length}
        >
          <SimpleBarChart
            label={t("candidatura.naoEleitos")}
            secondaryLabel={t("candidatura.eleitos")}
            onSelect={(item) => filters.set({ ano: item.name })}
            data={(r?.por_ano ?? []).map((a) => ({
              name: a.chave ?? "—",
              value: a.quantidade,
              secondary: a.eleitos,
            }))}
          />
        </ChartCard>
        <ChartCard title={t("candidatura.porSituacao")} loading={resumo.loading} isEmpty={!r?.por_situacao.length}>
          <DonutChart
            othersLabel={t("common.outros")}
            data={(r?.por_situacao ?? []).map((s) => ({ name: s.chave ?? "—", value: s.quantidade }))}
          />
        </ChartCard>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title={t("candidatura.porCargo")} loading={resumo.loading} isEmpty={!r?.por_cargo.length} height={360}>
          <SimpleBarChart
            layout="horizontal"
            height={360}
            label={t("candidatura.naoEleitos")}
            secondaryLabel={t("candidatura.eleitos")}
            onSelect={(item) => filters.set({ cargo: item.name })}
            data={(r?.por_cargo ?? []).slice(0, 12).map((c) => ({
              name: c.chave ?? "—",
              value: c.quantidade,
              secondary: c.eleitos,
            }))}
          />
        </ChartCard>
        <ChartCard title={t("candidatura.porPartido")} loading={resumo.loading} isEmpty={!r?.por_partido.length} height={360}>
          <SimpleBarChart
            layout="horizontal"
            height={360}
            label={t("candidatura.naoEleitos")}
            secondaryLabel={t("candidatura.eleitos")}
            onSelect={(item) => filters.set({ partido: item.name })}
            data={(r?.por_partido ?? []).slice(0, 15).map((c) => ({
              name: c.chave ?? "—",
              value: c.quantidade,
              secondary: c.eleitos,
            }))}
          />
        </ChartCard>
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
    </>
  )
}
