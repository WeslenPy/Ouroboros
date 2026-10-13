import { isRouteErrorResponse, Links, Meta, Outlet, Scripts, ScrollRestoration } from "react-router"
import { useTranslation } from "react-i18next"

import "~/i18n"
import "./app.css"
import type { Route } from "./+types/root"
import { ThemeProvider } from "./components/provider/theme"
import { ErrorPage } from "./components/custom/error-page"
import { TooltipProvider } from "./components/ui/tooltip"
import { Toaster } from "./components/ui/sonner"
import { ApiProvider } from "./context/api"

export const links: Route.LinksFunction = () => [
  { rel: "preconnect", href: "https://fonts.googleapis.com" },
  { rel: "preconnect", href: "https://fonts.gstatic.com", crossOrigin: "anonymous" },
  {
    rel: "stylesheet",
    href: "https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,100..900;1,14..32,100..900&display=swap",
  },
]

export function meta() {
  return [{ title: "Ouroboros" }]
}

// Aplica o tema antes da hidratação (evita flash claro no modo escuro).
const themeScript = `(function(){try{var t=localStorage.getItem('theme-preference');if(t==='dark'||(!t&&matchMedia('(prefers-color-scheme: dark)').matches))document.documentElement.classList.add('dark')}catch(e){}})()`

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-br" suppressHydrationWarning>
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        <Meta />
        <Links />
      </head>
      <body>
        {children}
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  )
}

export function HydrateFallback() {
  return (
    <div className="flex h-svh items-center justify-center">
      <div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
    </div>
  )
}

export default function App() {
  return (
    <ApiProvider>
      <ThemeProvider>
        <TooltipProvider delayDuration={200}>
          <Outlet />
          <Toaster position="top-center" />
        </TooltipProvider>
      </ThemeProvider>
    </ApiProvider>
  )
}

export function ErrorBoundary({ error }: Route.ErrorBoundaryProps) {
  const { t } = useTranslation()
  let title = t("errors.title")
  let details = t("errors.details")
  let status: number | undefined
  let stack: string | undefined

  if (isRouteErrorResponse(error)) {
    status = error.status
    title = error.status === 404 ? t("errors.404") : t("errors.error")
    details = error.status === 404 ? t("errors.notFound") : error.statusText || details
  } else if (import.meta.env.DEV && error instanceof Error) {
    details = error.message
    stack = error.stack
  }

  return <ErrorPage title={title} message={details} statusCode={status} stack={stack} />
}
