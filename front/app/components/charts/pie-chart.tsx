import { useMemo } from "react"
import { Cell, Pie, PieChart } from "recharts"

import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/ui/chart"
import { cn } from "~/lib/utils"
import { chartColor, formatCompactTooltipValue, toChartConfigKey } from "./chart-utils"

export interface PieItem {
  name: string
  value: number
}

/** Rosca com legenda (copiado do WADashboard, agrupa o excedente em "Outros"). */
export function DonutChart({
  data,
  className,
  maxSlices = 6,
  othersLabel = "Outros",
  valueFormatter = formatCompactTooltipValue,
}: {
  data: PieItem[]
  className?: string
  maxSlices?: number
  othersLabel?: string
  valueFormatter?: (value: number) => string
}) {
  const { config, chartData } = useMemo(() => {
    const sorted = [...data].sort((a, b) => b.value - a.value)
    const head = sorted.slice(0, maxSlices)
    const rest = sorted.slice(maxSlices).reduce((acc, d) => acc + d.value, 0)
    const items = rest > 0 ? [...head, { name: othersLabel, value: rest }] : head
    const config: ChartConfig = {}
    const chartData = items.map((item, index) => {
      const key = toChartConfigKey(item.name, index)
      config[key] = { label: item.name, color: chartColor(index) }
      return { key, name: item.name, value: item.value, fill: `var(--color-${key})` }
    })
    return { config, chartData }
  }, [data, maxSlices, othersLabel])

  if (!data.length) return null

  return (
    <div className={cn("flex w-full flex-col gap-4", className)}>
      <ChartContainer
        config={config}
        className="mx-auto aspect-square max-h-[220px] w-full max-w-[260px] [&_.recharts-responsive-container]:!h-full"
        initialDimension={{ width: 260, height: 220 }}
      >
        <PieChart margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
          <ChartTooltip
            content={<ChartTooltipContent hideLabel nameKey="name" valueFormatter={valueFormatter} />}
          />
          <Pie
            data={chartData}
            dataKey="value"
            nameKey="name"
            innerRadius="55%"
            outerRadius="80%"
            paddingAngle={3}
            cornerRadius={4}
            strokeWidth={2}
            stroke="var(--background)"
          >
            {chartData.map((entry) => (
              <Cell key={entry.key} fill={entry.fill} />
            ))}
          </Pie>
        </PieChart>
      </ChartContainer>
      <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 px-1">
        {chartData.map((entry) => (
          <div key={entry.key} className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className="size-2 shrink-0 rounded-[2px]" style={{ backgroundColor: entry.fill }} />
            <span className="text-foreground">{entry.name}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
