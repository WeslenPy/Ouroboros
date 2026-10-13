import type { ReactNode } from "react"
import { IconAlertCircle, IconDatabaseOff, IconLoader2, IconRefresh } from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import { Button } from "@/ui/button"
import { Skeleton } from "@/ui/skeleton"
import { cn } from "~/lib/utils"

export function EmptyState({
  title,
  description,
  className,
  height,
}: {
  title?: string
  description?: string
  className?: string
  height?: number
}) {
  const { t } = useTranslation()
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-8 text-center",
        className,
      )}
      style={height ? { height } : undefined}
    >
      <IconDatabaseOff className="size-8 text-muted-foreground/60" />
      <p className="text-sm font-medium">{title ?? t("common.noData")}</p>
      {description && <p className="max-w-sm text-xs text-muted-foreground">{description}</p>}
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-8 text-center">
      <IconAlertCircle className="size-8 text-destructive" />
      <div>
        <p className="text-sm font-medium">{t("errors.load")}</p>
        <p className="text-xs text-muted-foreground">{error.message}</p>
      </div>
      {onRetry && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          <IconRefresh /> {t("common.retry")}
        </Button>
      )}
    </div>
  )
}

export function LoadMore({
  hasMore,
  loading,
  onClick,
  count,
}: {
  hasMore: boolean
  loading: boolean
  onClick: () => void
  count: number
}) {
  const { t } = useTranslation()
  return (
    <div className="flex items-center justify-between gap-4 px-1 pt-3 text-xs text-muted-foreground">
      <span>{t("common.showing", { count })}</span>
      {hasMore && (
        <Button size="sm" variant="outline" onClick={onClick} disabled={loading}>
          {loading && <IconLoader2 className="animate-spin" />}
          {t("common.loadMore")}
        </Button>
      )}
    </div>
  )
}

export function PageHeader({
  title,
  description,
  actions,
  children,
}: {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  children?: ReactNode
}) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="flex min-w-0 items-center gap-4">
        {children}
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-semibold tracking-tight">{title}</h1>
          {description && <p className="text-sm text-muted-foreground">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function BlockSkeleton({ height = 240 }: { height?: number }) {
  return <Skeleton className="w-full rounded-lg" style={{ height }} />
}
