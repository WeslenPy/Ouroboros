import { useCallback, useEffect, useRef, useState } from "react"

import type { Page } from "~/interface/api"

export interface Resource<T> {
  data: T | undefined
  error: Error | undefined
  loading: boolean
  reload: () => void
}

/** Busca um recurso e refaz quando `deps` mudam. Ignora respostas de buscas antigas. */
export function useResource<T>(
  fetcher: () => Promise<T>,
  deps: unknown[],
  { enabled = true, pollMs }: { enabled?: boolean; pollMs?: number } = {},
): Resource<T> {
  const [data, setData] = useState<T>()
  const [error, setError] = useState<Error>()
  const [loading, setLoading] = useState(enabled)
  const [tick, setTick] = useState(0)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return
    }
    let active = true
    setLoading(true)
    fetcherRef
      .current()
      .then((value) => {
        if (!active) return
        setData(value)
        setError(undefined)
      })
      .catch((err: Error) => active && setError(err))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled, tick])

  useEffect(() => {
    if (!pollMs || !enabled) return
    const id = window.setInterval(() => setTick((t) => t + 1), pollMs)
    return () => window.clearInterval(id)
  }, [pollMs, enabled])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data, error, loading, reload }
}

export interface CursorList<T> {
  items: T[]
  error: Error | undefined
  loading: boolean
  hasMore: boolean
  loadMore: () => void
  reload: () => void
}

/** Lista paginada por cursor (keyset): acumula páginas com "carregar mais". */
export function useCursorList<T>(
  fetcher: (cursor: string | null) => Promise<Page<T>>,
  deps: unknown[],
  { enabled = true }: { enabled?: boolean } = {},
): CursorList<T> {
  const [items, setItems] = useState<T[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [error, setError] = useState<Error>()
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  const generation = useRef(0)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const run = useCallback((from: string | null, append: boolean) => {
    const gen = generation.current
    setLoading(true)
    fetcherRef
      .current(from)
      .then((page) => {
        if (gen !== generation.current) return
        setItems((prev) => (append ? [...prev, ...page.items] : page.items))
        setCursor(page.next_cursor)
        setError(undefined)
      })
      .catch((err: Error) => gen === generation.current && setError(err))
      .finally(() => gen === generation.current && setLoading(false))
  }, [])

  useEffect(() => {
    generation.current++
    setItems([])
    setCursor(null)
    if (enabled) run(null, false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled, tick])

  return {
    items,
    error,
    loading,
    hasMore: cursor !== null,
    loadMore: () => cursor && !loading && run(cursor, true),
    reload: () => setTick((t) => t + 1),
  }
}
