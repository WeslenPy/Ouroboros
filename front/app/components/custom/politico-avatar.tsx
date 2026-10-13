import { Avatar, AvatarFallback, AvatarImage } from "@/ui/avatar"
import { useApi } from "~/context/api"
import type { PoliticoResumo } from "~/interface/api"
import { initials } from "~/lib/format"
import { cn } from "~/lib/utils"

export function PoliticoAvatar({
  politico,
  className,
}: {
  politico: Pick<PoliticoResumo, "nome" | "foto">
  className?: string
}) {
  const api = useApi()
  return (
    <Avatar className={cn("size-9", className)}>
      {politico.foto && (
        <AvatarImage src={api.url(politico.foto.url)} alt={politico.nome} className="object-cover" />
      )}
      <AvatarFallback className="text-xs">{initials(politico.nome)}</AvatarFallback>
    </Avatar>
  )
}
