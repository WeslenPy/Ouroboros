import { useMemo } from "react"
import { Link } from "react-router"
import { IconUsers } from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import { Badge } from "@/ui/badge"
import { Card, CardContent } from "@/ui/card"
import { FilterBar, SelectFilter } from "~/components/custom/filters"
import { BlockSkeleton, EmptyState, ErrorState, PageHeader } from "~/components/custom/states"
import { useApi } from "~/context/api"
import { usePageTitle } from "~/context/page"
import { useFilters } from "~/hooks/use-filters"
import { useResource } from "~/hooks/use-resource"
import { formatInt } from "~/lib/format"
import { cn } from "~/lib/utils"

const KEYS = ["ativo"] as const

export default function PartidosList() {
  const { t } = useTranslation()
  const api = useApi()
  const filters = useFilters(KEYS)
  usePageTitle(t("navigation.partidos"))

  const partidos = useResource(
    () => api.partidos({ ativo: filters.values.ativo || undefined }),
    [filters.key],
  )
  const stats = useResource(() => api.stats(), [])
  const emExercicio = useMemo(
    () => new Map((stats.data?.em_exercicio_por_partido ?? []).map((c) => [c.chave, c.quantidade])),
    [stats.data],
  )
  const ordenados = useMemo(
    () =>
      [...(partidos.data ?? [])].sort(
        (a, b) => (emExercicio.get(b.sigla) ?? 0) - (emExercicio.get(a.sigla) ?? 0),
      ),
    [partidos.data, emExercicio],
  )
  const max = Math.max(1, ...emExercicio.values())

  return (
    <>
      <PageHeader title={t("navigation.partidos")} description={t("partido.listDesc")} />
      <FilterBar onClear={filters.clear} canClear={filters.key !== ""}>
        <SelectFilter
          value={filters.values.ativo}
          onChange={(v) => filters.set({ ativo: v })}
          placeholder={t("filters.situacao")}
          options={[
            { value: "true", label: t("partido.ativo") },
            { value: "false", label: t("partido.extinto") },
          ]}
        />
      </FilterBar>
      {partidos.error ? (
        <ErrorState error={partidos.error} onRetry={partidos.reload} />
      ) : partidos.loading ? (
        <BlockSkeleton height={400} />
      ) : !ordenados.length ? (
        <EmptyState />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
          {ordenados.map((p) => {
            const n = emExercicio.get(p.sigla) ?? 0
            return (
              <Link key={p.id} to={`/partidos/${encodeURIComponent(p.sigla)}`}>
                <Card className="h-full gap-3 py-4 transition-colors hover:border-primary/40">
                  <CardContent className="flex flex-col gap-3 px-4">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-lg font-semibold">{p.sigla}</p>
                        <p className="truncate text-xs text-muted-foreground" title={p.nome}>
                          {p.nome}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1">
                        {p.numero_tse && (
                          <span className="font-mono text-xl font-bold text-muted-foreground/60">
                            {p.numero_tse}
                          </span>
                        )}
                        {!p.ativo && <Badge variant="outline">{t("partido.extinto")}</Badge>}
                      </div>
                    </div>
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <span className="inline-flex items-center gap-1">
                          <IconUsers className="size-3.5" /> {t("kpi.emExercicio")}
                        </span>
                        <span className="font-medium text-foreground tabular-nums">{formatInt(n)}</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                        <div
                          className={cn("h-full rounded-full bg-primary transition-all")}
                          style={{ width: `${(n / max) * 100}%` }}
                        />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            )
          })}
        </div>
      )}
    </>
  )
}
