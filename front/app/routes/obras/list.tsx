import { Link } from "react-router"
import {
  IconAffiliate,
  IconAlertTriangle,
  IconBuildingBridge,
  IconCash,
  IconMapPin,
} from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import { SimpleBarChart } from "~/components/charts/bar-chart"
import { ChartCard } from "~/components/charts/chart-card"
import { DonutChart } from "~/components/charts/pie-chart"
import {
  ExportButton,
  FilterBar,
  SearchFilter,
  SelectFilter,
  boolOptions,
  yearOptions,
} from "~/components/custom/filters"
import { KpiGrid } from "~/components/custom/kpi"
import { ObrasMapa, ObrasTable } from "~/components/custom/obras"
import { PageHeader } from "~/components/custom/states"
import { useApi } from "~/context/api"
import { usePageTitle } from "~/context/page"
import { toParams, useFilters } from "~/hooks/use-filters"
import { useResource } from "~/hooks/use-resource"
import { UFS, type TotalObras } from "~/interface/api"
import { formatBRL, formatDocumento, formatInt, toNumber } from "~/lib/format"

const KEYS = [
  "ano",
  "uf",
  "situacao",
  "q",
  "parada",
  "com_local",
  "emendas",
  "politico",
  "municipio",
  "fornecedor",
  "proponente",
  "emenda",
] as const
const NUMERIC = ["ano", "politico", "municipio"] as const

const SITUACOES = ["Em execução", "Concluída", "Aprovada", "Prestação de Contas", "Rescindido", "Anulado"]

function Ranking({
  titulo,
  itens,
  loading,
  link,
  grafo,
  valor,
}: {
  titulo: string
  itens: TotalObras[]
  loading: boolean
  link?: (c: string) => string
  grafo?: (c: string) => string
  valor: (i: TotalObras) => string
}) {
  const { t } = useTranslation()
  return (
    <ChartCard title={titulo} loading={loading} isEmpty={!itens.length} height={300}>
      <ol className="divide-y text-sm">
        {itens.slice(0, 10).map((item, i) => (
          <li key={`${item.chave}-${i}`} className="flex items-center gap-3 py-2">
            <span className="w-5 text-right text-xs text-muted-foreground">{i + 1}</span>
            <div className="min-w-0 flex-1">
              {item.chave && link ? (
                <Link to={link(item.chave)} className="block truncate font-medium hover:underline">
                  {item.rotulo ?? item.chave}
                </Link>
              ) : (
                <p className="truncate font-medium">{item.rotulo ?? item.chave ?? "—"}</p>
              )}
              <p className="text-[11px] text-muted-foreground">
                {t("obra.qtd", { count: item.quantidade })}
              </p>
            </div>
            <span className="text-right text-xs font-medium tabular-nums">{valor(item)}</span>
            {item.chave && grafo && (
              <Link
                to={grafo(item.chave)}
                title={t("grafo.verRede")}
                className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <IconAffiliate className="size-4" />
              </Link>
            )}
          </li>
        ))}
      </ol>
    </ChartCard>
  )
}

export default function Obras() {
  const { t } = useTranslation()
  const api = useApi()
  const filters = useFilters(KEYS)
  const params = toParams(filters.values, NUMERIC)
  usePageTitle(t("navigation.obras"))

  const resumo = useResource(() => api.obrasResumo(params), [filters.key])
  const mapa = useResource(() => api.obrasMapa({ ...params, limite: 3000 }), [filters.key])
  const r = resumo.data
  const brl = (v: number) => formatBRL(v, true)

  return (
    <>
      <PageHeader
        title={t("navigation.obras")}
        description={t("obra.listDesc")}
        actions={<ExportButton onExport={() => api.exportCsv("/obras", params, "obras")} />}
      />
      <FilterBar onClear={filters.clear} canClear={filters.key !== ""}>
        <SelectFilter
          value={filters.values.ano}
          onChange={(v) => filters.set({ ano: v })}
          placeholder={t("filters.ano")}
          options={yearOptions(2008)}
        />
        <SelectFilter
          value={filters.values.uf}
          onChange={(v) => filters.set({ uf: v })}
          placeholder="UF"
          options={UFS.map((u) => ({ value: u, label: u }))}
        />
        <SelectFilter
          value={filters.values.situacao}
          onChange={(v) => filters.set({ situacao: v })}
          placeholder={t("obra.situacao")}
          options={SITUACOES.map((s) => ({ value: s, label: s }))}
        />
        <SelectFilter
          value={filters.values.parada}
          onChange={(v) => filters.set({ parada: v })}
          placeholder={t("obra.parada")}
          options={boolOptions(t)}
        />
        <SelectFilter
          value={filters.values.emendas}
          onChange={(v) => filters.set({ emendas: v })}
          placeholder={t("obra.comEmenda")}
          options={boolOptions(t)}
        />
        <SearchFilter
          value={filters.values.q}
          onChange={(v) => filters.set({ q: v })}
          placeholder={t("obra.filtroObjeto")}
          minLength={3}
        />
      </FilterBar>

      <KpiGrid
        loading={resumo.loading}
        items={[
          { title: t("obra.convenios"), value: formatInt(r?.quantidade), icon: IconBuildingBridge },
          {
            title: t("obra.valorGlobal"),
            value: formatBRL(r?.valor_global, true),
            hint: t("obra.repasseHint", { valor: formatBRL(r?.valor_repasse, true) }),
            icon: IconCash,
          },
          {
            title: t("obra.liberado"),
            value: formatBRL(r?.valor_desembolsado, true),
            hint: t("obra.liberadoHint"),
            icon: IconCash,
          },
          {
            title: t("obra.paradas"),
            value: formatInt(r?.paradas),
            hint: t("obra.paradasHint", { count: r?.com_localizacao ?? 0 }),
            icon: IconAlertTriangle,
            to: "/obras?parada=true",
          },
        ]}
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard
          className="lg:col-span-2"
          title={t("obra.mapa")}
          description={t("obra.mapaDesc")}
          loading={mapa.loading}
          isEmpty={!mapa.data?.length}
          height={420}
          action={<IconMapPin className="size-4 text-muted-foreground" />}
        >
          <ObrasMapa pontos={mapa.data ?? []} />
        </ChartCard>
        <ChartCard title={t("obra.porSituacao")} loading={resumo.loading} isEmpty={!r?.por_situacao.length} height={420}>
          <DonutChart
            valueFormatter={brl}
            data={(r?.por_situacao ?? []).slice(0, 8).map((x) => ({
              name: x.chave ?? t("obra.semSituacao"),
              value: toNumber(x.valor_global),
            }))}
          />
        </ChartCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title={t("obra.porAno")} loading={resumo.loading} isEmpty={!r?.por_ano.length}>
          <SimpleBarChart
            label={t("obra.valorGlobal")}
            secondaryLabel={t("obra.liberado")}
            valueFormatter={brl}
            onSelect={(item) => filters.set({ ano: item.name })}
            data={(r?.por_ano ?? []).map((a) => ({
              name: a.chave ?? "—",
              value: toNumber(a.valor_global),
              secondary: toNumber(a.valor_desembolsado),
            }))}
          />
        </ChartCard>
        <ChartCard title={t("obra.porUf")} loading={resumo.loading} isEmpty={!r?.por_uf.length}>
          <SimpleBarChart
            label={t("obra.valorGlobal")}
            valueFormatter={brl}
            onSelect={(item) => item.name !== "—" && filters.set({ uf: item.name })}
            data={(r?.por_uf ?? []).map((u) => ({ name: u.chave ?? "—", value: toNumber(u.valor_global) }))}
          />
        </ChartCard>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Ranking
          titulo={t("obra.maioresAutores")}
          itens={r?.maiores_autores ?? []}
          loading={resumo.loading}
          link={(c) => `/politicos/${c}`}
          grafo={(c) => `/grafo?no=politico:${c}`}
          valor={(i) => formatBRL(i.valor_global, true)}
        />
        <Ranking
          titulo={t("obra.maioresFornecedores")}
          itens={(r?.maiores_fornecedores ?? []).map((f) => ({
            ...f,
            rotulo: `${f.rotulo ?? ""} · ${formatDocumento(f.chave)}`,
          }))}
          loading={resumo.loading}
          link={(c) => `/fornecedores/${c}`}
          grafo={(c) => `/grafo?no=doc:${c}`}
          valor={(i) => `${formatBRL(i.valor_global, true)} / ${formatBRL(i.valor_desembolsado, true)}`}
        />
        <Ranking
          titulo={t("obra.porOrgao")}
          itens={r?.por_orgao ?? []}
          loading={resumo.loading}
          valor={(i) => formatBRL(i.valor_global, true)}
        />
      </div>

      <ObrasTable params={params} deps={[filters.key]} />
    </>
  )
}
