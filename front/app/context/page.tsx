import { createContext, useContext, useEffect, useState, type ReactNode } from "react"
import { useLocation } from "react-router"

import { APP_NAME } from "~/config/page-routes"

interface PageContextValue {
  /** título da entidade aberta (ex.: nome do político), mostrado no breadcrumb */
  detail: string | undefined
  setDetail: (title: string | undefined) => void
}

const PageContext = createContext<PageContextValue | undefined>(undefined)

export function PageProvider({ children }: { children: ReactNode }) {
  const [detail, setDetail] = useState<string>()
  const { pathname } = useLocation()

  useEffect(() => setDetail(undefined), [pathname])

  return <PageContext.Provider value={{ detail, setDetail }}>{children}</PageContext.Provider>
}

export function usePage() {
  const ctx = useContext(PageContext)
  if (!ctx) throw new Error("usePage must be inside PageProvider")
  return ctx
}

/** Define o título da aba e o último nível do breadcrumb. */
export function usePageTitle(title: string | undefined, detail?: string) {
  const { setDetail } = usePage()
  useEffect(() => {
    if (title) document.title = `${title} · ${APP_NAME}`
  }, [title])
  useEffect(() => {
    setDetail(detail)
  }, [detail, setDetail])
}
