import type { ReactNode } from "react"
import { Link, useParams } from "react-router"
import {
  IconBuildingBridge,
  IconCash,
  IconExternalLink,
  IconMapPin,
  IconPercentage,
  IconReceipt,
} from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/ui/table"
import { KpiGrid } from "~/components/custom/kpi"
import { ExecucaoBar, SituacaoObra, tituloObra } from "~/components/custom/obras"
import { BlockSkeleton, EmptyState, ErrorState, PageHeader } from "~/components/custom/states"
import { MapaButton } from "~/components/grafo/mapa-button"
import { useApi } from "~/context/api"
import { usePageTitle } from "~/context/page"
import { useResource } from "~/hooks/use-resource"
import { formatBRL, formatDate, formatDocumento, formatInt, toNumber } from "~/lib/format"
import { cn } from "~/lib/utils"

function Secao({ titulo, children, className }: { titulo: ReactNode; children: ReactNode; className?: string }) {
  return (
    <Card className={cn("gap-3 shadow-xs", className)}>
      <CardHeader>
        <CardTitle className="text-base">{titulo}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

function Tabela({ cabecalho, linhas }: { cabecalho: ReactNode[]; linhas: ReactNode[][] }) {
  if (!linhas.length) return <EmptyState height={120} className="border-none" />
  return (
    <div className="overflow-x-auto rounded-lg border">
      <Table>
        <TableHeader className="bg-muted/60">
          <TableRow>
            {cabecalho.map((c, i) => (
              <TableHead key={i}>{c}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {linhas.map((l, i) => (
            <TableRow key={i}>
              {l.map((c, j) => (
                <TableCell key={j} className="align-top">
                  {c}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function Documento({ doc, nome }: { doc: string | null; nome: string | null }) {
  if (doc && /^\d{14}$/.test(doc)) {
    return (
      <div>
        <Link to={`/fornecedores/${doc}`} className="font-medium hover:underline">
          {nome ?? doc}
        </Link>
        <p className="font-mono text-[11px] text-muted-foreground">{formatDocumento(doc)}</p>
      </div>
    )
  }
  return (
    <div>
      <p className="font-medium">{nome ?? "—"}</p>
      {doc && <p className="font-mono text-[11px] text-muted-foreground">{doc}</p>}
    </div>
  )
}

export default function ObraDetail() {
  const { numero = "" } = useParams()
  const { t } = useTranslation()
  const api = useApi()
  const obra = useResource(() => api.obra(numero), [numero])
  const o = obra.data
  const titulo = o ? tituloObra(o) : undefined
  usePageTitle(titulo, titulo)

  if (obra.error) return <ErrorState error={obra.error} onRetry={obra.reload} />
  if (!o) return <BlockSkeleton height={400} />

  const datas: [string, string | null][] = [
    [t("obra.datas.proposta"), o.data_proposta],
    [t("obra.datas.assinatura"), o.data_assinatura],
    [t("obra.datas.inicioVigencia"), o.inicio_vigencia],
    [t("obra.datas.inicioObra"), o.inicio_obra],
    [t("obra.datas.ultimaMedicao"), o.ultima_medicao],
    [t("obra.datas.fimVigencia"), o.fim_vigencia],
    [t("obra.datas.fimOriginal"), o.fim_vigencia_original],
    [t("obra.datas.prestacaoContas"), o.limite_prestacao_contas],
  ]
  const temCoordenada = o.latitude !== null && o.longitude !== null
  const osm = temCoordenada
    ? `https://www.openstreetmap.org/?mlat=${o.latitude}&mlon=${o.longitude}#map=16/${o.latitude}/${o.longitude}`
    : null

  return (
    <>
      <PageHeader
        title={titulo}
        description={
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span>
              {t("obra.convenio")} {o.numero} · {o.ano}
            </span>
            {o.modalidade && <Badge variant="outline">{o.modalidade}</Badge>}
            {o.orgao_superior && <span>{o.orgao_superior}</span>}
          </span>
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <MapaButton no={`obra:${o.numero}`} />
            <Button asChild variant="outline" size="sm">
              <a href={o.link_transferegov} target="_blank" rel="noreferrer">
                <IconExternalLink /> Transferegov
              </a>
            </Button>
            {o.link_obrasgov && (
              <Button asChild variant="outline" size="sm">
                <a href={o.link_obrasgov} target="_blank" rel="noreferrer">
                  <IconExternalLink /> Obrasgov
                </a>
              </Button>
            )}
          </div>
        }
      >
        <div className="flex size-12 items-center justify-center rounded-lg bg-muted">
          <IconBuildingBridge className="size-6 text-muted-foreground" />
        </div>
      </PageHeader>

      <KpiGrid
        items={[
          {
            title: t("obra.valorGlobal"),
            value: formatBRL(o.valor_global, true),
            hint: t("obra.repasseContrapartida", {
              repasse: formatBRL(o.valor_repasse, true),
              contrapartida: formatBRL(o.valor_contrapartida, true),
            }),
            icon: IconCash,
          },
          {
            title: t("obra.liberado"),
            value: formatBRL(o.valor_desembolsado, true),
            hint: t("obra.empenhadoHint", { valor: formatBRL(o.valor_empenhado, true) }),
            icon: IconCash,
          },
          {
            title: t("obra.pagoFornecedores"),
            value: formatBRL(o.valor_pago_fornecedores, true),
            hint: o.valor_saldo_conta !== null ? t("obra.saldoConta", { valor: formatBRL(o.valor_saldo_conta, true) }) : undefined,
            icon: IconReceipt,
          },
          {
            title: t("obra.execucao"),
            value: o.percentual_execucao !== null ? `${toNumber(o.percentual_execucao).toFixed(0)}%` : "—",
            hint:
              o.dias_sem_medicao !== null
                ? t("obra.diasSemMedicao", { count: o.dias_sem_medicao })
                : t("obra.semAcompanhamento"),
            icon: IconPercentage,
          },
        ]}
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Secao titulo={t("obra.situacao")}>
          <div className="space-y-3 text-sm">
            <SituacaoObra obra={o} />
            {o.subsituacao && <p className="text-xs text-muted-foreground">{o.subsituacao}</p>}
            <ExecucaoBar percentual={o.percentual_execucao} />
            {(o.prorrogacoes || o.aditivos) && (
              <p className="text-xs text-muted-foreground">
                {t("obra.prorrogacoes", { count: o.prorrogacoes ?? 0 })} ·{" "}
                {t("obra.aditivos", { count: o.aditivos ?? 0 })}
              </p>
            )}
            <p className="text-xs text-muted-foreground">{o.objeto}</p>
          </div>
        </Secao>
        <Secao titulo={t("obra.datas.titulo")}>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            {datas.map(([label, valor]) => (
              <div key={label}>
                <dt className="text-xs text-muted-foreground">{label}</dt>
                <dd className="font-medium tabular-nums">{formatDate(valor)}</dd>
              </div>
            ))}
          </dl>
        </Secao>
        <Secao
          titulo={
            <span className="flex items-center gap-2">
              <IconMapPin className="size-4" /> {t("obra.local")}
            </span>
          }
        >
          <div className="space-y-2 text-sm">
            {o.municipio_codigo_ibge ? (
              <Link to={`/entes/${o.municipio_codigo_ibge}`} className="font-medium hover:underline">
                {o.municipio_nome} - {o.uf}
              </Link>
            ) : (
              <p className="font-medium">{o.uf ?? "—"}</p>
            )}
            {o.endereco && <p>{o.endereco}</p>}
            {o.cep && <p className="font-mono text-xs text-muted-foreground">CEP {o.cep}</p>}
            {osm && (
              <a href={osm} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs text-primary hover:underline">
                <IconExternalLink className="size-3" /> {Number(o.latitude).toFixed(5)}, {Number(o.longitude).toFixed(5)}
              </a>
            )}
            <div className="border-t pt-2">
              <p className="text-xs text-muted-foreground">{t("obra.convenente")}</p>
              <Documento doc={o.proponente_cnpj} nome={o.proponente_nome} />
              {o.natureza_juridica && <p className="text-[11px] text-muted-foreground">{o.natureza_juridica}</p>}
            </div>
          </div>
        </Secao>
      </div>

      <Secao titulo={t("obra.emendas")}>
        <Tabela
          cabecalho={[t("emenda.codigo"), t("emenda.autor"), t("emenda.tipo"), t("obra.valorEmenda")]}
          linhas={o.emendas.map((e) => [
            e.emenda_codigo ? (
              <Link to={`/emendas/${e.emenda_codigo}`} className="font-mono text-xs hover:underline">
                {e.emenda_codigo}
              </Link>
            ) : (
              "—"
            ),
            e.politico_id ? (
              <Link to={`/politicos/${e.politico_id}`} className="font-medium hover:underline">
                {e.politico_nome ?? e.parlamentar_nome}
              </Link>
            ) : (
              <span className="text-muted-foreground">{e.parlamentar_nome}</span>
            ),
            <span className="flex flex-wrap gap-1">
              {e.tipo && <Badge variant="outline">{e.tipo}</Badge>}
              {e.impositiva && <Badge variant="secondary">{t("obra.impositiva")}</Badge>}
            </span>,
            <span className="tabular-nums">{formatBRL(e.valor_repasse)}</span>,
          ])}
        />
      </Secao>

      <div className="grid gap-4 xl:grid-cols-2">
        <Secao titulo={t("obra.contratos")}>
          <Tabela
            cabecalho={[t("obra.fornecedor"), t("obra.contrato"), t("common.valor")]}
            linhas={o.contratos.map((k) => [
              <Documento doc={k.fornecedor_documento} nome={k.fornecedor_nome} />,
              <div className="max-w-64">
                <p className="line-clamp-2 text-xs" title={k.objeto ?? ""}>
                  {k.objeto ?? "—"}
                </p>
                <p className="text-[11px] text-muted-foreground tabular-nums">
                  {[k.modalidade_licitacao, k.numero, formatDate(k.data_assinatura)].filter(Boolean).join(" · ")}
                </p>
              </div>,
              <span className="tabular-nums">{formatBRL(k.valor)}</span>,
            ])}
          />
        </Secao>
        <Secao titulo={t("obra.pagamentos")}>
          <Tabela
            cabecalho={[t("obra.fornecedor"), t("obra.periodo"), t("common.valor")]}
            linhas={o.fornecedores.map((f) => [
              f.documento ? <Documento doc={f.documento} nome={f.nome} /> : <span className="text-muted-foreground">{t("obra.pessoasFisicas")}</span>,
              <span className="text-xs tabular-nums">
                {formatDate(f.primeiro_pagamento)} – {formatDate(f.ultimo_pagamento)}
                <span className="block text-[11px] text-muted-foreground">
                  {t("obra.pagamentosQtd", { count: f.pagamentos })}
                </span>
              </span>,
              <span className="tabular-nums">{formatBRL(f.valor)}</span>,
            ])}
          />
        </Secao>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Secao titulo={t("obra.metas")}>
          <Tabela
            cabecalho={["#", t("obra.meta"), t("obra.periodo"), t("common.valor")]}
            linhas={o.metas.map((m) => [
              m.numero ?? "—",
              <div className="max-w-72">
                <p className="line-clamp-3 text-xs">{m.descricao ?? "—"}</p>
                {m.endereco && <p className="text-[11px] text-muted-foreground">{m.endereco}</p>}
                {m.quantidade !== null && (
                  <p className="text-[11px] text-muted-foreground">
                    {formatInt(toNumber(m.quantidade))} {m.unidade}
                  </p>
                )}
              </div>,
              <span className="text-xs tabular-nums">
                {formatDate(m.data_inicio)} – {formatDate(m.data_fim)}
              </span>,
              <span className="tabular-nums">{formatBRL(m.valor)}</span>,
            ])}
          />
        </Secao>
        <Secao titulo={t("obra.desembolsos")}>
          <Tabela
            cabecalho={[t("obra.data"), t("obra.ordemBancaria"), t("common.valor")]}
            linhas={o.desembolsos.map((d) => [
              <span className="tabular-nums">{formatDate(d.data)}</span>,
              <span className="font-mono text-xs">{d.documento ?? "—"}</span>,
              <span className="tabular-nums">{formatBRL(d.valor)}</span>,
            ])}
          />
        </Secao>
      </div>
      <p className="text-xs text-muted-foreground">
        {t("obra.fonte")}{" "}
        <a href={o.fonte_url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
          Transferegov / Siconv
        </a>
      </p>
    </>
  )
}
