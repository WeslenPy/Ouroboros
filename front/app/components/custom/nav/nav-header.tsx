import { Link, useLocation } from "react-router"
import { useTranslation } from "react-i18next"

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { HOME_PATH, resolveNav } from "~/config/page-routes"
import { usePage } from "~/context/page"
import { LanguageSelect } from "../language"
import { ThemeToggleButton } from "../theme"
import { GlobalSearch } from "./global-search"

export function NavHeader() {
  const { t } = useTranslation()
  const { pathname } = useLocation()
  const { detail } = usePage()
  const nav = resolveNav(pathname)
  const isHome = pathname === HOME_PATH
  const isSection = nav && pathname === nav.url

  return (
    <header className="sticky top-0 z-50 flex h-(--header-height) shrink-0 items-center gap-2 border-b bg-background/80 backdrop-blur transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-(--header-height)">
      <div className="flex w-full items-center gap-1 px-4 lg:gap-2 lg:px-6">
        <SidebarTrigger className="-ml-1" />
        <Separator orientation="vertical" className="mx-2 data-[orientation=vertical]:h-4" />

        <Breadcrumb className="min-w-0">
          <BreadcrumbList className="flex-nowrap">
            <BreadcrumbItem>
              {isHome ? (
                <BreadcrumbPage>{t("navigation.overview")}</BreadcrumbPage>
              ) : (
                <BreadcrumbLink asChild>
                  <Link to={HOME_PATH}>{t("navigation.home")}</Link>
                </BreadcrumbLink>
              )}
            </BreadcrumbItem>
            {nav && !isHome && (
              <>
                <BreadcrumbSeparator />
                <BreadcrumbItem>
                  {isSection ? (
                    <BreadcrumbPage>{t(`navigation.${nav.key}`)}</BreadcrumbPage>
                  ) : (
                    <BreadcrumbLink asChild>
                      <Link to={nav.url}>{t(`navigation.${nav.key}`)}</Link>
                    </BreadcrumbLink>
                  )}
                </BreadcrumbItem>
              </>
            )}
            {!isSection && !isHome && detail && (
              <>
                <BreadcrumbSeparator />
                <BreadcrumbItem className="min-w-0">
                  <BreadcrumbPage className="truncate">{detail}</BreadcrumbPage>
                </BreadcrumbItem>
              </>
            )}
          </BreadcrumbList>
        </Breadcrumb>

        <div className="ml-auto flex items-center gap-1">
          <GlobalSearch />
          <LanguageSelect />
          <ThemeToggleButton />
        </div>
      </div>
    </header>
  )
}
