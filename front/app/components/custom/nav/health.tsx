import { useTranslation } from "react-i18next"

import { SidebarMenu, SidebarMenuButton, SidebarMenuItem } from "@/ui/sidebar"
import { useApi } from "~/context/api"
import { useResource } from "~/hooks/use-resource"
import { cn } from "~/lib/utils"

/** Estado da API e do banco (GET /health), atualizado a cada 30s. */
export function HealthBadge() {
  const { t } = useTranslation()
  const api = useApi()
  const { data, error } = useResource(() => api.health(), [], { pollMs: 30_000 })
  const ok = !error && data?.db === "ok"
  const label = error ? t("health.offline") : ok ? t("health.online") : t("health.checking")

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton tooltip={label} className="text-xs text-muted-foreground">
          <span className="relative flex size-2.5 shrink-0 items-center justify-center">
            {ok && (
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-500 opacity-60" />
            )}
            <span
              className={cn(
                "relative inline-flex size-2.5 rounded-full",
                error ? "bg-destructive" : ok ? "bg-emerald-500" : "bg-muted-foreground",
              )}
            />
          </span>
          <span>{label}</span>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
