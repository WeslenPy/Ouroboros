import * as React from "react"
import { NavLink } from "react-router"
import { IconBook2, IconExternalLink, type Icon } from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/ui/sidebar"
import { APP_NAME, NAV_MAIN, NAV_SECONDARY, type NavEntry } from "~/config/page-routes"
import { DAGSTER_URL, HOST_API } from "~/constants/url"
import { HealthBadge } from "./health"
import { Logo } from "../logo"

function NavItem({ entry }: { entry: NavEntry }) {
  const { t } = useTranslation()
  const Icon = entry.icon
  const title = t(`navigation.${entry.key}`)
  return (
    <SidebarMenuItem>
      <NavLink to={entry.url} end={entry.url === "/"} preventScrollReset>
        {({ isActive }) => (
          <SidebarMenuButton isActive={isActive} tooltip={title}>
            <Icon />
            <span>{title}</span>
          </SidebarMenuButton>
        )}
      </NavLink>
    </SidebarMenuItem>
  )
}

function ExternalItem({ title, url, icon: Icon }: { title: string; url: string; icon: Icon }) {
  return (
    <SidebarMenuItem>
      <SidebarMenuButton asChild tooltip={title}>
        <a href={url} target="_blank" rel="noreferrer">
          <Icon />
          <span>{title}</span>
          <IconExternalLink className="ml-auto !size-3 opacity-60" />
        </a>
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const { t } = useTranslation()

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              asChild
              tooltip={APP_NAME}
              className="hover:bg-transparent active:bg-transparent"
            >
              <NavLink to="/">
                <Logo />
              </NavLink>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>{t("navigation.groups.data")}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV_MAIN.map((entry) => (
                <NavItem key={entry.url} entry={entry} />
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel>{t("navigation.groups.ops")}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV_SECONDARY.map((entry) => (
                <NavItem key={entry.url} entry={entry} />
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup className="mt-auto">
          <SidebarGroupContent>
            <SidebarMenu>
              <ExternalItem title={t("navigation.apiDocs")} url={`${HOST_API}/docs`} icon={IconBook2} />
              <ExternalItem title="Dagster" url={DAGSTER_URL} icon={IconExternalLink} />
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <HealthBadge />
      </SidebarFooter>
    </Sidebar>
  )
}
