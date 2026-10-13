"""CLI: `ouroboros ingest <job|grupo> [-p PARTICAO ...]` roda ingestão sem precisar do Dagster."""

import argparse

from ouroboros.core.logging import setup_logging
from ouroboros.pipelines.jobs import GRUPOS, JOBS, run_sync


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
    args = parser.parse_args(argv)

    setup_logging()
    if args.cmd == "ingest":
        nomes = GRUPOS.get(args.alvo, [args.alvo])
        if args.particao and len(nomes) > 1:
            parser.error("--particao só vale para um job, não para grupo")
        for nome in nomes:
            total = run_sync(JOBS[nome], args.particao)
            print(f"{nome}: {total} registros")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
