import { useMemo } from "react"
import { Link } from "react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { useTranslation } from "react-i18next"

import { Badge } from "@/ui/badge"
import { DataTable } from "~/components/custom/data-table"
import { FilterBar, SelectFilter } from "~/components/custom/filters"
import { PageHeader } from "~/components/custom/states"
import { useApi } from "~/context/api"
import { usePageTitle } from "~/context/page"
import { useFilters } from "~/hooks/use-filters"
import { useCursorList } from "~/hooks/use-resource"
import type { MatchPendenteOut } from "~/interface/api"
import { formatDateTime } from "~/lib/format"

const KEYS = ["resolvido", "origem"] as const

export default function Matches() {
  const { t } = useTranslation()
  const api = useApi()
  const filters = useFilters(KEYS)
  usePageTitle(t("navigation.matches"))

  // Padrão da tela: só pendentes. "todos" omite o filtro.
  const resolvido = filters.values.resolvido || "false"
  const list = useCursorList(
    (cursor) =>
      api.matches({
        resolvido: resolvido === "todos" ? undefined : resolvido,
        origem: filters.values.origem || undefined,
        cursor,
        limit: 50,
      }),
    [filters.key],
  )

  const columns = useMemo<ColumnDef<MatchPendenteOut>[]>(
    () => [
      { id: "id", accessorKey: "id", header: "#", cell: ({ getValue }) => <span className="font-mono text-xs">{getValue<number>()}</span> },
      { id: "origem", accessorKey: "origem", header: t("politico.origem"), cell: ({ getValue }) => <Badge variant="outline">{getValue<string>()}</Badge> },
      { id: "id_externo", accessorKey: "id_externo", header: t("politico.idExterno"), cell: ({ getValue }) => <span className="font-mono text-xs">{getValue<string>()}</span> },
      { id: "motivo", accessorKey: "motivo", header: t("match.motivo"), cell: ({ getValue }) => t(`match.motivos.${getValue<string>()}`, getValue<string>()) },
      {
        id: "candidatos",
        accessorFn: (m) => m.politico_ids.length,
        header: t("match.candidatos"),
        cell: ({ row }) => (
          <div className="flex flex-wrap gap-1">
            {row.original.politico_ids.map((id) => (
              <Badge key={id} variant="secondary" asChild>
                <Link to={`/politicos/${id}`}>#{id}</Link>
              </Badge>
            ))}
          </div>
        ),
      },
      {
        id: "resolvido",
        accessorKey: "resolvido",
        header: "Status",
        cell: ({ getValue }) =>
          getValue<boolean>() ? (
            <Badge className="bg-emerald-600 text-white">{t("match.resolvido")}</Badge>
          ) : (
            <Badge variant="outline" className="border-amber-500/40 text-amber-600">
              {t("match.pendente")}
            </Badge>
          ),
      },
      { id: "criado", accessorKey: "criado_em", header: t("match.criado"), cell: ({ getValue }) => <span className="text-xs">{formatDateTime(getValue<string>())}</span> },
    ],
    [t],
  )

  return (
    <>
      <PageHeader title={t("navigation.matches")} description={t("match.listDesc")} />
      <FilterBar onClear={filters.clear} canClear={filters.key !== ""}>
        <SelectFilter
          value={filters.values.resolvido === "false" ? "" : filters.values.resolvido}
          onChange={(v) => filters.set({ resolvido: v })}
          placeholder={t("match.pendentes")}
          options={[
            { value: "true", label: t("match.resolvidos") },
            { value: "todos", label: t("match.todos") },
          ]}
        />
        <SelectFilter
          value={filters.values.origem}
          onChange={(v) => filters.set({ origem: v })}
          placeholder={t("politico.origem")}
          options={["camara", "senado", "tse"].map((o) => ({ value: o, label: o }))}
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
      />
    </>
  )
}
