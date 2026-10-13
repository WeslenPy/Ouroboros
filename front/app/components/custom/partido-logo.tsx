import { useState } from "react"

import { useApi } from "~/context/api"
import type { PartidoOut } from "~/interface/api"
import { cn } from "~/lib/utils"

/** Logo do partido; sem logo (ou se falhar ao carregar) mostra o número TSE ou a sigla. */
export function PartidoLogo({
  partido,
  className,
}: {
  partido: Pick<PartidoOut, "sigla" | "numero_tse" | "logo">
  className?: string
}) {
  const api = useApi()
  const [falhou, setFalhou] = useState(false)
  const base = "flex shrink-0 items-center justify-center overflow-hidden rounded-lg"

  if (partido.logo && !falhou) {
    return (
      // fundo claro fixo: logos costumam ter transparência pensada para fundo branco
      <div className={cn(base, "bg-white p-1 ring-1 ring-border", className)}>
        <img
          src={api.url(partido.logo.url)}
          alt={partido.sigla}
          loading="lazy"
          className="size-full object-contain"
          onError={() => setFalhou(true)}
        />
      </div>
    )
  }
  return (
    <div className={cn(base, "bg-primary/10 font-mono font-bold text-primary", className)}>
      {partido.numero_tse ?? partido.sigla.slice(0, 3)}
    </div>
  )
}
