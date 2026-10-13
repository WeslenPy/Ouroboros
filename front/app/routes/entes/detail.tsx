import { Link, useParams } from "react-router"
import { IconMapPin } from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import { Button } from "@/ui/button"
import { MapaButton } from "~/components/grafo/mapa-button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/card"
import { useEsferaLabel } from "~/components/custom/labels"
import { OrigemCard } from "~/components/custom/origem"
import { BlockSkeleton, ErrorState, PageHeader } from "~/components/custom/states"
import { ObrasTable } from "~/components/custom/obras"
import { useApi } from "~/context/api"
import { usePageTitle } from "~/context/page"
import { useResource } from "~/hooks/use-resource"

export default function EnteDetail() {
  const { codigo = "" } = useParams()
  const { t } = useTranslation()
  const api = useApi()
  const esferaLabel = useEsferaLabel()
  const ente = useResource(() => api.ente(codigo), [codigo])
  const e = ente.data
  usePageTitle(e?.nome, e?.nome)

  if (ente.error) return <ErrorState error={ente.error} onRetry={ente.reload} />
  if (!e) return <BlockSkeleton height={300} />

  const campos: [string, string | number | null][] = [
    [t("ente.codigo"), e.codigo_ibge],
    [t("filters.esfera"), esferaLabel(e.esfera)],
    ["UF", e.uf],
    [t("ente.ufCodigo"), e.uf_codigo],
    [t("ente.regiao"), e.regiao],
  ]

  return (
    <>
      <PageHeader
        title={e.nome}
        description={esferaLabel(e.esfera)}
        actions={
          e.uf && (
            <>
              {e.esfera === "municipal" && <MapaButton no={`municipio:${e.codigo_ibge}`} />}
              <Button asChild variant="outline" size="sm">
                <Link to={`/politicos?uf=${e.uf}&em_exercicio=true`}>{t("ente.verPoliticos")}</Link>
              </Button>
              <Button asChild variant="outline" size="sm">
                <Link to={`/despesas?uf=${e.uf}`}>{t("ente.verDespesas")}</Link>
              </Button>
            </>
          )
        }
      >
        <div className="flex size-12 items-center justify-center rounded-lg bg-muted">
          <IconMapPin className="size-6 text-muted-foreground" />
        </div>
      </PageHeader>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="gap-3 shadow-xs">
          <CardHeader>
            <CardTitle className="text-base">{t("ente.dados")}</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-4 text-sm">
              {campos.map(([label, value]) => (
                <div key={label}>
                  <dt className="text-xs text-muted-foreground">{label}</dt>
                  <dd className="font-medium">{value ?? "—"}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>
        <OrigemCard origem={e.origem} />
      </div>
      {e.esfera === "municipal" && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">{t("ente.obras")}</h2>
            <Link to={`/obras?municipio=${e.codigo_ibge}`} className="text-xs text-primary hover:underline">
              {t("common.verTudo")}
            </Link>
          </div>
          <ObrasTable params={{ municipio: e.codigo_ibge }} deps={[e.codigo_ibge]} />
        </div>
      )}
    </>
  )
}
