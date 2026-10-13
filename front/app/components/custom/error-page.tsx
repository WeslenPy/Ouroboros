import { Link } from "react-router"
import { IconAlertTriangle, IconHome } from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import { Button } from "@/ui/button"

export function ErrorPage({
  title,
  message,
  statusCode,
  stack,
}: {
  title: string
  message: string
  statusCode?: number
  stack?: string
}) {
  const { t } = useTranslation()
  return (
    <main className="flex min-h-[60svh] flex-col items-center justify-center gap-4 p-6 text-center">
      <div className="flex size-14 items-center justify-center rounded-full bg-destructive/10 text-destructive">
        <IconAlertTriangle className="size-7" />
      </div>
      {statusCode && <p className="font-mono text-5xl font-bold text-muted-foreground/40">{statusCode}</p>}
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="max-w-md text-sm text-muted-foreground">{message}</p>
      <Button asChild variant="outline">
        <Link to="/">
          <IconHome /> {t("navigation.home")}
        </Link>
      </Button>
      {stack && (
        <pre className="mt-4 max-h-64 w-full max-w-3xl overflow-auto rounded-lg border bg-muted/40 p-4 text-left text-xs">
          {stack}
        </pre>
      )}
    </main>
  )
}
