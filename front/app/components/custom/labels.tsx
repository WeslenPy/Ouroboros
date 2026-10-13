import { useCallback } from "react"
import { useTranslation } from "react-i18next"

import { Badge } from "@/ui/badge"
import type { StatusExecucao } from "~/interface/api"
import { cn } from "~/lib/utils"

export function useCargoLabel() {
  const { t } = useTranslation()
  return useCallback((cargo: string | null | undefined) => (cargo ? t(`cargo.${cargo}`, cargo) : "—"), [t])
}

export function useEsferaLabel() {
  const { t } = useTranslation()
  return useCallback((esfera: string | null | undefined) => (esfera ? t(`esfera.${esfera}`, esfera) : "—"), [t])
}

const STATUS_CLASS: Record<StatusExecucao, string> = {
  sucesso: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  falha: "border-destructive/30 bg-destructive/10 text-destructive",
  rodando: "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-400",
}

export function StatusBadge({ status }: { status: StatusExecucao }) {
  const { t } = useTranslation()
  return (
    <Badge variant="outline" className={cn("gap-1.5", STATUS_CLASS[status])}>
      <span
        className={cn(
          "size-1.5 rounded-full bg-current",
          status === "rodando" && "animate-pulse",
        )}
      />
      {t(`status.${status}`)}
    </Badge>
  )
}

export function VerbaBadge({ verba }: { verba: string }) {
  return (
    <Badge variant="secondary" className="font-mono text-[10px]">
      {verba}
    </Badge>
  )
}
