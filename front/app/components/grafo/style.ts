import {
  IconBriefcase,
  IconBuildingBank,
  IconBuildingCommunity,
  IconBuildingStore,
  IconCategory,
  IconCheckbox,
  IconFlag,
  IconId,
  IconMapPin,
  IconReceipt,
  IconTag,
  IconUser,
  IconUsersGroup,
  type Icon,
} from "@tabler/icons-react"

import type { GrafoGrupo, GrafoNo } from "~/interface/api"

export interface GrupoStyle {
  /** cor da linha (SVG) */
  stroke: string
  /** ícone/realce do nó */
  chip: string
  /** borda do cartão */
  border: string
  /** ponto da legenda */
  dot: string
}

export const GRUPO: Record<GrafoGrupo, GrupoStyle> = {
  centro: {
    stroke: "var(--primary)",
    chip: "bg-primary text-primary-foreground",
    border: "border-primary",
    dot: "bg-primary",
  },
  carreira: {
    stroke: "#8b5cf6",
    chip: "bg-violet-500/15 text-violet-600 dark:text-violet-300",
    border: "border-violet-500/40",
    dot: "bg-violet-500",
  },
  gastos: {
    stroke: "#f59e0b",
    chip: "bg-amber-500/15 text-amber-600 dark:text-amber-300",
    border: "border-amber-500/40",
    dot: "bg-amber-500",
  },
  emendas: {
    stroke: "#10b981",
    chip: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300",
    border: "border-emerald-500/40",
    dot: "bg-emerald-500",
  },
  conexoes: {
    stroke: "#0ea5e9",
    chip: "bg-sky-500/15 text-sky-600 dark:text-sky-300",
    border: "border-sky-500/40",
    dot: "bg-sky-500",
  },
}

const POR_TIPO: Record<string, Icon> = {
  politico: IconUser,
  partido: IconFlag,
  cargo: IconId,
  eleicao: IconCheckbox,
  categoria: IconTag,
  fornecedor: IconBuildingStore,
  area: IconCategory,
  municipio: IconMapPin,
  favorecido: IconBuildingCommunity,
  autor: IconUsersGroup,
}

const POR_HUB: Record<string, Icon> = {
  "hub:carreira": IconBriefcase,
  "hub:gastos": IconReceipt,
  "hub:emendas": IconBuildingBank,
  "hub:autores": IconUsersGroup,
  "hub:areas": IconCategory,
}

export function iconFor(no: GrafoNo): Icon {
  if (no.tipo === "hub") return POR_HUB[no.id] ?? IconCategory
  return POR_TIPO[no.tipo] ?? IconCategory
}

/** Nó pode virar centro de outro grafo. */
export function exploravel(no: GrafoNo): string | null {
  if (!no.chave) return null
  if (no.tipo === "politico") return `politico:${no.chave}`
  if (no.tipo === "fornecedor" || no.tipo === "favorecido") return `doc:${no.chave}`
  if (no.tipo === "municipio") return `municipio:${no.chave}`
  return null
}

/** Página do app com mais detalhes do nó. */
export function paginaDe(no: GrafoNo): string | null {
  if (!no.chave) return null
  switch (no.tipo) {
    case "politico":
      return `/politicos/${no.chave}`
    case "partido":
      return `/partidos/${encodeURIComponent(no.chave)}`
    case "fornecedor":
    case "favorecido":
      return `/fornecedores/${encodeURIComponent(no.chave)}`
    case "municipio":
      return `/emendas?municipio=${no.chave}`
    default:
      return null
  }
}
