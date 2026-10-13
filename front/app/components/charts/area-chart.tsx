import { useMemo } from "react"
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts"

import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/ui/chart"
import {
  CARTESIAN_CHART_CLASSNAME,
  cartesianChartDimension,
  chartColor,
  formatCompactTick,
  formatCompactTooltipValue,
} from "./chart-utils"

export interface SeriesPoint {
  label: string
  value: number
}

/** Série temporal com área em gradiente (gasto por mês/ano). */
export function TimeAreaChart({
  data,
  height = 280,
  label = "Valor",
  valueFormatter = formatCompactTooltipValue,
}: {
  data: SeriesPoint[]
  height?: number
  label?: string
  valueFormatter?: (value: number) => string
}) {
  const config = useMemo<ChartConfig>(() => ({ value: { label, color: chartColor(1) } }), [label])
  if (!data.length) return null

  return (
    <ChartContainer
      config={config}
      className={CARTESIAN_CHART_CLASSNAME}
      style={{ height }}
      initialDimension={cartesianChartDimension(height)}
    >
      <AreaChart accessibilityLayer data={data} margin={{ left: 4, right: 12 }}>
        <defs>
          <linearGradient id="fillValue" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="var(--color-value)" stopOpacity={0.6} />
            <stop offset="95%" stopColor="var(--color-value)" stopOpacity={0.05} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} minTickGap={24} />
        <YAxis
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          width={52}
          tickFormatter={formatCompactTick}
        />
        <ChartTooltip
          cursor={false}
          content={<ChartTooltipContent indicator="dot" valueFormatter={valueFormatter} />}
        />
        <Area
          dataKey="value"
          type="monotone"
          fill="url(#fillValue)"
          stroke="var(--color-value)"
          strokeWidth={2}
        />
      </AreaChart>
    </ChartContainer>
  )
}
