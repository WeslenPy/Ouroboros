import { useState } from "react"
import { Link } from "react-router"
import { IconChevronDown, IconExternalLink, IconFileInvoice } from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { Card, CardContent } from "@/ui/card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/ui/collapsible"
import { EmptyState, ErrorState, LoadMore } from "~/components/custom/states"
import { useApi } from "~/context/api"
import { useCursorList, useResource } from "~/hooks/use-resource"
import type { AlertaOut, DetectorOut, Params, Severidade } from "~/interface/api"
import { formatBRL, formatDocumento, formatInt, monthLabel } from "~/lib/format"
import { cn } from "~/lib/utils"

const COR_SEVERIDADE: Record<Severidade, string> = {
  alta: "bg-red-600 text-white border-transparent",
  media: "bg-amber-500 text-white border-transparent",
  baixa: "border-sky-500/40 text-sky-700 dark:text-sky-400",
}

export function SeveridadeBadge({ severidade }: { severidade: Severidade }) {
  const { t } = useTranslation()
  return (
    <Badge variant="outline" className={COR_SEVERIDADE[severidade]}>
      {t(`alerta.severidades.${severidade}`)}
    </Badge>
  )
}

/** Cor do risco 0-100 (mesma escala da severidade). */
export function corRisco(risco: number): string {
  if (risco >= 70) return "bg-red-600"
  if (risco >= 45) return "bg-amber-500"
  return "bg-sky-500"
}

export function RiscoBar({ risco, className }: { risco: number; className?: string }) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="h-2 w-24 overflow-hidden rounded-full bg-muted">
        <div className={cn("h-full rounded-full", corRisco(risco))} style={{ width: `${risco}%` }} />
      </div>
      <span className="w-10 text-right text-sm font-semibold tabular-nums">{risco.toFixed(0)}</span>
    </div>
  )
}

const DINHEIRO = /(total|valor|pago|recebido|do_autor|mediana|gabinete$|fora_da_uf)/
const PROPORCAO = /(participacao|densidade)/

function formatMetrica(chave: string, valor: unknown): string {
  if (typeof valor === "number") {
    if (PROPORCAO.test(chave)) return `${(valor * 100).toFixed(0)}%`
    if (DINHEIRO.test(chave)) return formatBRL(valor)
    return Number.isInteger(valor) ? formatInt(valor) : valor.toLocaleString()
  }
  if (Array.isArray(valor)) return valor.join(", ")
  if (valor === null || valor === undefined) return "—"
  return String(valor)
}

function Distribuicao({ dados }: { dados: Record<string, { observado: number; esperado: number }> }) {
  const { t } = useTranslation()
  const max = Math.max(...Object.values(dados).flatMap((d) => [d.observado, d.esperado]))
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium text-muted-foreground">{t("alerta.digitos")}</p>
      {Object.entries(dados).map(([d, v]) => (
        <div key={d} className="flex items-center gap-2 text-xs">
          <span className="w-3 font-mono">{d}</span>
          <div className="relative h-3 flex-1 rounded bg-muted">
            <div
              className="absolute inset-y-0 left-0 rounded bg-primary/70"
              style={{ width: `${(v.observado / max) * 100}%` }}
            />
            <div
              className="absolute inset-y-0 w-0.5 bg-foreground"
              style={{ left: `${(v.esperado / max) * 100}%` }}
              title={t("alerta.esperado")}
            />
          </div>
          <span className="w-20 text-right tabular-nums text-muted-foreground">
            {(v.observado * 100).toFixed(1)}% / {(v.esperado * 100).toFixed(1)}%
          </span>
        </div>
      ))}
    </div>
  )
}

function Evidencias({ alerta }: { alerta: AlertaOut }) {
  const { t, i18n } = useTranslation()
  const { metricas, documentos, emendas, distribuicao, por_uf } = alerta.evidencias as AlertaOut["evidencias"] & {
    distribuicao?: Record<string, { observado: number; esperado: number }>
    por_uf?: Record<string, number>
  }
  return (
    <div className="grid gap-4 border-t pt-3 md:grid-cols-2">
      {metricas && (
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
          {Object.entries(metricas).map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-muted-foreground">{t(`alerta.metricas.${k}`, k.replaceAll("_", " "))}</dt>
              <dd className="break-words font-medium tabular-nums">{formatMetrica(k, v)}</dd>
            </div>
          ))}
        </dl>
      )}
      {distribuicao && <Distribuicao dados={distribuicao} />}
      {por_uf && (
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
          {Object.entries(por_uf).map(([uf, v]) => (
            <div key={uf} className="contents">
              <dt className="font-mono">{uf}</dt>
              <dd className="tabular-nums">{formatBRL(v)}</dd>
            </div>
          ))}
        </dl>
      )}
      {documentos && documentos.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground">
            {t("alerta.documentos", { count: documentos.length })}
          </p>
          <ul className="space-y-1 text-xs">
            {documentos.map((d, i) => (
              <li key={i} className="flex flex-wrap items-center gap-x-2">
                <IconFileInvoice className="size-3.5 text-muted-foreground" />
                {d.ano && d.mes && <span>{monthLabel(d.ano, d.mes)}</span>}
                {d.parlamentar && <span className="text-muted-foreground">{d.parlamentar}</span>}
                {d.fornecedor && <span className="truncate text-muted-foreground">{d.fornecedor}</span>}
                {d.valor !== undefined && <span className="tabular-nums">{formatBRL(d.valor)}</span>}
                {d.url ? (
                  <a
                    href={d.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-0.5 text-primary hover:underline"
                  >
                    {t("alerta.verNota")} <IconExternalLink className="size-3" />
                  </a>
                ) : (
                  d.despesa_id && <span className="font-mono text-muted-foreground">#{d.despesa_id}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {emendas && emendas.length > 0 && (
        <div className="space-y-1 text-xs">
          <p className="font-medium text-muted-foreground">{t("alerta.emendas")}</p>
          <p className="font-mono">{emendas.join(", ")}</p>
        </div>
      )}
      <p className="text-[11px] text-muted-foreground md:col-span-2">
        {t("alerta.geradoEm", { data: new Date(alerta.gerado_em).toLocaleString(i18n.language) })}
      </p>
    </div>
  )
}

export function AlertaCard({
  alerta,
  detector,
  mostrarPolitico = true,
}: {
  alerta: AlertaOut
  detector?: DetectorOut
  mostrarPolitico?: boolean
}) {
  const { t } = useTranslation()
  const [aberto, setAberto] = useState(false)
  const periodo =
    alerta.ano_inicio && alerta.ano_fim && alerta.ano_fim !== alerta.ano_inicio
      ? `${alerta.ano_inicio}–${alerta.ano_fim}`
      : alerta.ano_inicio
  return (
    <Card className="gap-2 py-3">
      <Collapsible open={aberto} onOpenChange={setAberto}>
        <CardContent className="space-y-2 px-4">
          <div className="flex flex-wrap items-center gap-2">
            <SeveridadeBadge severidade={alerta.severidade} />
            <span className="text-xs font-semibold tabular-nums">{alerta.score.toFixed(0)}</span>
            <Badge variant="secondary" className="font-normal">
              {detector?.titulo ?? alerta.detector}
            </Badge>
            {periodo && <span className="text-xs text-muted-foreground">{periodo}</span>}
            {alerta.valor && (
              <span className="ml-auto text-sm font-semibold tabular-nums">{formatBRL(alerta.valor)}</span>
            )}
          </div>
          <p className="font-medium leading-snug">{alerta.titulo}</p>
          <p className="text-sm text-muted-foreground">{alerta.descricao}</p>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
            {mostrarPolitico && alerta.politico_id && (
              <Link to={`/politicos/${alerta.politico_id}`} className="text-primary hover:underline">
                {alerta.politico_nome ?? `#${alerta.politico_id}`}
              </Link>
            )}
            {alerta.entidade_documento && (
              <Link
                to={`/fornecedores/${alerta.entidade_documento}`}
                className="text-primary hover:underline"
              >
                {alerta.entidade_nome} · {formatDocumento(alerta.entidade_documento)}
              </Link>
            )}
            <CollapsibleTrigger asChild>
              <Button variant="ghost" size="sm" className="ml-auto h-7 text-xs">
                {t("alerta.evidencias")}
                <IconChevronDown className={cn("transition-transform", aberto && "rotate-180")} />
              </Button>
            </CollapsibleTrigger>
          </div>
          <CollapsibleContent>
            <Evidencias alerta={alerta} />
          </CollapsibleContent>
        </CardContent>
      </Collapsible>
    </Card>
  )
}

/** Lista de alertas paginada (do mais forte ao mais fraco) para os filtros dados. */
export function AlertasList({
  params,
  detectores,
  mostrarPolitico = true,
}: {
  params: Params
  detectores?: Record<string, DetectorOut>
  mostrarPolitico?: boolean
}) {
  const { t } = useTranslation()
  const api = useApi()
  const list = useCursorList((cursor) => api.alertas({ ...params, cursor, limit: 30 }), [
    JSON.stringify(params),
  ])
  const catalogo = useResource(() => api.alertasDetectores(), [], { enabled: !detectores })
  const porCodigo =
    detectores ??
    Object.fromEntries((catalogo.data?.detectores ?? []).map((d) => [d.codigo, d]))
  if (list.error) return <ErrorState error={list.error} onRetry={list.reload} />
  if (!list.loading && list.items.length === 0)
    return <EmptyState title={t("alerta.vazio")} description={t("alerta.vazioDesc")} />
  return (
    <div className="flex flex-col gap-3">
      {list.items.map((a) => (
        <AlertaCard
          key={a.id}
          alerta={a}
          detector={porCodigo[a.detector]}
          mostrarPolitico={mostrarPolitico}
        />
      ))}
      <LoadMore
        hasMore={list.hasMore}
        loading={list.loading}
        onClick={list.loadMore}
        count={list.items.length}
      />
    </div>
  )
}
