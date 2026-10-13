import { useMemo } from "react"
import { useNavigate } from "react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { useTranslation } from "react-i18next"

import { Badge } from "@/ui/badge"
import { DataTable } from "~/components/custom/data-table"
import { FilterBar, SearchFilter, SelectFilter } from "~/components/custom/filters"
import { useEsferaLabel } from "~/components/custom/labels"
import { PageHeader } from "~/components/custom/states"
import { useApi } from "~/context/api"
import { usePageTitle } from "~/context/page"
import { toParams, useFilters } from "~/hooks/use-filters"
import { useCursorList } from "~/hooks/use-resource"
import { ESFERAS, UFS, type EnteOut } from "~/interface/api"

const KEYS = ["busca", "esfera", "uf"] as const

export default function EntesList() {
  const { t } = useTranslation()
  const api = useApi()
  const navigate = useNavigate()
  const esferaLabel = useEsferaLabel()
  const filters = useFilters(KEYS)
  const params = toParams(filters.values)
  usePageTitle(t("navigation.entes"))

  const list = useCursorList((cursor) => api.entes({ ...params, cursor, limit: 100 }), [filters.key])

  const columns = useMemo<ColumnDef<EnteOut>[]>(
    () => [
      {
        id: "codigo",
        accessorKey: "codigo_ibge",
        header: t("ente.codigo"),
        cell: ({ getValue }) => <span className="font-mono text-xs">{getValue<number>()}</span>,
      },
      {
        id: "nome",
        accessorKey: "nome",
        header: t("ente.nome"),
        cell: ({ getValue }) => <span className="font-medium">{getValue<string>()}</span>,
      },
      {
        id: "esfera",
        accessorKey: "esfera",
        header: t("filters.esfera"),
        cell: ({ getValue }) => <Badge variant="outline">{esferaLabel(getValue<string>())}</Badge>,
      },
      { id: "uf", accessorKey: "uf", header: "UF", cell: ({ getValue }) => getValue<string>() ?? "—" },
      {
        id: "regiao",
        accessorKey: "regiao",
        header: t("ente.regiao"),
        cell: ({ getValue }) => getValue<string>() ?? "—",
      },
    ],
    [t, esferaLabel],
  )

  return (
    <>
      <PageHeader title={t("navigation.entes")} description={t("ente.listDesc")} />
      <FilterBar onClear={filters.clear} canClear={filters.key !== ""}>
        <SearchFilter
          value={filters.values.busca}
          onChange={(v) => filters.set({ busca: v })}
          placeholder={t("filters.buscaNome")}
          minLength={2}
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
      </FilterBar>
      <DataTable
        columns={columns}
        data={list.items}
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        hasMore={list.hasMore}
        onLoadMore={list.loadMore}
        onRowClick={(e) => navigate(`/entes/${e.codigo_ibge}`)}
      />
    </>
  )
}
