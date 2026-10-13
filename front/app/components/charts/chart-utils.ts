import type { ChartConfig } from "@/components/ui/chart"

export const CHART_COLOR_VARS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
] as const

export function chartColor(index: number): string {
  return CHART_COLOR_VARS[index % CHART_COLOR_VARS.length]
}

export function toChartConfigKey(name: string, index: number): string {
  const key = name
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "")

  return key || `item_${index}`
}

export function buildConfigFromLabels(labels: string[]): ChartConfig {
  return labels.reduce<ChartConfig>((acc, label, index) => {
    acc[toChartConfigKey(label, index)] = {
      label,
      color: chartColor(index),
    }
    return acc
  }, {})
}

export function formatChartDate(value: string): string {
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })
}

export function isTimeseriesEmpty(points: unknown[], keys: unknown[]): boolean {
  return !points.length || !keys.length
}

export const DEFAULT_CARTESIAN_CHART_HEIGHT = 280

export const CARTESIAN_CHART_CLASSNAME =
  "w-full [&_.recharts-responsive-container]:!h-full"

export function cartesianChartDimension(height = DEFAULT_CARTESIAN_CHART_HEIGHT) {
  return { width: 600, height }
}

export function formatCompactNumber(value: number): string {
  const abs = Math.abs(value)
  const sign = value < 0 ? "-" : ""

  if (abs >= 1_000_000_000) {
    const scaled = abs / 1_000_000_000
    return `${sign}${formatCompactScaled(scaled)}B`
  }

  if (abs >= 1_000_000) {
    const scaled = abs / 1_000_000
    return `${sign}${formatCompactScaled(scaled)}M`
  }

  if (abs >= 1_000) {
    const scaled = abs / 1_000
    return `${sign}${formatCompactScaled(scaled)}K`
  }

  return `${sign}${Math.round(abs)}`
}

function formatCompactScaled(value: number): string {
  const formatted = value >= 100 ? value.toFixed(0) : value.toFixed(1)
  return formatted.replace(/\.0$/, "")
}

export function formatCompactTick(value: string | number): string {
  const num = Number(value)
  if (!Number.isFinite(num)) return String(value)
  return formatCompactNumber(num)
}

export function formatCompactTooltipValue(value: number): string {
  return formatCompactNumber(value)
}

