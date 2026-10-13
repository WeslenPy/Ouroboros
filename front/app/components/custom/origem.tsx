import { IconExternalLink, IconFingerprint } from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import { Card, CardContent, CardHeader, CardTitle } from "@/ui/card"
import type { Origem } from "~/interface/api"
import { formatDateTime } from "~/lib/format"

/** Linhagem do registro: de onde veio, hash do bruto e quando foi ingerido. */
export function OrigemCard({ origem }: { origem: Origem }) {
  const { t } = useTranslation()
  return (
    <Card className="gap-3 shadow-xs">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <IconFingerprint className="size-4" /> {t("origem.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div>
          <p className="text-xs text-muted-foreground">{t("origem.fonte")}</p>
          <p className="font-medium">{origem.fonte}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">{t("origem.url")}</p>
          <a
            href={origem.fonte_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex max-w-full items-center gap-1 break-all text-primary hover:underline"
          >
            <span className="truncate">{origem.fonte_url}</span>
            <IconExternalLink className="size-3.5 shrink-0" />
          </a>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">{t("origem.hash")}</p>
          <p className="truncate font-mono text-xs" title={origem.raw_hash}>
            {origem.raw_hash}
          </p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">{t("origem.ingerido")}</p>
          <p>{formatDateTime(origem.ingerido_em)}</p>
        </div>
      </CardContent>
    </Card>
  )
}
