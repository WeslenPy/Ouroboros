import {
  IconAlertTriangle,
  IconBuildingCommunity,
  IconCash,
  IconCloudDownload,
  IconFlag,
  IconLayoutDashboard,
  IconMapPin,
  IconTicket,
  IconUsers,
  type Icon,
} from "@tabler/icons-react"

export const APP_NAME = "Ouroboros"
export const HOME_PATH = "/"

export interface NavEntry {
  /** chave i18n em `navigation.*` */
  key: string
  url: string
  icon: Icon
}

export const NAV_MAIN: NavEntry[] = [
  { key: "overview", url: "/", icon: IconLayoutDashboard },
  { key: "politicos", url: "/politicos", icon: IconUsers },
  { key: "despesas", url: "/despesas", icon: IconCash },
  { key: "candidaturas", url: "/candidaturas", icon: IconTicket },
  { key: "partidos", url: "/partidos", icon: IconFlag },
  { key: "entes", url: "/entes", icon: IconMapPin },
]

export const NAV_SECONDARY: NavEntry[] = [
  { key: "fontes", url: "/fontes", icon: IconCloudDownload },
  { key: "matches", url: "/matches", icon: IconAlertTriangle },
]

export const NAV_ALL = [...NAV_MAIN, ...NAV_SECONDARY]

/** Item de navegação que contém o caminho atual (o mais específico). */
export function resolveNav(pathname: string): NavEntry | undefined {
  if (pathname === "/") return NAV_MAIN[0]
  return NAV_ALL.filter((n) => n.url !== "/" && pathname.startsWith(n.url)).sort(
    (a, b) => b.url.length - a.url.length,
  )[0]
}

export { IconBuildingCommunity as AppIcon }
