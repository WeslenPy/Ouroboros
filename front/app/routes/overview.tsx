import { useState } from "react"
import { Link, useNavigate } from "react-router"
import {
  IconAlertTriangle,
  IconCash,
  IconClockHour4,
  IconFlag,
  IconMapPin,
  IconTicket,
  IconUserCheck,
  IconUsers,
} from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import { SimpleBarChart } from "~/components/charts/bar-chart"
import { TimeAreaChart } from "~/components/charts/area-chart"
import { ChartCard } from "~/components/charts/chart-card"
import { DonutChart } from "~/components/charts/pie-chart"
import { SelectFilter, yearOptions } from "~/components/custom/filters"
import { KpiGrid } from "~/components/custom/kpi"
import { StatusBadge, useCargoLabel } from "~/components/custom/labels"
import { ErrorState, PageHeader } from "~/components/custom/states"
import { Button } from "@/ui/button"
import { useApi } from "~/context/api"
import { usePageTitle } from "~/context/page"
import { useResource } from "~/hooks/use-resource"
import { formatBRL, formatDocumento, formatInt, formatRelative, monthLabel, toNumber } from "~/lib/format"

export default function Overview() {
  const { t } = useTranslation()
  const api = useApi()
  const navigate = useNavigate()
  const cargoLabel = useCargoLabel()
  const [ano, setAno] = useState(String(new Date().getFullYear()))
  usePageTitle(t("navigation.overview"))

  const stats = useResource(() => api.stats(), [])
  const resumo = useResource(() => api.despesasResumo({ ano: Number(ano) }), [ano])
  const fontes = useResource(() => api.fontes(), [], { pollMs: 30_000 })
  const s = stats.data
  const brl = (v: number) => formatBRL(v, true)

  if (stats.error) return <ErrorState error={stats.error} onRetry={stats.reload} />

  const falhas = fontes.data?.filter((f) => f.status === "falha").length ?? 0
  const rodando = fontes.data?.filter((f) => f.status === "rodando").length ?? 0

  return (
    <>
      <PageHeader
        title={t("overview.title")}
        description={t("overview.subtitle")}
        actions={
          s?.ultima_ingestao_em && (
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <IconClockHour4 className="size-4" />
              {t("overview.lastIngest", { when: formatRelative(s.ultima_ingestao_em) })}
            </span>
          )
        }
      />

      <KpiGrid
        loading={stats.loading}
        items={[
          {
            title: t("kpi.politicos"),
            value: formatInt(s?.politicos),
            hint: t("kpi.fotos", { count: s?.fotos ?? 0 }),
            icon: IconUsers,
            to: "/politicos",
          },
          {
            title: t("kpi.emExercicio"),
            value: formatInt(s?.politicos_em_exercicio),
            hint: t("kpi.mandatos", { count: s?.mandatos ?? 0 }),
            icon: IconUserCheck,
            to: "/politicos?em_exercicio=true",
          },
          {
            title: t("kpi.gastoTotal"),
            value: formatBRL(s?.despesas_total, true),
            hint: t("kpi.despesas", { count: s?.despesas ?? 0, semDono: formatInt(s?.despesas_sem_politico) }),
            icon: IconCash,
            to: "/despesas",
          },
          {
            title: t("kpi.candidaturas"),
            value: formatInt(s?.candidaturas, true),
            hint: t("kpi.eleitas", { count: s?.candidaturas_eleitas ?? 0 }),
            icon: IconTicket,
            to: "/candidaturas",
          },
          { title: t("kpi.partidos"), value: formatInt(s?.partidos), icon: IconFlag, to: "/partidos" },
          { title: t("kpi.entes"), value: formatInt(s?.entes), icon: IconMapPin, to: "/entes" },
          {
            title: t("kpi.matches"),
            value: formatInt(s?.matches_pendentes),
            hint: t("kpi.matchesHint"),
            icon: IconAlertTriangle,
            to: "/matches",
          },
          {
            title: t("kpi.fontes"),
            value: fontes.data ? `${fontes.data.length - falhas - rodando}/${fontes.data.length}` : "—",
            hint: t("kpi.fontesHint", { falhas, rodando }),
            icon: IconClockHour4,
            to: "/fontes",
          },
        ]}
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard
          className="lg:col-span-2"
          title={t("overview.gastoMensal")}
          description={
            resumo.data
              ? t("overview.gastoMensalDesc", {
                  total: formatBRL(resumo.data.total),
                  count: resumo.data.quantidade,
                })
              : undefined
          }
          action={
            <SelectFilter
              value={ano}
              onChange={(v) => setAno(v || String(new Date().getFullYear()))}
              options={yearOptions()}
              placeholder={t("filters.ano")}
            />
          }
          loading={resumo.loading}
          isEmpty={!resumo.data?.por_mes.length}
        >
          <TimeAreaChart
            label={t("common.valor")}
            valueFormatter={brl}
            data={(resumo.data?.por_mes ?? []).map((m) => ({
              label: monthLabel(m.ano, m.mes),
              value: toNumber(m.total),
            }))}
          />
        </ChartCard>
        <ChartCard
          title={t("overview.porVerba")}
          description={t("overview.porVerbaDesc")}
          loading={stats.loading}
          isEmpty={!s?.despesas_por_verba.length}
        >
          <DonutChart
            valueFormatter={brl}
            data={(s?.despesas_por_verba ?? []).map((v) => ({ name: v.verba, value: toNumber(v.total) }))}
          />
        </ChartCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard
          title={t("overview.porCargo")}
          loading={stats.loading}
          isEmpty={!s?.em_exercicio_por_cargo.length}
        >
          <DonutChart
            othersLabel={t("common.outros")}
            data={(s?.em_exercicio_por_cargo ?? []).map((c) => ({
              name: cargoLabel(c.chave),
              value: c.quantidade,
            }))}
          />
        </ChartCard>
        <ChartCard
          className="lg:col-span-2"
          title={t("overview.porPartido")}
          description={t("overview.clickToFilter")}
          loading={stats.loading}
          isEmpty={!s?.em_exercicio_por_partido.length}
          height={360}
        >
          <SimpleBarChart
            height={360}
            label={t("common.quantidade")}
            colorful
            onSelect={(item) => item.name !== t("common.multiplos") && navigate(`/partidos/${item.name}`)}
            data={(s?.em_exercicio_por_partido ?? []).slice(0, 20).map((p) => ({
              name: p.chave ?? t("common.multiplos"),
              value: p.quantidade,
            }))}
          />
        </ChartCard>
      </div>

      <ChartCard
        title={t("overview.porUf")}
        description={t("overview.clickToFilter")}
        loading={stats.loading}
        isEmpty={!s?.em_exercicio_por_uf.length}
      >
        <SimpleBarChart
          label={t("common.quantidade")}
          onSelect={(item) => navigate(`/politicos?em_exercicio=true&uf=${item.name}`)}
          data={(s?.em_exercicio_por_uf ?? []).map((u) => ({ name: u.chave ?? "—", value: u.quantidade }))}
        />
      </ChartCard>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title={t("overview.topCategorias", { ano })}
          loading={resumo.loading}
          isEmpty={!resumo.data?.por_categoria.length}
          height={360}
        >
          <SimpleBarChart
            layout="horizontal"
            height={360}
            label={t("common.valor")}
            valueFormatter={brl}
            onSelect={(item) => navigate(`/despesas?ano=${ano}&categoria=${encodeURIComponent(item.name)}`)}
            data={(resumo.data?.por_categoria ?? []).slice(0, 10).map((c) => ({
              name: c.categoria,
              value: toNumber(c.total),
            }))}
          />
        </ChartCard>
        <ChartCard
          title={t("overview.topFornecedores", { ano })}
          loading={resumo.loading}
          isEmpty={!resumo.data?.maiores_fornecedores.length}
          height={360}
        >
          <ol className="divide-y text-sm">
            {(resumo.data?.maiores_fornecedores ?? []).slice(0, 10).map((f, i) => (
              <li key={`${f.fornecedor_documento}-${i}`} className="flex items-center gap-3 py-2">
                <span className="w-5 text-right text-xs text-muted-foreground tabular-nums">{i + 1}</span>
                <div className="min-w-0 flex-1">
                  {f.fornecedor_documento ? (
                    <Link
                      to={`/fornecedores/${encodeURIComponent(f.fornecedor_documento)}`}
                      className="block truncate font-medium hover:underline"
                    >
                      {f.fornecedor_nome ?? formatDocumento(f.fornecedor_documento)}
                    </Link>
                  ) : (
                    <span className="block truncate font-medium">{f.fornecedor_nome ?? "—"}</span>
                  )}
                  <span className="text-xs text-muted-foreground">
                    {formatDocumento(f.fornecedor_documento)} · {t("common.docs", { count: f.quantidade })}
                  </span>
                </div>
                <span className="font-medium tabular-nums">{formatBRL(f.total, true)}</span>
              </li>
            ))}
          </ol>
        </ChartCard>
      </div>

      <ChartCard
        title={t("overview.fontes")}
        action={
          <Button asChild variant="ghost" size="sm">
            <Link to="/fontes">{t("common.verTudo")}</Link>
          </Button>
        }
        loading={fontes.loading && !fontes.data}
        isEmpty={!fontes.data?.length}
        height={160}
      >
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {fontes.data?.map((f) => (
            <div
              key={`${f.fonte}-${f.recurso}-${f.particao}`}
              className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">
                  {f.fonte}/{f.recurso} <span className="text-muted-foreground">· {f.particao}</span>
                </p>
                <p className="text-xs text-muted-foreground">
                  {formatInt(f.registros)} {t("common.registros")} · {formatRelative(f.finalizado_em ?? f.iniciado_em)}
                </p>
              </div>
              <StatusBadge status={f.status} />
            </div>
          ))}
        </div>
      </ChartCard>
    </>
  )
}
