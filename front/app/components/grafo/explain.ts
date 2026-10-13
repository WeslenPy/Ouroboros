import type { TFunction } from "i18next"

import type { Grafo, GrafoNo } from "~/interface/api"
import { formatBRL } from "~/lib/format"

/**
 * Frase em português simples que explica o que o nó significa em relação ao centro do grafo.
 * Ex.: "Chico Alencar pagou R$ 488 mil a Cia Aérea - TAM com a cota parlamentar."
 */
export function explicar(no: GrafoNo, grafo: Grafo, t: TFunction): string {
  const byId = new Map(grafo.nos.map((n) => [n.id, n]))
  const centro = byId.get(grafo.centro)
  const pai = no.pai ? byId.get(no.pai) : undefined
  const tipoCentro = grafo.centro.split(":")[0] // politico | doc | municipio | obra
  const vars = {
    centro: centro?.rotulo ?? "",
    rotulo: no.rotulo,
    pai: pai?.rotulo ?? "",
    detalhe: no.detalhe ?? "",
    valor: no.valor !== null ? formatBRL(no.valor, true) : "",
  }
  const k = (key: string) => t(`grafo.explica.${key}`, vars)

  if (no.id === grafo.centro) return k(`centro_${tipoCentro}`)
  switch (no.tipo) {
    case "hub":
      return k(`${no.id.replace("hub:", "hub_")}_${tipoCentro}`)
    case "categoria":
      return k(tipoCentro === "doc" ? "categoria_doc" : "categoria")
    case "fornecedor":
      if (pai?.tipo === "obra") return k("empreiteira")
      if (pai?.id === "hub:execucao") return k("executou")
      return k("fornecedor")
    case "obra":
      if (pai?.tipo === "fornecedor") return k("obra_empreiteira")
      return k(tipoCentro === "municipio" ? "obra_municipio" : "obra")
    case "area":
      return k(tipoCentro === "municipio" ? "area_municipio" : "area")
    case "municipio":
      return k(pai?.id === "hub:local" ? "local_obra" : "municipio")
    case "favorecido":
      return k(pai?.id === "hub:local" ? "convenente" : "favorecido")
    case "autor":
      return k("autor")
    case "cargo":
      return k("cargo")
    case "eleicao":
      return k("eleicao")
    case "partido":
      return pai?.tipo === "politico" ? k("partido_de") : k("partido")
    case "politico":
      if (pai?.tipo === "fornecedor" && pai.grupo === "obras") return k("conexao_obra")
      if (pai?.tipo === "fornecedor") return k("conexao_fornecedor")
      if (pai?.tipo === "favorecido") return k("conexao_favorecido")
      if (pai?.tipo === "obra") return k("politico_obra")
      if (pai?.id === "hub:gastos") return k("politico_pagou")
      if (pai?.id === "hub:emendas") return k(tipoCentro === "obra" ? "politico_financiou" : "politico_emendou")
      if (pai?.id === "hub:autores") return k("politico_autor")
      return k("politico")
    default:
      return no.detalhe ?? no.rotulo
  }
}
