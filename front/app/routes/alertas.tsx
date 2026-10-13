import { useMemo } from "react"
import { Link, useNavigate } from "react-router"
import type { ColumnDef } from "@tanstack/react-table"
import {
  IconAlertTriangle,
  IconFlame,
  IconInfoCircle,
  IconScale,
  IconUsers,
} from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import { Alert, AlertDescription, AlertTitle } from "@/ui/alert"
import { Avatar, AvatarFallback, AvatarImage } from "@/ui/avatar"
import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/ui/tabs"
import { AlertasList, RiscoBar } from "~/components/custom/alertas"
import { DataTable } from "~/components/custom/data-table"
import { FilterBar, SelectFilter } from "~/components/custom/filters"
import { KpiGrid } from "~/components/custom/kpi"
import { PageHeader } from "~/components/custom/states"
import { useApi } from "~/context/api"
import { usePageTitle } from "~/context/page"
import { useFilters } from "~/hooks/use-filters"
import { useResource } from "~/hooks/use-resource"
import { SEVERIDADES, UFS, type DetectorOut, type RiscoPolitico } from "~/interface/api"
import { formatBRL, formatInt, formatRelative, initials } from "~/lib/format"

const KEYS = ["aba", "detector", "severidade", "uf", "partido", "entidade"] as const

export default function Alertas() {
  const { t } = useTranslation()
  const api = useApi()
  const navigate = useNavigate()
  const filters = useFilters(KEYS)
  const f = filters.values
  const aba = f.aba || "ranking"
  usePageTitle(t("navigation.alertas"))

  const catalogo = useResource(() => api.alertasDetectores(), [])
  const detectores = useMemo(
    () => Object.fromEntries((catalogo.data?.detectores ?? []).map((d) => [d.codigo, d])),
    [catalogo.data],
  ) as Record<string, DetectorOut>

  const ranking = useResource(
    () =>
      api.alertasRanking({
        limit: 200,
        detector: f.detector || undefined,
        uf: f.uf || undefined,
        partido: f.partido || undefined,
      }),
    [f.detector, f.uf, f.partido],
    { enabled: aba === "ranking" },
  )

  const totais = (catalogo.data?.detectores ?? []).reduce(
    (acc, d) => ({ alertas: acc.alertas + d.alertas, alta: acc.alta + d.alta }),
    { alertas: 0, alta: 0 },
  )

  const columns = useMemo<ColumnDef<RiscoPolitico>[]>(
    () => [
      {
        id: "pos",
        header: "#",
        cell: ({ row }) => <span className="text-xs text-muted-foreground">{row.index + 1}</span>,
      },
      {
        id: "nome",
        accessorKey: "nome",
        header: t("alerta.politico"),
        cell: ({ row }) => {
          const p = row.original
          return (
            <Link to={`/politicos/${p.politico_id}`} className="flex items-center gap-2 hover:underline">
              <Avatar className="size-8">
                {p.foto_id && <AvatarImage src={api.url(`/v1/fotos/${p.foto_id}`)} className="object-cover" />}
                <AvatarFallback className="text-[10px]">{initials(p.nome)}</AvatarFallback>
              </Avatar>
              <span className="font-medium">{p.nome}</span>
            </Link>
          )
        },
      },
      {
        id: "partido",
        header: t("alerta.partidoUf"),
        cell: ({ row }) => (
          <span className="text-xs">
            {[row.original.partido, row.original.uf].filter(Boolean).join(" · ") || "—"}
          </span>
        ),
      },
      {
        id: "risco",
        accessorKey: "risco",
        header: t("alerta.risco"),
        cell: ({ getValue }) => <RiscoBar risco={getValue<number>()} />,
      },
      {
        id: "alertas",
        accessorKey: "alertas",
        header: t("alerta.alertas"),
        cell: ({ row }) => (
          <span className="tabular-nums">
            {row.original.alertas}
            {row.original.alertas_alta > 0 && (
              <span className="ml-1 text-xs font-semibold text-red-600">
                ({row.original.alertas_alta} {t("alerta.severidades.alta").toLowerCase()})
              </span>
            )}
          </span>
        ),
      },
      {
        id: "valor",
        accessorFn: (r) => Number(r.valor),
        header: t("alerta.valorEnvolvido"),
        cell: ({ row }) => <span className="tabular-nums">{formatBRL(row.original.valor, true)}</span>,
      },
      {
        id: "detectores",
        header: t("alerta.principais"),
        enableSorting: false,
        cell: ({ row }) => (
          <div className="flex flex-wrap gap-1">
            {row.original.detectores.slice(0, 3).map((d) => (
              <Badge key={d.detector} variant="outline" className="font-normal">
                {detectores[d.detector]?.titulo ?? d.detector} · {d.score.toFixed(0)}
              </Badge>
            ))}
          </div>
        ),
      },
    ],
    [t, api, detectores],
  )

  const opcoesDetector = (catalogo.data?.detectores ?? []).map((d) => ({
    value: d.codigo,
    label: d.titulo,
  }))

  return (
    <>
      <PageHeader title={t("navigation.alertas")} description={t("alerta.desc")} />

      <Alert>
        <IconInfoCircle />
        <AlertTitle>{t("alerta.avisoTitulo")}</AlertTitle>
        <AlertDescription>{catalogo.data?.aviso ?? t("alerta.aviso")}</AlertDescription>
      </Alert>

      <KpiGrid
        loading={catalogo.loading}
        items={[
          { title: t("alerta.totalAlertas"), value: formatInt(totais.alertas), icon: IconAlertTriangle },
          { title: t("alerta.altaSeveridade"), value: formatInt(totais.alta), icon: IconFlame },
          {
            title: t("alerta.detectores"),
            value: formatInt(catalogo.data?.detectores.length ?? 0),
            icon: IconScale,
          },
          {
            title: t("alerta.atualizado"),
            value: catalogo.data?.gerado_em ? formatRelative(catalogo.data.gerado_em) : "—",
            hint: t("alerta.atualizadoHint"),
            icon: IconUsers,
          },
        ]}
      />

      <Tabs value={aba} onValueChange={(v) => filters.set({ aba: v === "ranking" ? "" : v })}>
        <TabsList>
          <TabsTrigger value="ranking">{t("alerta.abas.ranking")}</TabsTrigger>
          <TabsTrigger value="lista">{t("alerta.abas.lista")}</TabsTrigger>
          <TabsTrigger value="metodologia">{t("alerta.abas.metodologia")}</TabsTrigger>
        </TabsList>

        <FilterBar onClear={() => filters.set({ detector: "", severidade: "", uf: "", partido: "" })} canClear={!!(f.detector || f.severidade || f.uf || f.partido)}>
          {aba !== "metodologia" && (
            <SelectFilter
              value={f.detector}
              onChange={(v) => filters.set({ detector: v })}
              placeholder={t("alerta.detector")}
              options={opcoesDetector}
              className="max-w-72"
            />
          )}
          {aba === "lista" && (
            <SelectFilter
              value={f.severidade}
              onChange={(v) => filters.set({ severidade: v })}
              placeholder={t("alerta.severidade")}
              options={SEVERIDADES.map((s) => ({ value: s, label: t(`alerta.severidades.${s}`) }))}
            />
          )}
          {aba === "ranking" && (
            <SelectFilter
              value={f.uf}
              onChange={(v) => filters.set({ uf: v })}
              placeholder="UF"
              options={UFS.map((u) => ({ value: u, label: u }))}
            />
          )}
        </FilterBar>

        <TabsContent value="ranking" className="mt-4 space-y-2">
          <p className="text-xs text-muted-foreground">{t("alerta.rankingHint")}</p>
          <DataTable
            columns={columns}
            data={ranking.data?.items ?? []}
            loading={ranking.loading}
            error={ranking.error}
            onRetry={ranking.reload}
            onRowClick={(r) => navigate(`/politicos/${r.politico_id}`)}
          />
        </TabsContent>

        <TabsContent value="lista" className="mt-4">
          <AlertasList
            detectores={detectores}
            params={{
              detector: f.detector || undefined,
              severidade: f.severidade || undefined,
              entidade: f.entidade || undefined,
            }}
          />
        </TabsContent>

        <TabsContent value="metodologia" className="mt-4 grid gap-4 md:grid-cols-2">
          {(catalogo.data?.detectores ?? []).map((d) => (
            <Card key={d.codigo} className="gap-3">
              <CardHeader className="flex flex-row items-start justify-between gap-2 space-y-0">
                <div>
                  <CardTitle className="text-base">{d.titulo}</CardTitle>
                  <p className="text-xs text-muted-foreground">
                    {t(`alerta.areas.${d.area}`)} · {t("alerta.confianca")} {(d.peso * 100).toFixed(0)}%
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => filters.set({ aba: "lista", detector: d.codigo })}
                >
                  {formatInt(d.alertas)} {t("alerta.alertas").toLowerCase()}
                </Button>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">{d.metodologia}</p>
                <div className="flex gap-2 text-xs">
                  <Badge className="bg-red-600 text-white">{d.alta} {t("alerta.severidades.alta").toLowerCase()}</Badge>
                  <Badge className="bg-amber-500 text-white">{d.media} {t("alerta.severidades.media").toLowerCase()}</Badge>
                  <Badge variant="outline">{d.baixa} {t("alerta.severidades.baixa").toLowerCase()}</Badge>
                </div>
              </CardContent>
            </Card>
          ))}
        </TabsContent>
      </Tabs>
    </>
  )
}
