import i18n from "~/i18n"

function locale(): string {
  return i18n.language?.startsWith("en") ? "en-US" : "pt-BR"
}

export function toNumber(value: string | number | null | undefined): number {
  if (value === null || value === undefined || value === "") return 0
  const n = typeof value === "number" ? value : Number(value)
  return Number.isFinite(n) ? n : 0
}

export function formatBRL(value: string | number | null | undefined, compact = false): string {
  if (value === null || value === undefined) return "—"
  return new Intl.NumberFormat(locale(), {
    style: "currency",
    currency: "BRL",
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: compact ? 1 : 2,
  }).format(toNumber(value))
}

export function formatInt(value: number | null | undefined, compact = false): string {
  if (value === null || value === undefined) return "—"
  return new Intl.NumberFormat(locale(), {
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: compact ? 1 : 0,
  }).format(value)
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—"
  const d = value.length === 10 ? new Date(`${value}T00:00:00`) : new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleDateString(locale())
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—"
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString(locale(), { dateStyle: "short", timeStyle: "short" })
}

export function formatRelative(value: string | null | undefined): string {
  if (!value) return "—"
  const diff = (new Date(value).getTime() - Date.now()) / 1000
  const rtf = new Intl.RelativeTimeFormat(locale(), { numeric: "auto" })
  const steps: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 31536000],
    ["month", 2592000],
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
  ]
  for (const [unit, secs] of steps) {
    if (Math.abs(diff) >= secs) return rtf.format(Math.round(diff / secs), unit)
  }
  return rtf.format(Math.round(diff), "second")
}

export function formatDuration(start: string, end: string | null): string {
  const ms = (end ? new Date(end) : new Date()).getTime() - new Date(start).getTime()
  const s = Math.max(0, Math.round(ms / 1000))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ${s % 60}s`
  return `${Math.floor(m / 60)}h ${m % 60}m`
}

export function formatDocumento(doc: string | null | undefined): string {
  if (!doc) return "—"
  if (/^\d{14}$/.test(doc)) return doc.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5")
  return doc
}

export function monthLabel(ano: number, mes: number): string {
  return new Date(ano, mes - 1, 1).toLocaleDateString(locale(), { month: "short", year: "2-digit" })
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("")
}
