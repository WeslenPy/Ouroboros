import { useCallback, useMemo } from "react"
import { useSearchParams } from "react-router"

/** Filtros guardados na query string (links compartilháveis). Valores vazios saem da URL. */
export function useFilters<K extends string>(keys: readonly K[]) {
  const [searchParams, setSearchParams] = useSearchParams()

  const values = useMemo(() => {
    const out = {} as Record<K, string>
    for (const key of keys) out[key] = searchParams.get(key) ?? ""
    return out
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, keys.join()])

  const set = useCallback(
    (patch: Partial<Record<K, string | number | null | undefined>>) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          for (const [key, value] of Object.entries(patch)) {
            if (value === undefined || value === null || value === "") next.delete(key)
            else next.set(key, String(value))
          }
          return next
        },
        { replace: true },
      )
    },
    [setSearchParams],
  )

  const clear = useCallback(() => setSearchParams({}, { replace: true }), [setSearchParams])

  return { values, set, clear, key: searchParams.toString() }
}

/** Converte strings da URL para parâmetros de API (número quando aplicável). */
export function toParams<K extends string>(
  values: Record<K, string>,
  numeric: readonly K[] = [],
): Record<string, string | number | undefined> {
  const out: Record<string, string | number | undefined> = {}
  for (const [key, value] of Object.entries(values) as [K, string][]) {
    if (!value) continue
    out[key] = numeric.includes(key) ? Number(value) : value
  }
  return out
}
