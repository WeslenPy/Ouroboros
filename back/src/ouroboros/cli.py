"""CLI: `ouroboros ingest <job|grupo> [-p PARTICAO ...]` roda ingestão sem precisar do Dagster.

`ouroboros logo <partido> (--url URL [--sem-baixar] | --arquivo CAMINHO | --remover)` define a
logo manual de um partido (sigla ou número TSE), que tem prioridade sobre a coletada.
"""

import argparse
import asyncio
from pathlib import Path

import httpx

from ouroboros.core.db import get_engine
from ouroboros.core.logging import setup_logging
from ouroboros.pipelines.jobs import GRUPOS, JOBS, run_sync
from ouroboros.pipelines.logos import (
    PartidoNaoEncontrado,
    registrar_logo_manual,
    remover_logo_manual,
)


def _logo(args: argparse.Namespace) -> str:
    async def _run() -> str:
        try:
            if args.remover:
                removida = await remover_logo_manual(args.partido)
                return "logo manual removida" if removida else "partido não tinha logo manual"
            imagem = await registrar_logo_manual(
                args.partido,
                url=args.url,
                arquivo=Path(args.arquivo) if args.arquivo else None,
                baixar=not args.sem_baixar,
            )
            return f"logo de {args.partido}: {imagem.largura}x{imagem.altura} {imagem.extensao}"
        finally:
            await get_engine().dispose()

    return asyncio.run(_run())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ouroboros")
    sub = parser.add_subparsers(dest="cmd", required=True)
    ingest = sub.add_parser("ingest", help="roda a ingestão de uma fonte (ou grupo de fontes)")
    ingest.add_argument("alvo", choices=[*JOBS, *GRUPOS])
    ingest.add_argument(
        "-p",
        "--particao",
        action="append",
        help="partição (ano, legislatura...); repetível. Padrão: as de settings.",
    )
    logo = sub.add_parser("logo", help="define a logo manual de um partido")
    logo.add_argument("partido", help="sigla ou número TSE")
    origem = logo.add_mutually_exclusive_group(required=True)
    origem.add_argument("--url", help="URL da imagem (JPEG, PNG ou WEBP)")
    origem.add_argument("--arquivo", help="arquivo local da imagem")
    origem.add_argument("--remover", action="store_true", help="apaga a logo manual")
    logo.add_argument(
        "--sem-baixar",
        action="store_true",
        help="com --url: só valida e guarda a URL; a imagem é servida pela origem",
    )
    args = parser.parse_args(argv)

    setup_logging()
    if args.cmd == "ingest":
        nomes = GRUPOS.get(args.alvo, [args.alvo])
        if args.particao and len(nomes) > 1:
            parser.error("--particao só vale para um job, não para grupo")
        for nome in nomes:
            total = run_sync(JOBS[nome], args.particao)
            print(f"{nome}: {total} registros")
    elif args.cmd == "logo":
        if args.sem_baixar and not args.url:
            parser.error("--sem-baixar só vale com --url")
        try:
            print(_logo(args))
        # ValueError cobre imagem inválida e URL não http(s)
        except (PartidoNaoEncontrado, ValueError, OSError, httpx.HTTPError) as exc:
            parser.exit(1, f"erro: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
