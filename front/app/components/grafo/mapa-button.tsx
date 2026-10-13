import { Link } from "react-router"
import { IconAffiliate } from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import { Button } from "@/ui/button"

/** Atalho para abrir a entidade no mapa de conexões (`no` = "politico:ID", "doc:CNPJ"...). */
export function MapaButton({ no, ano }: { no: string; ano?: string | number }) {
  const { t } = useTranslation()
  const qs = new URLSearchParams({ no })
  if (ano) qs.set("ano", String(ano))
  return (
    <Button asChild size="sm">
      <Link to={`/grafo?${qs}`}>
        <IconAffiliate /> {t("grafo.verRede")}
      </Link>
    </Button>
  )
}
