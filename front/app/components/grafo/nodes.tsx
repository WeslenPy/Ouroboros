import { memo } from "react"
import {
  BaseEdge,
  EdgeLabelRenderer,
  Handle,
  Position,
  getStraightPath,
  type EdgeProps,
  type Node,
  type NodeProps,
} from "@xyflow/react"
import { IconArrowsMaximize } from "@tabler/icons-react"

import { Avatar, AvatarFallback, AvatarImage } from "@/ui/avatar"
import type { GrafoNo } from "~/interface/api"
import { formatBRL, initials } from "~/lib/format"
import { cn } from "~/lib/utils"
import { GRUPO, exploravel, iconFor } from "./style"

export interface NodeData extends Record<string, unknown> {
  no: GrafoNo
  imagem: string | null
  centro: boolean
  dim: boolean
  selected: boolean
  /** filhos escondidos: clique abre */
  mais: number
}

export type GraphNode = Node<NodeData>

// Linhas ligam centro a centro: um handle invisível no meio do nó.
const HANDLE = "!pointer-events-none !absolute !top-1/2 !left-1/2 !size-px !min-h-0 !min-w-0 !-translate-1/2 !border-0 !bg-transparent"

function Handles() {
  return (
    <>
      <Handle type="target" position={Position.Top} className={HANDLE} isConnectable={false} />
      <Handle type="source" position={Position.Top} className={HANDLE} isConnectable={false} />
    </>
  )
}

function Mais({ n }: { n: number }) {
  if (!n) return null
  return (
    <span className="absolute -top-2 -right-2 flex h-5 min-w-5 items-center justify-center rounded-full bg-foreground px-1.5 text-[10px] font-bold text-background shadow">
      +{n}
    </span>
  )
}

function Valor({ valor, className }: { valor: string | null; className?: string }) {
  if (valor === null) return null
  return (
    <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-semibold tabular-nums", className)}>
      {formatBRL(valor, true)}
    </span>
  )
}

export const CenterNode = memo(function CenterNode({ data }: NodeProps<GraphNode>) {
  const { no, imagem } = data
  const Icon = iconFor(no)
  return (
    <div className="flex w-64 flex-col items-center gap-2 text-center">
      <Handles />
      <div className="relative">
        <span className="absolute inset-0 animate-ping rounded-full bg-primary/20 [animation-duration:3s]" />
        {imagem ? (
          <Avatar className="relative size-24 border-4 border-primary shadow-xl">
            <AvatarImage src={imagem} alt={no.rotulo} className="object-cover" />
            <AvatarFallback className="text-2xl">{initials(no.rotulo)}</AvatarFallback>
          </Avatar>
        ) : (
          <div className="relative flex size-24 items-center justify-center rounded-full border-4 border-primary bg-card shadow-xl">
            <Icon className="size-10 text-primary" />
          </div>
        )}
      </div>
      <div className="rounded-xl border bg-card/95 px-4 py-2 shadow-lg backdrop-blur">
        <p className="text-lg leading-tight font-bold">{no.rotulo}</p>
        {no.detalhe && <p className="text-xs text-muted-foreground">{no.detalhe}</p>}
        <Valor valor={no.valor} className="mt-1 inline-block bg-primary/10 text-primary" />
      </div>
    </div>
  )
})

export const HubNode = memo(function HubNode({ data }: NodeProps<GraphNode>) {
  const { no, dim, selected, mais } = data
  const Icon = iconFor(no)
  const g = GRUPO[no.grupo]
  return (
    <div
      className={cn(
        "relative flex items-center gap-3 rounded-full border-2 bg-card py-2 pr-4 pl-2 shadow-md transition-all duration-200",
        g.border,
        dim && "opacity-25",
        selected && "ring-4 ring-ring/40",
      )}
    >
      <Handles />
      <Mais n={mais} />
      <span className={cn("flex size-10 items-center justify-center rounded-full", g.chip)}>
        <Icon className="size-5" />
      </span>
      <div className="min-w-0">
        <p className="text-sm leading-tight font-semibold whitespace-nowrap">{no.rotulo}</p>
        {no.detalhe && (
          <p className="max-w-52 truncate text-[11px] text-muted-foreground">{no.detalhe}</p>
        )}
      </div>
      <Valor valor={no.valor} className={g.chip} />
    </div>
  )
})

export const EntityNode = memo(function EntityNode({ data }: NodeProps<GraphNode>) {
  const { no, imagem, dim, selected, mais } = data
  const Icon = iconFor(no)
  const g = GRUPO[no.grupo]
  return (
    <div
      className={cn(
        "group relative flex w-52 cursor-pointer items-center gap-2.5 rounded-xl border bg-card p-2 shadow-sm transition-all duration-200 hover:shadow-md",
        g.border,
        dim && "opacity-20",
        selected && "ring-4 ring-ring/40",
      )}
    >
      <Handles />
      <Mais n={mais} />
      {imagem ? (
        <Avatar className="size-9 shrink-0">
          <AvatarImage src={imagem} alt={no.rotulo} className="object-cover" />
          <AvatarFallback className="text-[10px]">{initials(no.rotulo)}</AvatarFallback>
        </Avatar>
      ) : (
        <span className={cn("flex size-9 shrink-0 items-center justify-center rounded-lg", g.chip)}>
          <Icon className="size-4.5" />
        </span>
      )}
      <div className="min-w-0 flex-1">
        <p className="line-clamp-2 text-xs leading-tight font-semibold" title={no.rotulo}>
          {no.rotulo}
        </p>
        {no.valor !== null ? (
          <p className="text-[11px] font-medium text-muted-foreground tabular-nums">
            {formatBRL(no.valor, true)}
          </p>
        ) : (
          no.detalhe && <p className="truncate text-[11px] text-muted-foreground">{no.detalhe}</p>
        )}
      </div>
      {exploravel(no) && (
        <IconArrowsMaximize className="size-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
      )}
    </div>
  )
})

export interface EdgeData extends Record<string, unknown> {
  valor: number | null
  cor: string
  largura: number
  dim: boolean
  destaque: boolean
  rotulo: string | null
}

/** Linha reta entre centros; espessura proporcional ao dinheiro; rótulo com o valor. */
export function MoneyEdge({ id, sourceX, sourceY, targetX, targetY, data }: EdgeProps) {
  const d = data as EdgeData
  const [path, labelX, labelY] = getStraightPath({ sourceX, sourceY, targetX, targetY })
  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        style={{
          stroke: d.cor,
          strokeWidth: d.largura,
          opacity: d.dim ? 0.08 : d.destaque ? 0.95 : 0.45,
          transition: "opacity 200ms",
        }}
        className={d.destaque ? "[stroke-dasharray:8_6] animate-[dash_1s_linear_infinite]" : undefined}
      />
      {d.rotulo && d.destaque && (
        <EdgeLabelRenderer>
          <div
            className="nodrag nopan pointer-events-none absolute rounded-full border bg-background px-2 py-0.5 text-[10px] font-semibold tabular-nums shadow-sm"
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
          >
            {d.rotulo}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  )
}

export const nodeTypes = { center: CenterNode, hub: HubNode, entity: EntityNode }
export const edgeTypes = { money: MoneyEdge }
