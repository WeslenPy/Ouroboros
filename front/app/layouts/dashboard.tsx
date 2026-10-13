import type { CSSProperties } from "react"
import { Outlet } from "react-router"

import { SidebarInset, SidebarProvider } from "@/ui/sidebar"
import { NavHeader } from "~/components/custom/nav/nav-header"
import { AppSidebar } from "~/components/custom/nav/sidebar"
import { PageProvider } from "~/context/page"

export default function DashboardLayout() {
  return (
    <PageProvider>
      <SidebarProvider
        style={
          {
            "--sidebar-width": "calc(var(--spacing) * 64)",
            "--header-height": "calc(var(--spacing) * 14)",
          } as CSSProperties
        }
      >
        <AppSidebar variant="inset" />
        <SidebarInset className="min-w-0">
          <NavHeader />
          <div className="@container/main flex flex-1 flex-col">
            <div className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 p-4 md:p-6">
              <Outlet />
            </div>
          </div>
        </SidebarInset>
      </SidebarProvider>
    </PageProvider>
  )
}
