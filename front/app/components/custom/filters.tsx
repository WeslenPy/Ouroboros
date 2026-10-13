import { useEffect, useState, type ReactNode } from "react"
import { IconDownload, IconFilterOff, IconLoader2, IconSearch } from "@tabler/icons-react"
import { useTranslation } from "react-i18next"
import { toast } from "sonner"

import { Button } from "@/ui/button"
import { Input } from "@/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/ui/select"
import { cn } from "~/lib/utils"

const ALL = "__all__"

export function FilterBar({
  children,
  onClear,
  canClear,
  className,
}: {
  children: ReactNode
  onClear?: () => void
  canClear?: boolean
  className?: string
}) {
  const { t } = useTranslation()
  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      {children}
      {onClear && canClear && (
        <Button variant="ghost" size="sm" onClick={onClear} className="text-muted-foreground">
          <IconFilterOff /> {t("filters.clear")}
        </Button>
      )}
    </div>
  )
}

export interface Option {
  value: string
  label: string
}

/** Select com opção "todos" que limpa o filtro. */
export function SelectFilter({
  value,
  onChange,
  options,
  placeholder,
  className,
}: {
  value: string
  onChange: (value: string) => void
  options: Option[]
  placeholder: string
  className?: string
}) {
  const { t } = useTranslation()
  return (
    <Select value={value || ALL} onValueChange={(v) => onChange(v === ALL ? "" : v)}>
      <SelectTrigger size="sm" className={cn("min-w-32", className)}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent className="max-h-80">
        <SelectItem value={ALL}>
          <span className="text-muted-foreground">
            {placeholder}: {t("filters.all")}
          </span>
        </SelectItem>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

/** Campo de texto que só aplica após pausa na digitação. */
export function SearchFilter({
  value,
  onChange,
  placeholder,
  minLength = 0,
  className,
  type = "search",
}: {
  value: string
  onChange: (value: string) => void
  placeholder: string
  minLength?: number
  className?: string
  type?: "search" | "date"
}) {
  const [draft, setDraft] = useState(value)
  useEffect(() => setDraft(value), [value])
  useEffect(() => {
    if (draft === value) return
    const trimmed = draft.trim()
    if (trimmed && trimmed.length < minLength) return
    const id = window.setTimeout(() => onChange(trimmed), 400)
    return () => window.clearTimeout(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft])

  return (
    <div className={cn("relative w-full sm:w-60", className)}>
      {type === "search" && (
        <IconSearch className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
      )}
      <Input
        type={type}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className={cn("h-8 w-full", type === "search" && "pl-8")}
      />
    </div>
  )
}

export function yearOptions(from = 2008, to = new Date().getFullYear()): Option[] {
  const out: Option[] = []
  for (let y = to; y >= from; y--) out.push({ value: String(y), label: String(y) })
  return out
}

export function monthOptions(locale: string): Option[] {
  return Array.from({ length: 12 }, (_, i) => ({
    value: String(i + 1),
    label: new Date(2000, i, 1).toLocaleDateString(locale, { month: "long" }),
  }))
}

export function boolOptions(t: (k: string) => string): Option[] {
  return [
    { value: "true", label: t("common.yes") },
    { value: "false", label: t("common.no") },
  ]
}

/** Botão de exportação CSV (percorre páginas pela API). */
export function ExportButton({ onExport }: { onExport: () => Promise<number> }) {
  const { t } = useTranslation()
  const [busy, setBusy] = useState(false)
  return (
    <Button
      size="sm"
      variant="outline"
      disabled={busy}
      onClick={async () => {
        setBusy(true)
        try {
          const pages = await onExport()
          toast.success(t("export.done", { pages }))
        } catch (err) {
          toast.error(t("export.failed"), { description: (err as Error).message })
        } finally {
          setBusy(false)
        }
      }}
    >
      {busy ? <IconLoader2 className="animate-spin" /> : <IconDownload />}
      CSV
    </Button>
  )
}
