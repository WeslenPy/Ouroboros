import { useState } from "react"
import { Link, useParams } from "react-router"
import { IconBuildingStore, IconCash, IconReceipt } from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import { DespesasTable, ResumoCharts } from "~/components/custom/despesas-panel"
import { ExportButton, SelectFilter, yearOptions } from "~/components/custom/filters"
import { MapaButton } from "~/components/grafo/mapa-button"
import { KpiGrid } from "~/components/custom/kpi"
import { ObrasTable } from "~/components/custom/obras"
import { PageHeader } from "~/components/custom/states"
import { useApi } from "~/context/api"
import { usePageTitle } from "~/context/page"
import { useResource } from "~/hooks/use-resource"
import type { Params } from "~/interface/api"
import { formatBRL, formatDocumento, formatInt } from "~/lib/format"

export default function Fornecedor() {
  const { documento = "" } = useParams()
  const { t } = useTranslation()
  const api = useApi()
  const [ano, setAno] = useState("")
  const filtro = { fornecedor: documento, ano: ano ? Number(ano) : undefined }

  const resumo = useResource(() => api.despesasResumo(filtro), [documento, ano])
  const nome = resumo.data?.maiores_fornecedores[0]?.fornecedor_nome ?? formatDocumento(documento)
  usePageTitle(nome, nome)

  return (
    <>
      <PageHeader
        title={nome}
        description={<span className="font-mono">{formatDocumento(documento)}</span>}
        actions={
          <>
            {/^\d{14}$/.test(documento) &&<MapaButton no={`doc:${documento}`} ano={ano} />}
            <SelectFilter value={ano} onChange={setAno} placeholder={t("filters.ano")} options={yearOptions()} />
            <ExportButton
              onExport={() => api.exportCsv("/despesas", filtro, `fornecedor_${documento}`)}
            />
          </>
        }
      >
        <div className="flex size-12 items-center justify-center rounded-lg bg-muted">
          <IconBuildingStore className="size-6 text-muted-foreground" />
        </div>
      </PageHeader>
      <KpiGrid
        className="xl:grid-cols-2"
        loading={resumo.loading}
        items={[
          { title: t("fornecedor.recebido"), value: formatBRL(resumo.data?.total), icon: IconCash },
          { title: t("despesa.documentos"), value: formatInt(resumo.data?.quantidade), icon: IconReceipt },
        ]}
      />
      <ResumoCharts resumo={resumo} />
      <DespesasTable
        deps={[documento, ano]}
        fetcher={(cursor) => api.despesas({ ...filtro, cursor, limit: 50 })}
      />
      {/^\d{14}$/.test(documento) && (
        <>
          <ObrasSecao titulo={t("fornecedor.obrasContratada")} params={{ fornecedor: documento, ano: filtro.ano }} deps={[documento, ano]} />
          <ObrasSecao titulo={t("fornecedor.obrasConvenente")} params={{ proponente: documento, ano: filtro.ano }} deps={[documento, ano]} />
        </>
      )}
    </>
  )
}

function ObrasSecao({ titulo, params, deps }: { titulo: string; params: Params; deps: unknown[] }) {
  const { t } = useTranslation()
  const api = useApi()
  // só mostra a seção se houver ao menos um convênio
  const existe = useResource(() => api.obras({ ...params, limit: 1 }), deps)
  if (!existe.data?.items.length) return null
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null) as [string, string][],
  )
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">{titulo}</h2>
        <Link to={`/obras?${qs}`} className="text-xs text-primary hover:underline">
          {t("common.verTudo")}
        </Link>
      </div>
      <ObrasTable params={params} deps={deps} />
    </div>
  )
}
