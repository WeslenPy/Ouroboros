import { useEffect, useState } from "react"
import { useNavigate } from "react-router"
import { IconSearch } from "@tabler/icons-react"
import { useTranslation } from "react-i18next"

import { Button } from "@/ui/button"
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/ui/command"
import { useApi } from "~/context/api"
import type { PoliticoResumo } from "~/interface/api"
import { PoliticoAvatar } from "../politico-avatar"
import { useCargoLabel } from "../labels"

/** Busca rápida de políticos (Ctrl/⌘ + K). */
export function GlobalSearch() {
  const { t } = useTranslation()
  const api = useApi()
  const navigate = useNavigate()
  const cargoLabel = useCargoLabel()
  const [open, setOpen] = useState(false)
  const [term, setTerm] = useState("")
  const [results, setResults] = useState<PoliticoResumo[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setOpen((o) => !o)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])

  useEffect(() => {
    if (term.trim().length < 3) {
      setResults([])
      return
    }
    let active = true
    setLoading(true)
    const id = window.setTimeout(() => {
      api
        .politicos({ busca: term.trim(), limit: 12 })
        .then((page) => active && setResults(page.items))
        .catch(() => active && setResults([]))
        .finally(() => active && setLoading(false))
    }, 250)
    return () => {
      active = false
      window.clearTimeout(id)
    }
  }, [term, api])

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        className="h-8 gap-2 text-muted-foreground max-sm:w-8 max-sm:px-0 sm:w-56 sm:justify-start"
        onClick={() => setOpen(true)}
      >
        <IconSearch className="size-4" />
        <span className="max-sm:hidden">{t("search.placeholder")}</span>
        <kbd className="ml-auto rounded border bg-muted px-1.5 text-[10px] font-medium max-sm:hidden">
          Ctrl K
        </kbd>
      </Button>
      <CommandDialog open={open} onOpenChange={setOpen} shouldFilter={false}>
        <CommandInput placeholder={t("search.placeholder")} value={term} onValueChange={setTerm} />
        <CommandList>
          <CommandEmpty>
            {term.trim().length < 3
              ? t("search.minChars")
              : loading
                ? t("common.loading")
                : t("common.noResults")}
          </CommandEmpty>
          {results.length > 0 && (
            <CommandGroup heading={t("navigation.politicos")}>
              {results.map((p) => (
                <CommandItem
                  key={p.id}
                  value={String(p.id)}
                  onSelect={() => {
                    setOpen(false)
                    navigate(`/politicos/${p.id}`)
                  }}
                  className="gap-3"
                >
                  <PoliticoAvatar politico={p} className="size-7" />
                  <div className="flex min-w-0 flex-col">
                    <span className="truncate">{p.nome}</span>
                    {p.ultimo_mandato && (
                      <span className="truncate text-xs text-muted-foreground">
                        {cargoLabel(p.ultimo_mandato.cargo)} · {p.ultimo_mandato.partido_sigla ?? "—"}
                        {p.ultimo_mandato.uf ? `/${p.ultimo_mandato.uf}` : ""}
                      </span>
                    )}
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          )}
        </CommandList>
      </CommandDialog>
    </>
  )
}
