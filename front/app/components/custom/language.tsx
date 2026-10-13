"use client"

import * as React from "react"
import { Check } from "lucide-react"
import { ReactCountryFlag } from "react-country-flag"

import { cn } from "~/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"

import { useTranslation } from "react-i18next"

export function LanguageSelect({
  className,
  variant = "default",
}: {
  className?: string
  variant?: "default" | "menu"
}) {
    const { i18n, t } = useTranslation()
    const [open, setOpen] = React.useState(false)
    const [value, setValue] = React.useState(i18n.language)

    const languages = [
        {
        value: "pt",
        label: t("languages.portuguese"),
        countryCode: "BR",
        },
        {
        value: "en",
        label: t("languages.english"),
        countryCode: "US",
        },
    ]



    const switchLanguage = (lang: string) => {
        i18n.changeLanguage(lang)
        setValue(lang)
    }

  



    const currentLanguage = languages.find((l) => l.value === value || l.countryCode == value)

    return (
        <div className={className}>
            <Popover open={open} onOpenChange={setOpen} >
            <PopoverTrigger asChild>
                <Button
                variant="outline"
                role="combobox"
                aria-expanded={open}
                className={cn(
                  "flex h-9 items-center gap-2 text-sm",
                  variant === "menu"
                    ? "w-full justify-start"
                    : "mt-3 mb-3 h-8",
                )}
                >
                <ReactCountryFlag
                    countryCode={currentLanguage?.countryCode ?? "BR"}
                    svg
                    style={{ width: "1.5em", height: "1.5em" }}
                />
                <span className={variant === "menu" ? undefined : "max-sm:hidden"}>
                  {currentLanguage?.label}
                </span>
                </Button>
            </PopoverTrigger>

            <PopoverContent className="z-[110] w-[200px] p-0">
                <Command>
                <CommandInput placeholder={t("common.searchLanguage")} className="h-9" />
                <CommandList>
                    <CommandEmpty>{t("common.noLanguage")}</CommandEmpty>
                    <CommandGroup>
                    {languages.map((language) => (
                        <CommandItem
                        key={language.value}
                        value={language.value}
                        onSelect={(currentValue) => {
                            switchLanguage(currentValue)
                            setOpen(false)
                        }}
                        className="flex items-center gap-2"
                        >
                        <ReactCountryFlag
                            countryCode={language.countryCode}
                            svg
                            style={{ width: "1.5em", height: "1.5em" }}
                        />
                        <span>{language.label}</span>
                        <Check
                            className={cn(
                            "ml-auto",
                            value === language.value ? "opacity-100" : "opacity-0"
                            )}
                        />
                        </CommandItem>
                    ))}
                    </CommandGroup>
                </CommandList>
                </Command>
            </PopoverContent>
            </Popover>

        </div>
  )
}
