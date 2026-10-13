import { useMemo } from "react"
import { useNavigate } from "react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { useTranslation } from "react-i18next"

import { Badge } from "@/ui/badge"
import { DataTable } from "~/components/custom/data-table"
import {
  ExportButton,
  FilterBar,
  SearchFilter,
  SelectFilter,
  boolOptions,
} from "~/components/custom/filters"
import { useCargoLabel, useEsferaLabel } from "~/components/custom/labels"
import { PoliticoAvatar } from "~/components/custom/politico-avatar"
import { PageHeader } from "~/components/custom/states"
import { useApi } from "~/context/api"
import { usePageTitle } from "~/context/page"
import { toParams, useFilters } from "~/hooks/use-filters"
import { useCursorList, useResource } from "~/hooks/use-resource"
import { CARGOS, ESFERAS, UFS, type PoliticoResumo } from "~/interface/api"
import { formatDate } from "~/lib/format"

const KEYS = ["busca", "cargo", "esfera", "uf", "partido", "em_exercicio", "com_mandato"] as const

export default function PoliticosList() {
  const { t } = useTranslation()
  const api = useApi()
  const navigate = useNavigate()
  const cargoLabel = useCargoLabel()
  const esferaLabel = useEsferaLabel()
  const filters = useFilters(KEYS)
  const params = toParams(filters.values)
  usePageTitle(t("navigation.politicos"))

  const partidos = useResource(() => api.partidos(), [])
  const list = useCursorList(
    (cursor) => api.politicos({ ...params, cursor, limit: 50 }),
    [filters.key],
  )

  const columns = useMemo<ColumnDef<PoliticoResumo>[]>(
    () => [
      {
        id: "nome",
        accessorKey: "nome",
        header: t("politico.nome"),
        cell: ({ row }) => (
          <div className="flex items-center gap-3">
            <PoliticoAvatar politico={row.original} />
            <div className="min-w-0">
              <p className="truncate font-medium">{row.original.nome}</p>
              <p className="truncate text-xs text-muted-foreground">{row.original.nome_civil}</p>
            </div>
          </div>
        ),
      },
      {
        id: "cargo",
        accessorFn: (p) => p.ultimo_mandato?.cargo ?? "",
        header: t("politico.ultimoCargo"),
        cell: ({ row }) => {
          const m = row.original.ultimo_mandato
          return m ? (
            <div>
              <p>{cargoLabel(m.cargo)}</p>
              <p className="text-xs text-muted-foreground">{esferaLabel(m.esfera)}</p>
            </div>
          ) : (
            <span className="text-muted-foreground">{t("politico.semMandato")}</span>
          )
        },
      },
      {
        id: "partido",
        accessorFn: (p) => p.ultimo_mandato?.partido_sigla ?? p.ultimo_mandato?.partidos.at(-1) ?? "",
        header: t("politico.partido"),
        cell: ({ getValue }) =>
          getValue<string>() ? <Badge variant="outline">{getValue<string>()}</Badge> : "—",
      },
      {
        id: "uf",
        accessorFn: (p) => p.ultimo_mandato?.uf ?? "",
        header: "UF",
        cell: ({ getValue }) => getValue<string>() || "—",
      },
      {
        id: "periodo",
        accessorFn: (p) => p.ultimo_mandato?.inicio ?? "",
        header: t("politico.periodo"),
        meta: { className: "max-md:hidden" },
        cell: ({ row }) => {
          const m = row.original.ultimo_mandato
          return m ? (
            <span className="text-xs text-muted-foreground tabular-nums">
              {formatDate(m.inicio)} – {formatDate(m.fim)}
            </span>
          ) : (
            "—"
          )
        },
      },
    ],
    [t, cargoLabel, esferaLabel],
  )

  return (
    <>
      <PageHeader
        title={t("navigation.politicos")}
        description={t("politico.listDesc")}
        actions={
          <ExportButton
            onExport={() => api.exportCsv("/politicos", params, "politicos")}
          />
        }
      />
      <FilterBar onClear={filters.clear} canClear={filters.key !== ""}>
        <SearchFilter
          value={filters.values.busca}
          onChange={(v) => filters.set({ busca: v })}
          placeholder={t("filters.buscaNome")}
          minLength={3}
        />
        <SelectFilter
          value={filters.values.cargo}
          onChange={(v) => filters.set({ cargo: v })}
          placeholder={t("filters.cargo")}
          options={CARGOS.map((c) => ({ value: c, label: cargoLabel(c) }))}
        />
        <SelectFilter
          value={filters.values.esfera}
          onChange={(v) => filters.set({ esfera: v })}
          placeholder={t("filters.esfera")}
          options={ESFERAS.map((e) => ({ value: e, label: esferaLabel(e) }))}
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
          value={filters.values.em_exercicio}
          onChange={(v) => filters.set({ em_exercicio: v === "true" ? v : "" })}
          placeholder={t("filters.emExercicio")}
          options={boolOptions(t).slice(0, 1)}
        />
        <SelectFilter
          value={filters.values.com_mandato}
          onChange={(v) => filters.set({ com_mandato: v === "true" ? v : "" })}
          placeholder={t("filters.comMandato")}
          options={boolOptions(t).slice(0, 1)}
        />
      </FilterBar>
      <DataTable
        columns={columns}
        data={list.items}
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        hasMore={list.hasMore}
        onLoadMore={list.loadMore}
        onRowClick={(p) => navigate(`/politicos/${p.id}`)}
      />
    </>
  )
}
