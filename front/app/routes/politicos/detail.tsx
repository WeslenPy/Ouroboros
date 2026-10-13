import { useState } from "react"
import { Link, useParams } from "react-router"
import {
  IconCake,
  IconCash,
  IconId,
  IconPhoto,
  IconTicket,
  IconTimeline,
} from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import { Badge } from "@/ui/badge"
import { Card, CardContent } from "@/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/ui/tabs"
import { SimpleBarChart } from "~/components/charts/bar-chart"
import { ChartCard } from "~/components/charts/chart-card"
import {
  DespesasTable,
  FornecedoresList,
  ResumoCharts,
} from "~/components/custom/despesas-panel"
import { ExportButton, SelectFilter, yearOptions } from "~/components/custom/filters"
import { MapaButton } from "~/components/grafo/mapa-button"
import { KpiGrid } from "~/components/custom/kpi"
import { useCargoLabel, useEsferaLabel } from "~/components/custom/labels"
import { PoliticoAvatar } from "~/components/custom/politico-avatar"
import { BlockSkeleton, EmptyState, ErrorState, PageHeader } from "~/components/custom/states"
import { useApi } from "~/context/api"
import { usePageTitle } from "~/context/page"
import { useResource } from "~/hooks/use-resource"
import type { MandatoOut } from "~/interface/api"
import { formatBRL, formatDate, formatInt, toNumber } from "~/lib/format"
import { cn } from "~/lib/utils"

function emCurso(m: MandatoOut): boolean {
  const hoje = new Date().toISOString().slice(0, 10)
  return !!m.inicio && m.inicio <= hoje && (!m.fim || m.fim >= hoje)
}

export default function PoliticoDetail() {
  const { id = "" } = useParams()
  const { t } = useTranslation()
  const api = useApi()
  const cargoLabel = useCargoLabel()
  const esferaLabel = useEsferaLabel()
  const [tab, setTab] = useState("despesas")
  const [ano, setAno] = useState("")

  const politico = useResource(() => api.politico(id), [id])
  const p = politico.data
  usePageTitle(p?.nome, p?.nome)

  const resumo = useResource(
    () => api.politicoDespesasResumo(id, ano ? { ano: Number(ano) } : {}),
    [id, ano],
  )
  const candidaturas = useResource(() => api.politicoCandidaturas(id), [id], {
    enabled: tab === "candidaturas",
  })
  const fotos = useResource(() => api.politicoFotos(id), [id], { enabled: tab === "fotos" })

  if (politico.error) return <ErrorState error={politico.error} onRetry={politico.reload} />
  if (!p) return <BlockSkeleton height={400} />

  const totalGasto = p.gastos_gabinete_por_ano.reduce((acc, a) => acc + toNumber(a.total), 0)
  const atual = p.mandatos.find(emCurso)
  const m = p.ultimo_mandato

  return (
    <>
      <PageHeader
        title={p.nome}
        description={
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            {p.nome_civil && <span>{p.nome_civil}</span>}
            {p.data_nascimento && (
              <span className="inline-flex items-center gap-1">
                <IconCake className="size-3.5" /> {formatDate(p.data_nascimento)}
              </span>
            )}
            {p.genero && <span>{t(`genero.${p.genero}`, p.genero)}</span>}
          </span>
        }
        actions={
          m && (
            <div className="flex flex-wrap items-center gap-2">
              <MapaButton no={`politico:${p.id}`} />
              {atual && (
                <Badge className="bg-emerald-500/15 text-emerald-700 dark:text-emerald-400">
                  {t("politico.emExercicio")}
                </Badge>
              )}
              <Badge variant="outline">{cargoLabel(m.cargo)}</Badge>
              {(m.partido_sigla ?? m.partidos.at(-1)) && (
                <Badge variant="secondary" asChild>
                  <Link to={`/partidos/${m.partido_sigla ?? m.partidos.at(-1)}`}>
                    {m.partido_sigla ?? m.partidos.join(" → ")}
                  </Link>
                </Badge>
              )}
              {m.uf && <Badge variant="outline">{m.uf}</Badge>}
            </div>
          )
        }
      >
        <PoliticoAvatar politico={p} className="size-16 text-lg" />
      </PageHeader>

      <KpiGrid
        items={[
          {
            title: t("politico.gastoGabinete"),
            value: formatBRL(totalGasto, true),
            hint: t("politico.anosComGasto", { count: p.gastos_gabinete_por_ano.length }),
            icon: IconCash,
          },
          { title: t("politico.mandatos"), value: formatInt(p.mandatos.length), icon: IconTimeline },
          { title: t("politico.candidaturas"), value: formatInt(p.candidaturas), icon: IconTicket },
          { title: t("politico.identificadores"), value: formatInt(p.identificadores.length), icon: IconId },
        ]}
      />

      {p.gastos_gabinete_por_ano.length > 0 && (
        <ChartCard title={t("politico.gastoPorAno")} description={t("overview.clickToFilter")} height={200}>
          <SimpleBarChart
            height={200}
            label={t("common.valor")}
            valueFormatter={(v) => formatBRL(v, true)}
            onSelect={(item) => {
              setAno(item.name)
              setTab("despesas")
            }}
            data={p.gastos_gabinete_por_ano.map((a) => ({ name: String(a.ano), value: toNumber(a.total) }))}
          />
        </ChartCard>
      )}

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="max-w-full overflow-x-auto">
          <TabsTrigger value="despesas">
            <IconCash /> {t("politico.tabs.despesas")}
          </TabsTrigger>
          <TabsTrigger value="mandatos">
            <IconTimeline /> {t("politico.tabs.mandatos")} ({p.mandatos.length})
          </TabsTrigger>
          <TabsTrigger value="candidaturas">
            <IconTicket /> {t("politico.tabs.candidaturas")} ({p.candidaturas})
          </TabsTrigger>
          <TabsTrigger value="fotos">
            <IconPhoto /> {t("politico.tabs.fotos")}
          </TabsTrigger>
          <TabsTrigger value="ids">
            <IconId /> {t("politico.tabs.ids")}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="despesas" className="mt-4 flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <SelectFilter
              value={ano}
              onChange={setAno}
              placeholder={t("filters.ano")}
              options={yearOptions()}
            />
            <ExportButton
              onExport={() =>
                api.exportCsv(`/politicos/${id}/despesas`, { ano }, `despesas_politico_${id}`)
              }
            />
          </div>
          <ResumoCharts resumo={resumo} />
          <FornecedoresList resumo={resumo} />
          <DespesasTable
            showParlamentar={false}
            deps={[id, ano]}
            fetcher={(cursor) =>
              api.politicoDespesas(id, { ano: ano || undefined, cursor, limit: 50 })
            }
          />
        </TabsContent>

        <TabsContent value="mandatos" className="mt-4">
          {p.mandatos.length ? (
            <ol className="relative ml-3 border-l">
              {p.mandatos.map((mandato, i) => (
                <li key={i} className="mb-6 ml-6">
                  <span
                    className={cn(
                      "absolute -left-1.5 mt-1.5 size-3 rounded-full border-2 border-background",
                      emCurso(mandato) ? "bg-emerald-500" : "bg-muted-foreground/40",
                    )}
                  />
                  <Card className="gap-2 py-4">
                    <CardContent className="flex flex-wrap items-center justify-between gap-3 px-4">
                      <div>
                        <p className="font-medium">
                          {cargoLabel(mandato.cargo)}
                          {mandato.uf && <span className="text-muted-foreground"> · {mandato.uf}</span>}
                        </p>
                        <p className="text-xs text-muted-foreground tabular-nums">
                          {formatDate(mandato.inicio)} – {formatDate(mandato.fim)}
                          {mandato.legislatura && ` · ${t("politico.legislatura", { n: mandato.legislatura })}`}
                          {mandato.condicao && ` · ${mandato.condicao}`}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        <Badge variant="outline">{esferaLabel(mandato.esfera)}</Badge>
                        {mandato.partidos.map((sigla) => (
                          <Badge key={sigla} variant="secondary" asChild>
                            <Link to={`/partidos/${sigla}`}>{sigla}</Link>
                          </Badge>
                        ))}
                        <Badge variant="outline" className="font-mono text-[10px]">
                          {mandato.origem}
                        </Badge>
                      </div>
                    </CardContent>
                  </Card>
                </li>
              ))}
            </ol>
          ) : (
            <EmptyState />
          )}
        </TabsContent>

        <TabsContent value="candidaturas" className="mt-4">
          {candidaturas.loading ? (
            <BlockSkeleton />
          ) : candidaturas.error ? (
            <ErrorState error={candidaturas.error} onRetry={candidaturas.reload} />
          ) : !candidaturas.data?.length ? (
            <EmptyState />
          ) : (
            <div className="overflow-hidden rounded-lg border">
              <Table>
                <TableHeader className="bg-muted/60">
                  <TableRow>
                    <TableHead>{t("candidatura.ano")}</TableHead>
                    <TableHead>{t("candidatura.cargo")}</TableHead>
                    <TableHead>{t("candidatura.local")}</TableHead>
                    <TableHead>{t("candidatura.nomeUrna")}</TableHead>
                    <TableHead>{t("candidatura.partido")}</TableHead>
                    <TableHead>{t("candidatura.situacao")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {candidaturas.data.map((c) => (
                    <TableRow key={c.sq_candidato}>
                      <TableCell className="tabular-nums">
                        {c.ano} <span className="text-xs text-muted-foreground">{c.turno}º</span>
                      </TableCell>
                      <TableCell>{c.cargo}</TableCell>
                      <TableCell>{c.ue_nome}</TableCell>
                      <TableCell>
                        {c.nome_urna}
                        {c.numero_urna && (
                          <span className="ml-1 font-mono text-xs text-muted-foreground">{c.numero_urna}</span>
                        )}
                      </TableCell>
                      <TableCell>{c.partido_sigla ?? "—"}</TableCell>
                      <TableCell>
                        <Badge
                          variant={c.eleito ? "default" : "outline"}
                          className={cn(c.eleito && "bg-emerald-600 text-white")}
                        >
                          {c.situacao_turno ?? c.situacao_candidatura ?? "—"}
                        </Badge>
                        {c.motivos_situacao.length > 0 && (
                          <p className="mt-1 text-xs text-muted-foreground">{c.motivos_situacao.join(" · ")}</p>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>

        <TabsContent value="fotos" className="mt-4">
          {fotos.loading ? (
            <BlockSkeleton />
          ) : !fotos.data?.length ? (
            <EmptyState />
          ) : (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
              {fotos.data.map((f) => (
                <a
                  key={f.id}
                  href={f.url_origem}
                  target="_blank"
                  rel="noreferrer"
                  className="group overflow-hidden rounded-lg border"
                >
                  <img
                    src={api.url(f.url)}
                    alt={`${p.nome} ${f.ano ?? ""}`}
                    loading="lazy"
                    className="aspect-[3/4] w-full object-cover transition-transform group-hover:scale-105"
                  />
                  <div className="flex items-center justify-between px-2 py-1.5 text-xs">
                    <span className="font-medium">{f.origem}</span>
                    <span className="text-muted-foreground">{f.ano ?? "—"}</span>
                  </div>
                </a>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="ids" className="mt-4">
          <div className="overflow-hidden rounded-lg border">
            <Table>
              <TableHeader className="bg-muted/60">
                <TableRow>
                  <TableHead>{t("politico.origem")}</TableHead>
                  <TableHead>{t("politico.idExterno")}</TableHead>
                  <TableHead>{t("politico.metodo")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {p.identificadores.map((i) => (
                  <TableRow key={`${i.origem}-${i.id_externo}`}>
                    <TableCell className="font-medium">{i.origem}</TableCell>
                    <TableCell className="font-mono text-xs">{i.id_externo}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{t(`metodo.${i.metodo}`, i.metodo)}</Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>
      </Tabs>
    </>
  )
}
