import { useMemo } from "react"
import { Bar, BarChart, CartesianGrid, Cell, XAxis, YAxis } from "recharts"

import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/ui/chart"
import {
  CARTESIAN_CHART_CLASSNAME,
  cartesianChartDimension,
  chartColor,
  formatCompactTick,
  formatCompactTooltipValue,
} from "./chart-utils"

/** Rótulo do eixo Y sem quebra de linha (o padrão do recharts quebra em espaços). */
function SingleLineTick({ x, y, payload }: { x?: number | string; y?: number | string; payload?: { value: unknown } }) {
  const v = String(payload?.value ?? "")
  const label = v.length > 26 ? `${v.slice(0, 25)}…` : v
  return (
    <text x={x} y={y} dy={4} textAnchor="end" fontSize={11} className="fill-muted-foreground">
      <title>{v}</title>
      {label}
    </text>
  )
}

export interface BarItem {
  name: string
  value: number
  /** valor secundário empilhado (ex.: eleitos dentro do total) */
  secondary?: number
}

/**
 * Barras simples. `layout="horizontal"` desenha barras deitadas (bom para rótulos longos:
 * categorias, fornecedores).
 */
export function SimpleBarChart({
  data,
  height = 280,
  layout = "vertical",
  label = "Valor",
  secondaryLabel,
  valueFormatter = formatCompactTooltipValue,
  colorful = false,
  onSelect,
}: {
  data: BarItem[]
  height?: number
  layout?: "vertical" | "horizontal"
  label?: string
  secondaryLabel?: string
  valueFormatter?: (value: number) => string
  colorful?: boolean
  onSelect?: (item: BarItem) => void
}) {
  const config = useMemo<ChartConfig>(
    () => ({
      value: { label, color: chartColor(0) },
      extra: { label: secondaryLabel ?? "", color: chartColor(1) },
    }),
    [label, secondaryLabel],
  )
  const horizontal = layout === "horizontal"
  const stacked = data.some((d) => d.secondary !== undefined)
  const chartData = useMemo(
    () =>
      stacked
        ? data.map((d) => ({ ...d, extra: d.secondary ?? 0, value: d.value - (d.secondary ?? 0) }))
        : data,
    [data, stacked],
  )

  if (!data.length) return null

  return (
    <ChartContainer
      config={config}
      className={CARTESIAN_CHART_CLASSNAME}
      style={{ height }}
      initialDimension={cartesianChartDimension(height)}
    >
      <BarChart
        accessibilityLayer
        data={chartData}
        layout={horizontal ? "vertical" : "horizontal"}
        margin={horizontal ? { left: 8, right: 16 } : undefined}
      >
        <CartesianGrid vertical={horizontal} horizontal={!horizontal} />
        {horizontal ? (
          <>
            <XAxis type="number" tickLine={false} axisLine={false} tickFormatter={formatCompactTick} />
            <YAxis
              type="category"
              dataKey="name"
              tickLine={false}
              axisLine={false}
              width={170}
              interval={0}
              tick={SingleLineTick}
            />
          </>
        ) : (
          <>
            <XAxis dataKey="name" tickLine={false} axisLine={false} tickMargin={8} minTickGap={8} />
            <YAxis
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              width={52}
              tickFormatter={formatCompactTick}
            />
          </>
        )}
        <ChartTooltip
          cursor={{ fill: "var(--muted)", opacity: 0.5 }}
          content={<ChartTooltipContent valueFormatter={valueFormatter} />}
        />
        {stacked && (
          <Bar
            dataKey="extra"
            stackId="a"
            fill="var(--color-extra)"
            radius={0}
            className={onSelect ? "cursor-pointer" : undefined}
            onClick={(d) => onSelect?.(d.payload as BarItem)}
          />
        )}
        <Bar
          dataKey="value"
          stackId={stacked ? "a" : undefined}
          fill="var(--color-value)"
          radius={horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]}
          className={onSelect ? "cursor-pointer" : undefined}
          onClick={(d) => onSelect?.(d.payload as BarItem)}
        >
          {colorful && chartData.map((d, i) => <Cell key={d.name} fill={chartColor(i)} />)}
        </Bar>
      </BarChart>
    </ChartContainer>
  )
}
