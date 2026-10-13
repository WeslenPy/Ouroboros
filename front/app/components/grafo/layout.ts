import type { GrafoNo } from "~/interface/api"

export interface Point {
  x: number
  y: number
}

const ANEL_1 = 270 // raio do primeiro anel (temas)
const ANEL_MIN = 300 // distância mínima entre anéis seguintes (cartões têm ~210px)
const ESPACO_NO = 250 // espaço que cada nó ocupa no arco

/**
 * Layout radial por árvore: centro no meio, cada nível num anel, e cada ramo recebe um setor
 * proporcional ao número de folhas. Ramos do mesmo hub ficam juntos, então o desenho conta
 * a história "centro -> tema -> detalhe -> conexão" sem cruzar linhas.
 */
export function radialLayout(nos: GrafoNo[], centro: string): Map<string, Point> {
  const byId = new Map(nos.map((n) => [n.id, n]))
  const filhos = new Map<string, string[]>()
  for (const n of nos) {
    if (n.id === centro) continue
    const pai = n.pai && byId.has(n.pai) ? n.pai : centro
    if (!filhos.has(pai)) filhos.set(pai, [])
    filhos.get(pai)!.push(n.id)
  }

  const peso = new Map<string, number>()
  const pesar = (id: string): number => {
    const f = filhos.get(id) ?? []
    const w = f.length ? f.reduce((acc, c) => acc + pesar(c), 0) : 1
    peso.set(id, w)
    return w
  }
  pesar(centro)

  // profundidade real (pela árvore) e raio de cada anel, grande o bastante para não sobrepor
  const profundidade = new Map<string, number>([[centro, 0]])
  const porNivel: number[] = []
  const visitar = (id: string, d: number) => {
    porNivel[d] = (porNivel[d] ?? 0) + 1
    for (const c of filhos.get(id) ?? []) {
      profundidade.set(c, d + 1)
      visitar(c, d + 1)
    }
  }
  visitar(centro, 0)
  const raio: number[] = [0]
  for (let d = 1; d < porNivel.length; d++) {
    const minimo = (porNivel[d] * ESPACO_NO) / (2 * Math.PI)
    raio[d] = Math.max(d === 1 ? ANEL_1 : raio[d - 1] + ANEL_MIN, minimo)
  }

  const pos = new Map<string, Point>([[centro, { x: 0, y: 0 }]])
  const distribuir = (id: string, inicio: number, fim: number) => {
    const f = filhos.get(id) ?? []
    const total = f.reduce((acc, c) => acc + (peso.get(c) ?? 1), 0) || 1
    let a = inicio
    for (const c of f) {
      const span = ((fim - inicio) * (peso.get(c) ?? 1)) / total
      const meio = a + span / 2
      const r = raio[profundidade.get(c) ?? 1]
      pos.set(c, { x: Math.cos(meio) * r, y: Math.sin(meio) * r })
      distribuir(c, a, a + span)
      a += span
    }
  }
  distribuir(centro, -Math.PI / 2, (3 * Math.PI) / 2)
  return pos
}

/** Cadeia de ancestrais (pelo campo `pai`) até o centro, incluindo o próprio nó. */
export function caminho(nos: Map<string, GrafoNo>, id: string): string[] {
  const out: string[] = []
  let atual: string | null | undefined = id
  const vistos = new Set<string>()
  while (atual && !vistos.has(atual)) {
    vistos.add(atual)
    out.push(atual)
    atual = nos.get(atual)?.pai
  }
  return out
}
