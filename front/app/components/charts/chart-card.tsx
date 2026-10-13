import type { ReactNode } from "react"

import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/card"
import { cn } from "~/lib/utils"
import { EmptyState } from "../custom/states"

export function ChartCard({
  title,
  description,
  action,
  loading,
  isEmpty,
  children,
  className,
  height = 280,
}: {
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
  loading?: boolean
  isEmpty?: boolean
  children: ReactNode
  className?: string
  height?: number
}) {
  return (
    <Card className={cn("gap-4 overflow-hidden shadow-xs", className)}>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
        {action && <CardAction>{action}</CardAction>}
      </CardHeader>
      <CardContent className="px-2 sm:px-6">
        {loading ? (
          <div className="animate-pulse rounded-lg bg-muted/40" style={{ height }} />
        ) : isEmpty ? (
          <EmptyState height={height} className="border-none" />
        ) : (
          children
        )}
      </CardContent>
    </Card>
  )
}
