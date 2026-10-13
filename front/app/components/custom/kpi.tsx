import type { ReactNode } from "react"
import { Link } from "react-router"
import type { Icon } from "@tabler/icons-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/ui/card"
import { Skeleton } from "@/ui/skeleton"
import { cn } from "~/lib/utils"

export interface KpiItem {
  title: string
  value: ReactNode
  hint?: ReactNode
  icon?: Icon
  to?: string
}

export function KpiCard({ item, loading }: { item: KpiItem; loading?: boolean }) {
  const Icon = item.icon
  const body = (
    <Card
      className={cn(
        "h-full gap-2 bg-gradient-to-t from-primary/5 to-card shadow-xs transition-colors",
        item.to && "hover:border-primary/40",
      )}
    >
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-sm font-medium text-muted-foreground">{item.title}</CardTitle>
        {Icon && <Icon className="size-4 text-muted-foreground" />}
      </CardHeader>
      <CardContent className="space-y-1">
        {loading ? (
          <Skeleton className="h-8 w-28" />
        ) : (
          <p className="text-2xl font-semibold tabular-nums tracking-tight">{item.value}</p>
        )}
        {item.hint && <p className="text-xs text-muted-foreground">{item.hint}</p>}
      </CardContent>
    </Card>
  )
  return item.to ? (
    <Link to={item.to} className="block">
      {body}
    </Link>
  ) : (
    body
  )
}

export function KpiGrid({
  items,
  loading,
  className,
}: {
  items: KpiItem[]
  loading?: boolean
  className?: string
}) {
  return (
    <div className={cn("grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4", className)}>
      {items.map((item) => (
        <KpiCard key={item.title} item={item} loading={loading} />
      ))}
    </div>
  )
}
