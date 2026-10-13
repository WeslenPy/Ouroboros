import { useMemo } from "react"
import { Link, useNavigate, useParams } from "react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { IconCash, IconTicket, IconTimeline, IconUserCheck } from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { SimpleBarChart } from "~/components/charts/bar-chart"
import { ChartCard } from "~/components/charts/chart-card"
import { DataTable } from "~/components/custom/data-table"
import { KpiGrid } from "~/components/custom/kpi"
import { useCargoLabel } from "~/components/custom/labels"
import { OrigemCard } from "~/components/custom/origem"
import { PartidoLogo } from "~/components/custom/partido-logo"
import { PoliticoAvatar } from "~/components/custom/politico-avatar"
import { BlockSkeleton, ErrorState, PageHeader } from "~/components/custom/states"
import { useApi } from "~/context/api"
import { usePageTitle } from "~/context/page"
import { useCursorList, useResource } from "~/hooks/use-resource"
import type { PoliticoResumo } from "~/interface/api"
import { formatBRL, formatInt } from "~/lib/format"

export default function PartidoDetail() {
  const { sigla = "" } = useParams()
  const { t } = useTranslation()
  const api = useApi()
  const navigate = useNavigate()
  const cargoLabel = useCargoLabel()

  const partido = useResource(() => api.partido(sigla), [sigla])
  const cand = useResource(() => api.candidaturasResumo({ partido: sigla }), [sigla])
  const membros = useCursorList(
    (cursor) => api.politicos({ partido: sigla, em_exercicio: true, cursor, limit: 50 }),
    [sigla],
  )
  const p = partido.data
  usePageTitle(p?.sigla, p?.sigla)

  const columns = useMemo<ColumnDef<PoliticoResumo>[]>(
    () => [
      {
        id: "nome",
        accessorKey: "nome",
        header: t("politico.nome"),
        cell: ({ row }) => (
          <div className="flex items-center gap-3">
            <PoliticoAvatar politico={row.original} className="size-8" />
            <span className="font-medium">{row.original.nome}</span>
          </div>
        ),
      },
      {
        id: "cargo",
        accessorFn: (r) => r.ultimo_mandato?.cargo ?? "",
        header: t("politico.ultimoCargo"),
        cell: ({ getValue }) => cargoLabel(getValue<string>()),
      },
      {
        id: "uf",
        accessorFn: (r) => r.ultimo_mandato?.uf ?? "",
        header: "UF",
      },
    ],
    [t, cargoLabel],
  )

  if (partido.error) return <ErrorState error={partido.error} onRetry={partido.reload} />
  if (!p) return <BlockSkeleton height={400} />

  return (
    <>
      <PageHeader
        title={
          <span className="flex items-center gap-3">
            {p.sigla}
            {!p.ativo && <Badge variant="outline">{t("partido.extinto")}</Badge>}
          </span>
        }
        description={p.nome}
        actions={
          <Button asChild variant="outline" size="sm">
            <Link to={`/candidaturas?partido=${encodeURIComponent(p.sigla)}`}>
              {t("partido.verCandidaturas")}
            </Link>
          </Button>
        }
      >
        <PartidoLogo partido={p} className="size-14 text-2xl" />
      </PageHeader>

      <KpiGrid
        items={[
          { title: t("kpi.emExercicio"), value: formatInt(p.politicos_em_exercicio), icon: IconUserCheck },
          { title: t("politico.mandatos"), value: formatInt(p.mandatos), icon: IconTimeline },
          {
            title: t("kpi.candidaturas"),
            value: formatInt(p.candidaturas),
            hint: t("kpi.eleitas", { count: p.candidaturas_eleitas }),
            icon: IconTicket,
          },
          {
            title: t("partido.gastoGabinete"),
            value: formatBRL(p.despesas_total, true),
            hint: t("common.docs", { count: p.despesas_quantidade }),
            icon: IconCash,
          },
        ]}
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard
          className="lg:col-span-2"
          title={t("candidatura.porAno")}
          loading={cand.loading}
          isEmpty={!cand.data?.por_ano.length}
        >
          <SimpleBarChart
            label={t("candidatura.naoEleitos")}
            secondaryLabel={t("candidatura.eleitos")}
            onSelect={(item) => navigate(`/candidaturas?partido=${p.sigla}&ano=${item.name}`)}
            data={(cand.data?.por_ano ?? []).map((a) => ({
              name: a.chave ?? "—",
              value: a.quantidade,
              secondary: a.eleitos,
            }))}
          />
        </ChartCard>
        <OrigemCard origem={p.origem} />
      </div>

      <h2 className="text-lg font-semibold">{t("partido.membros")}</h2>
      <DataTable
        columns={columns}
        data={membros.items}
        loading={membros.loading}
        error={membros.error}
        onRetry={membros.reload}
        hasMore={membros.hasMore}
        onLoadMore={membros.loadMore}
        onRowClick={(r) => navigate(`/politicos/${r.id}`)}
      />
    </>
  )
}
