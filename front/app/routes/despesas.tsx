import { useEffect } from "react"
import { IconCash, IconReceipt, IconReceiptRefund } from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import {
  DespesasTable,
  FornecedoresList,
  ResumoCharts,
} from "~/components/custom/despesas-panel"
import {
  ExportButton,
  FilterBar,
  SearchFilter,
  SelectFilter,
  monthOptions,
  yearOptions,
} from "~/components/custom/filters"
import { KpiGrid } from "~/components/custom/kpi"
import { PageHeader } from "~/components/custom/states"
import { useApi } from "~/context/api"
import { usePageTitle } from "~/context/page"
import { toParams, useFilters } from "~/hooks/use-filters"
import { useResource } from "~/hooks/use-resource"
import { UFS } from "~/interface/api"
import { formatBRL, formatInt, toNumber } from "~/lib/format"

const KEYS = [
  "ano",
  "mes",
  "verba",
  "uf",
  "categoria",
  "fornecedor",
  "data_inicio",
  "data_fim",
] as const
const NUMERIC = ["ano", "mes"] as const

export default function Despesas() {
  const { t, i18n } = useTranslation()
  const api = useApi()
  const filters = useFilters(KEYS)
  const params = toParams(filters.values, NUMERIC)
  usePageTitle(t("navigation.despesas"))

  // Sem filtro o resumo agrega milhões de linhas: começa no ano corrente.
  useEffect(() => {
    if (filters.key === "") filters.set({ ano: new Date().getFullYear() })
  }, [filters.key, filters.set])

  const ready = filters.key !== ""
  const resumo = useResource(() => api.despesasResumo(params), [filters.key], { enabled: ready })
  const r = resumo.data
  const media = r && r.quantidade ? toNumber(r.total) / r.quantidade : 0

  return (
    <>
      <PageHeader
        title={t("navigation.despesas")}
        description={t("despesa.listDesc")}
        actions={<ExportButton onExport={() => api.exportCsv("/despesas", params, "despesas")} />}
      />
      <FilterBar onClear={filters.clear} canClear={filters.key !== ""}>
        <SelectFilter
          value={filters.values.ano}
          onChange={(v) => filters.set({ ano: v })}
          placeholder={t("filters.ano")}
          options={yearOptions()}
        />
        <SelectFilter
          value={filters.values.mes}
          onChange={(v) => filters.set({ mes: v })}
          placeholder={t("filters.mes")}
          options={monthOptions(i18n.language)}
        />
        <SelectFilter
          value={filters.values.verba}
          onChange={(v) => filters.set({ verba: v })}
          placeholder={t("filters.verba")}
          options={[
            { value: "CEAP", label: t("verba.CEAP") },
            { value: "CEAPS", label: t("verba.CEAPS") },
          ]}
        />
        <SelectFilter
          value={filters.values.uf}
          onChange={(v) => filters.set({ uf: v })}
          placeholder="UF"
          options={UFS.map((u) => ({ value: u, label: u }))}
        />
        <SearchFilter
          value={filters.values.categoria}
          onChange={(v) => filters.set({ categoria: v })}
          placeholder={t("filters.categoria")}
        />
        <SearchFilter
          value={filters.values.fornecedor}
          onChange={(v) => filters.set({ fornecedor: v })}
          placeholder={t("filters.fornecedor")}
        />
        <SearchFilter
          type="date"
          className="sm:w-40"
          value={filters.values.data_inicio}
          onChange={(v) => filters.set({ data_inicio: v })}
          placeholder={t("filters.dataInicio")}
        />
        <SearchFilter
          type="date"
          className="sm:w-40"
          value={filters.values.data_fim}
          onChange={(v) => filters.set({ data_fim: v })}
          placeholder={t("filters.dataFim")}
        />
      </FilterBar>

      <KpiGrid
        className="xl:grid-cols-3"
        loading={resumo.loading}
        items={[
          { title: t("despesa.total"), value: formatBRL(r?.total), icon: IconCash },
          { title: t("despesa.documentos"), value: formatInt(r?.quantidade), icon: IconReceipt },
          { title: t("despesa.media"), value: formatBRL(media), icon: IconReceiptRefund },
        ]}
      />
      <ResumoCharts resumo={resumo} onCategoria={(c) => filters.set({ categoria: c })} />
      <FornecedoresList resumo={resumo} />
      <DespesasTable
        enabled={ready}
        deps={[filters.key]}
        fetcher={(cursor) => api.despesas({ ...params, cursor, limit: 50 })}
      />
    </>
  )
}
