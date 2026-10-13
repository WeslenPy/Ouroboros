import { IconInfinity } from "@tabler/icons-react"

import { APP_NAME } from "~/config/page-routes"

export function Logo() {
  return (
    <>
      <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <IconInfinity className="size-5" />
      </div>
      <div className="grid flex-1 text-left leading-tight">
        <span className="truncate font-semibold">{APP_NAME}</span>
        <span className="truncate text-xs text-muted-foreground">dados públicos</span>
      </div>
    </>
  )
}
