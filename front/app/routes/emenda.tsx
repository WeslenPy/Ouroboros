import { Link, useNavigate, useParams } from "react-router"
import { IconBuildingBank, IconBuildingBridge, IconCash, IconPercentage } from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import { Badge } from "@/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/ui/table"
import { DataTable } from "~/components/custom/data-table"
import { KpiGrid } from "~/components/custom/kpi"
import { useObraColumns } from "~/components/custom/obras"
import { BlockSkeleton, EmptyState, ErrorState, PageHeader } from "~/components/custom/states"
import { MapaButton } from "~/components/grafo/mapa-button"
import { useApi } from "~/context/api"
import { usePageTitle } from "~/context/page"
import { useResource } from "~/hooks/use-resource"
import { formatBRL, formatDocumento, toNumber } from "~/lib/format"

export default function EmendaDetail() {
  const { codigo = "" } = useParams()
  const { t } = useTranslation()
  const api = useApi()
  const navigate = useNavigate()
  const obraColumns = useObraColumns()
  const emenda = useResource(() => api.emenda(codigo), [codigo])
  const e = emenda.data
  usePageTitle(e ? `${t("emenda.codigo")} ${e.codigo}` : undefined)

  if (emenda.error) return <ErrorState error={emenda.error} onRetry={emenda.reload} />
  if (!e) return <BlockSkeleton height={400} />

  const execucao = toNumber(e.empenhado) > 0 ? toNumber(e.pago) / toNumber(e.empenhado) : 0

  return (
    <>
      <PageHeader
        title={`${t("emenda.codigo")} ${e.codigo}`}
        description={
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span>{e.ano}</span>
            <span>{e.tipo}</span>
            {e.politico_id ? (
              <Link to={`/politicos/${e.politico_id}`} className="font-medium text-foreground hover:underline">
                {e.politico_nome ?? e.autor_nome}
              </Link>
            ) : (
              <span>{e.autor_nome}</span>
            )}
          </span>
        }
        actions={e.politico_id && <MapaButton no={`politico:${e.politico_id}`} ano={e.ano} />}
      >
        <div className="flex size-12 items-center justify-center rounded-lg bg-muted">
          <IconBuildingBank className="size-6 text-muted-foreground" />
        </div>
      </PageHeader>

      <KpiGrid
        items={[
          { title: t("emenda.empenhado"), value: formatBRL(e.empenhado, true), icon: IconCash },
          { title: t("emenda.pago"), value: formatBRL(e.pago, true), hint: t("emenda.pagoHint"), icon: IconCash },
          { title: t("emenda.execucao"), value: `${(execucao * 100).toFixed(1)}%`, icon: IconPercentage },
          {
            title: t("obra.convenios"),
            value: e.obras.length + e.transferencias_especiais.length,
            hint: t("emenda.execucaoComo"),
            icon: IconBuildingBridge,
          },
        ]}
      />

      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="gap-3 shadow-xs">
          <CardHeader>
            <CardTitle className="text-base">{t("emenda.destinos")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto rounded-lg border">
              <Table>
                <TableHeader className="bg-muted/60">
                  <TableRow>
                    <TableHead>{t("emenda.destino")}</TableHead>
                    <TableHead>{t("emenda.area")}</TableHead>
                    <TableHead className="text-right">{t("emenda.pago")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {e.destinos.map((d) => (
                    <TableRow key={d.id}>
                      <TableCell>
                        {d.municipio_codigo_ibge ? (
                          <Link to={`/entes/${d.municipio_codigo_ibge}`} className="hover:underline">
                            {d.municipio_nome} - {d.uf}
                          </Link>
                        ) : (
                          (d.localidade ?? "—")
                        )}
                      </TableCell>
                      <TableCell>
                        <p>{d.funcao ?? "—"}</p>
                        <p className="text-[11px] text-muted-foreground">{d.acao}</p>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatBRL(toNumber(d.valor_pago) + toNumber(d.valor_rp_pago))}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
        <Card className="gap-3 shadow-xs">
          <CardHeader>
            <CardTitle className="text-base">{t("emenda.maioresFavorecidos")}</CardTitle>
          </CardHeader>
          <CardContent>
            {e.favorecidos.length ? (
              <ol className="divide-y text-sm">
                {e.favorecidos.slice(0, 12).map((f, i) => (
                  <li key={`${f.chave}-${i}`} className="flex items-center gap-3 py-2">
                    <div className="min-w-0 flex-1">
                      {f.chave && /^\d{14}$/.test(f.chave) ? (
                        <Link to={`/fornecedores/${f.chave}`} className="block truncate font-medium hover:underline">
                          {f.rotulo}
                        </Link>
                      ) : (
                        <p className="truncate font-medium">{f.rotulo}</p>
                      )}
                      <p className="font-mono text-[11px] text-muted-foreground">{formatDocumento(f.chave)}</p>
                    </div>
                    <span className="tabular-nums">{formatBRL(f.pago, true)}</span>
                  </li>
                ))}
              </ol>
            ) : (
              <EmptyState height={120} className="border-none" />
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="gap-3 shadow-xs">
        <CardHeader>
          <CardTitle className="text-base">{t("emenda.obras")}</CardTitle>
        </CardHeader>
        <CardContent>
          {e.obras.length ? (
            <DataTable columns={obraColumns} data={e.obras} onRowClick={(o) => navigate(`/obras/${o.numero}`)} />
          ) : (
            <EmptyState height={120} className="border-none" title={t("emenda.semObras")} />
          )}
        </CardContent>
      </Card>

      {e.transferencias_especiais.length > 0 && (
        <Card className="gap-3 shadow-xs">
          <CardHeader>
            <CardTitle className="text-base">{t("emenda.transferencias")}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 lg:grid-cols-2">
            {e.transferencias_especiais.map((p) => (
              <div key={p.id} className="space-y-2 rounded-lg border p-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    {p.municipio_codigo_ibge ? (
                      <Link to={`/entes/${p.municipio_codigo_ibge}`} className="font-medium hover:underline">
                        {p.beneficiario_nome}
                      </Link>
                    ) : (
                      <p className="font-medium">{p.beneficiario_nome}</p>
                    )}
                    <p className="text-[11px] text-muted-foreground">
                      {p.codigo} · {p.uf} · {p.situacao}
                    </p>
                  </div>
                  <div className="text-right tabular-nums">
                    <p className="font-medium">
                      {formatBRL(toNumber(p.valor_investimento) + toNumber(p.valor_custeio), true)}
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      {t("obra.liberado")} {formatBRL(p.valor_pago, true)}
                    </p>
                  </div>
                </div>
                {p.areas && <Badge variant="outline">{p.areas}</Badge>}
                {p.executores.map((x, i) => (
                  <div key={i} className="border-t pt-2">
                    <p className="text-xs">{x.objeto ?? "—"}</p>
                    <p className="text-[11px] text-muted-foreground">
                      {x.nome} · {formatDocumento(x.cnpj)}
                    </p>
                  </div>
                ))}
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </>
  )
}
