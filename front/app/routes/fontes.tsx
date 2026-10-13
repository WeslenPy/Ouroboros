import { useMemo } from "react"
import type { ColumnDef } from "@tanstack/react-table"
import {
  IconAlertCircle,
  IconCircleCheck,
  IconExternalLink,
  IconLoader2,
  IconRefresh,
} from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import { Button } from "@/ui/button"
import { Card, CardContent } from "@/ui/card"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/ui/tooltip"
import { DataTable } from "~/components/custom/data-table"
import { FilterBar, SelectFilter } from "~/components/custom/filters"
import { KpiGrid } from "~/components/custom/kpi"
import { StatusBadge } from "~/components/custom/labels"
import { BlockSkeleton, ErrorState, PageHeader } from "~/components/custom/states"
import { DAGSTER_URL } from "~/constants/url"
import { useApi } from "~/context/api"
import { usePageTitle } from "~/context/page"
import { toParams, useFilters } from "~/hooks/use-filters"
import { useCursorList, useResource } from "~/hooks/use-resource"
import type { ExecucaoOut, FonteStatus } from "~/interface/api"
import { formatDateTime, formatDuration, formatInt, formatRelative } from "~/lib/format"
import { cn } from "~/lib/utils"

const KEYS = ["fonte", "recurso", "status"] as const

function FonteCard({ f, onPick }: { f: FonteStatus; onPick: () => void }) {
  const { t } = useTranslation()
  return (
    <Card
      onClick={onPick}
      className={cn(
        "cursor-pointer gap-2 py-4 transition-colors hover:border-primary/40",
        f.status === "falha" && "border-destructive/40",
      )}
    >
      <CardContent className="space-y-3 px-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="font-semibold">
              {f.fonte}
              <span className="text-muted-foreground">/{f.recurso}</span>
            </p>
            <p className="text-xs text-muted-foreground">
              {t("fonte.particao")}: <span className="font-mono">{f.particao}</span>
            </p>
          </div>
          <StatusBadge status={f.status} />
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <p className="text-muted-foreground">{t("common.registros")}</p>
            <p className="font-medium tabular-nums">{formatInt(f.registros)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">{t("fonte.duracao")}</p>
            <p className="font-medium tabular-nums">{formatDuration(f.iniciado_em, f.finalizado_em)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">{t("fonte.ultimaExecucao")}</p>
            <p className="font-medium" title={formatDateTime(f.iniciado_em)}>
              {formatRelative(f.iniciado_em)}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">{t("fonte.ultimoSucesso")}</p>
            <p className="font-medium" title={formatDateTime(f.ultimo_sucesso_em)}>
              {formatRelative(f.ultimo_sucesso_em)}
            </p>
          </div>
        </div>
        {f.erro && (
          <p className="line-clamp-3 rounded bg-destructive/10 p-2 font-mono text-[11px] text-destructive" title={f.erro}>
            {f.erro}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

export default function Fontes() {
  const { t } = useTranslation()
  const api = useApi()
  const filters = useFilters(KEYS)
  const params = toParams(filters.values)
  usePageTitle(t("navigation.fontes"))

  const fontes = useResource(() => api.fontes(), [], { pollMs: 15_000 })
  const rodando = fontes.data?.some((f) => f.status === "rodando")
  const execucoes = useCursorList(
    (cursor) => api.execucoes({ ...params, cursor, limit: 50 }),
    [filters.key, rodando],
  )
  const data = fontes.data ?? []
  const count = (s: string) => data.filter((f) => f.status === s).length

  const columns = useMemo<ColumnDef<ExecucaoOut>[]>(
    () => [
      { id: "id", accessorKey: "id", header: "#", cell: ({ getValue }) => <span className="font-mono text-xs">{getValue<number>()}</span> },
      {
        id: "fonte",
        accessorFn: (e) => `${e.fonte}/${e.recurso}`,
        header: t("fonte.fonte"),
        cell: ({ row }) => (
          <span className="font-medium">
            {row.original.fonte}
            <span className="text-muted-foreground">/{row.original.recurso}</span>
          </span>
        ),
      },
      { id: "particao", accessorKey: "particao", header: t("fonte.particao"), cell: ({ getValue }) => <span className="font-mono text-xs">{getValue<string>()}</span> },
      { id: "status", accessorKey: "status", header: "Status", cell: ({ row }) => <StatusBadge status={row.original.status} /> },
      { id: "registros", accessorKey: "registros", header: t("common.registros"), cell: ({ getValue }) => <span className="tabular-nums">{formatInt(getValue<number>())}</span> },
      { id: "inicio", accessorKey: "iniciado_em", header: t("fonte.inicio"), cell: ({ getValue }) => <span className="text-xs tabular-nums">{formatDateTime(getValue<string>())}</span> },
      {
        id: "duracao",
        accessorFn: (e) => (e.finalizado_em ? new Date(e.finalizado_em).getTime() - new Date(e.iniciado_em).getTime() : 0),
        header: t("fonte.duracao"),
        cell: ({ row }) => <span className="text-xs tabular-nums">{formatDuration(row.original.iniciado_em, row.original.finalizado_em)}</span>,
      },
      {
        id: "erro",
        accessorKey: "erro",
        header: t("fonte.erro"),
        enableSorting: false,
        cell: ({ getValue }) =>
          getValue<string>() ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="block max-w-56 truncate font-mono text-[11px] text-destructive">{getValue<string>()}</span>
              </TooltipTrigger>
              <TooltipContent className="max-w-md font-mono text-xs whitespace-pre-wrap">{getValue<string>()}</TooltipContent>
            </Tooltip>
          ) : (
            "—"
          ),
      },
    ],
    [t],
  )

  const nomesFonte = [...new Set(data.map((f) => f.fonte))]
  const nomesRecurso = [...new Set(data.map((f) => f.recurso))]

  return (
    <>
      <PageHeader
        title={t("navigation.fontes")}
        description={t("fonte.listDesc")}
        actions={
          <>
            <Button size="sm" variant="outline" onClick={fontes.reload}>
              <IconRefresh /> {t("common.atualizar")}
            </Button>
            <Button asChild size="sm" variant="outline">
              <a href={DAGSTER_URL} target="_blank" rel="noreferrer">
                Dagster <IconExternalLink />
              </a>
            </Button>
          </>
        }
      />
      <KpiGrid
        className="xl:grid-cols-3"
        loading={fontes.loading && !fontes.data}
        items={[
          { title: t("status.sucesso"), value: count("sucesso"), icon: IconCircleCheck },
          { title: t("status.rodando"), value: count("rodando"), icon: IconLoader2 },
          { title: t("status.falha"), value: count("falha"), icon: IconAlertCircle },
        ]}
      />
      {fontes.error ? (
        <ErrorState error={fontes.error} onRetry={fontes.reload} />
      ) : !fontes.data ? (
        <BlockSkeleton />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {data.map((f) => (
            <FonteCard
              key={`${f.fonte}-${f.recurso}-${f.particao}`}
              f={f}
              onPick={() => filters.set({ fonte: f.fonte, recurso: f.recurso })}
            />
          ))}
        </div>
      )}

      <div className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">{t("fonte.historico")}</h2>
        <FilterBar onClear={filters.clear} canClear={filters.key !== ""}>
          <SelectFilter
            value={filters.values.fonte}
            onChange={(v) => filters.set({ fonte: v })}
            placeholder={t("fonte.fonte")}
            options={nomesFonte.map((n) => ({ value: n, label: n }))}
          />
          <SelectFilter
            value={filters.values.recurso}
            onChange={(v) => filters.set({ recurso: v })}
            placeholder={t("fonte.recurso")}
            options={nomesRecurso.map((n) => ({ value: n, label: n }))}
          />
          <SelectFilter
            value={filters.values.status}
            onChange={(v) => filters.set({ status: v })}
            placeholder="Status"
            options={["sucesso", "rodando", "falha"].map((s) => ({ value: s, label: t(`status.${s}`) }))}
          />
        </FilterBar>
        <DataTable
          columns={columns}
          data={execucoes.items}
          loading={execucoes.loading}
          error={execucoes.error}
          onRetry={execucoes.reload}
          hasMore={execucoes.hasMore}
          onLoadMore={execucoes.loadMore}
        />
      </div>
    </>
  )
}
