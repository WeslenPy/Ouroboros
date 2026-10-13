import { Link } from "react-router"
import { IconInfoCircle } from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import { Alert, AlertDescription, AlertTitle } from "@/ui/alert"
import { Avatar, AvatarFallback, AvatarImage } from "@/ui/avatar"
import { Badge } from "@/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/card"
import { SimpleBarChart } from "~/components/charts/bar-chart"
import { ChartCard } from "~/components/charts/chart-card"
import { FilterBar, SelectFilter, yearOptions } from "~/components/custom/filters"
import { PresidenciaPanel } from "~/components/custom/presidencia-panel"
import { BlockSkeleton, ErrorState, PageHeader } from "~/components/custom/states"
import { useApi } from "~/context/api"
import { usePageTitle } from "~/context/page"
import { useFilters } from "~/hooks/use-filters"
import { useResource } from "~/hooks/use-resource"
import type { MandatoPresidente } from "~/interface/api"
import { formatBRL, formatDate, initials, toNumber } from "~/lib/format"
import { cn } from "~/lib/utils"

const KEYS = ["mandato", "ano", "tipo"] as const

function periodo(m: MandatoPresidente): string {
  return `${formatDate(m.inicio)} – ${formatDate(m.fim)}`
}

export default function Presidencia() {
  const { t } = useTranslation()
  const api = useApi()
  const filters = useFilters(KEYS)
  const f = filters.values
  usePageTitle(t("navigation.presidencia"))

  const presidentes = useResource(() => api.presidentes(), [])
  const mandatos = (presidentes.data ?? []).flatMap((p) => p.mandatos.map((m) => ({ ...m, nome: p.nome })))

  return (
    <>
      <PageHeader title={t("navigation.presidencia")} description={t("presidencia.desc")} />
      <Alert>
        <IconInfoCircle />
        <AlertTitle>{t("presidencia.avisoTitulo")}</AlertTitle>
        <AlertDescription>{t("presidencia.aviso")}</AlertDescription>
      </Alert>

      {presidentes.error ? (
        <ErrorState error={presidentes.error} onRetry={presidentes.reload} />
      ) : !presidentes.data ? (
        <BlockSkeleton height={220} />
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {presidentes.data.map((p) => (
              <Card key={p.politico_id} className="gap-3">
                <CardHeader className="flex flex-row items-center gap-3 space-y-0">
                  <Avatar className="size-11">
                    {p.foto_id && <AvatarImage src={api.url(`/v1/fotos/${p.foto_id}`)} className="object-cover" />}
                    <AvatarFallback>{initials(p.nome)}</AvatarFallback>
                  </Avatar>
                  <div className="min-w-0">
                    <CardTitle className="truncate text-base">
                      <Link to={`/politicos/${p.politico_id}`} className="hover:underline">
                        {p.nome}
                      </Link>
                    </CardTitle>
                    <p className="text-sm font-semibold tabular-nums">{formatBRL(p.total, true)}</p>
                  </div>
                </CardHeader>
                <CardContent className="space-y-1">
                  {p.mandatos.map((m) => (
                    <button
                      key={m.id_externo}
                      type="button"
                      onClick={() => filters.set({ mandato: f.mandato === m.id_externo ? "" : m.id_externo, ano: "" })}
                      className={cn(
                        "flex w-full items-center justify-between gap-2 rounded-md px-2 py-1 text-left text-xs hover:bg-muted",
                        f.mandato === m.id_externo && "bg-primary/10 ring-1 ring-primary/40",
                      )}
                      title={m.condicao ?? undefined}
                    >
                      <span>
                        {periodo(m)}
                        {m.condicao && <span className="text-muted-foreground"> *</span>}
                      </span>
                      <span className="tabular-nums">
                        {formatBRL(m.total, true)}
                        <span className="ml-1 text-muted-foreground">
                          ({formatBRL(m.por_dia, true)}/{t("presidencia.dia")})
                        </span>
                      </span>
                    </button>
                  ))}
                  {p.mandatos.some((m) => toNumber(m.sigiloso) > 0) && (
                    <Badge variant="outline" className="mt-1 font-normal">
                      {t("presidencia.temSigiloso")}
                    </Badge>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>

          <ChartCard title={t("presidencia.porDia")} description={t("presidencia.porDiaDesc")} height={300}>
            <SimpleBarChart
              layout="horizontal"
              height={300}
              colorful
              label={t("presidencia.porDiaLabel")}
              valueFormatter={(v) => formatBRL(v)}
              onSelect={(item) => {
                const m = mandatos.find((x) => `${x.nome} ${x.inicio.slice(0, 4)}` === item.name)
                if (m) filters.set({ mandato: m.id_externo, ano: "" })
              }}
              data={mandatos.map((m) => ({ name: `${m.nome} ${m.inicio.slice(0, 4)}`, value: toNumber(m.por_dia) }))}
            />
          </ChartCard>
        </>
      )}

      <FilterBar onClear={filters.clear} canClear={filters.key !== ""}>
        <SelectFilter
          value={f.mandato}
          onChange={(v) => filters.set({ mandato: v })}
          placeholder={t("presidencia.mandato")}
          options={mandatos.map((m) => ({ value: m.id_externo, label: `${m.nome} · ${periodo(m)}` }))}
          className="max-w-80"
        />
        <SelectFilter value={f.ano} onChange={(v) => filters.set({ ano: v })} placeholder={t("filters.ano")} options={yearOptions(2003)} />
        <SelectFilter
          value={f.tipo}
          onChange={(v) => filters.set({ tipo: v })}
          placeholder={t("presidencia.tipo")}
          options={[
            { value: "credito", label: t("presidencia.credito") },
            { value: "saque", label: t("presidencia.saque") },
          ]}
        />
      </FilterBar>

      <PresidenciaPanel
        params={{ mandato: f.mandato || undefined, ano: f.ano ? Number(f.ano) : undefined, tipo: f.tipo || undefined }}
      />
    </>
  )
}
