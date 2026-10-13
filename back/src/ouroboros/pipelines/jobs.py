"""Jobs de ingestão: conector + loader + partições padrão. Usados pelo Dagster e pela CLI."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from ouroboros.connectors.base import Connector
from ouroboros.connectors.camara import CamaraCeapConnector, CamaraDeputadosConnector
from ouroboros.connectors.ibge import IbgeConnector
from ouroboros.connectors.senado import SenadoCeapsConnector, SenadoSenadoresConnector
from ouroboros.connectors.tse import TseCandidatosConnector
from ouroboros.core.db import get_engine
from ouroboros.core.settings import get_settings
from ouroboros.pipelines.fotos import coletar_fotos_casa, coletar_fotos_tse
from ouroboros.pipelines.loaders import (
    load_candidaturas,
    load_despesas,
    load_entes,
    load_parlamentares,
)
from ouroboros.pipelines.runner import Loader, run_connector


@dataclass(frozen=True)
class Job:
    """Unidade de ingestão: roda `executar(particao)` para cada partição."""

    nome: str
    descricao: str
    executar: Callable[[str], Awaitable[int]]
    particoes: Callable[[], Sequence[str]]

    async def run(self, particoes: Sequence[str] | None = None) -> int:
        total = 0
        for particao in particoes or self.particoes():
            total += await self.executar(particao)
        return total


def _conector(
    nome: str,
    connector: Callable[[], Connector],
    loader: Loader,
    particoes: Callable[[], Sequence[str]],
) -> Job:
    async def executar(particao: str) -> int:
        return await run_connector(connector(), loader, particao)

    descricao = (connector.__doc__ or nome).strip().splitlines()[0]
    return Job(nome, descricao, executar, particoes)


def _s(values: Sequence[int]) -> list[str]:
    return [str(v) for v in values]


# Ordem importa só para eficiência: TSE primeiro dá CPF/nascimento para ligar o resto.
# Qualquer ordem chega ao mesmo resultado porque despesas são religadas a cada carga de pessoas.
JOBS: dict[str, Job] = {
    j.nome: j
    for j in [
        _conector("ibge", IbgeConnector, load_entes, lambda: ["atual"]),
        _conector(
            "tse_candidatos",
            TseCandidatosConnector,
            load_candidaturas,
            lambda: _s(get_settings().tse_anos),
        ),
        _conector(
            "camara_deputados",
            CamaraDeputadosConnector,
            load_parlamentares,
            lambda: _s(get_settings().camara_legislaturas),
        ),
        _conector(
            "senado_senadores",
            SenadoSenadoresConnector,
            load_parlamentares,
            lambda: _s(get_settings().senado_legislaturas),
        ),
        _conector(
            "camara_ceap",
            CamaraCeapConnector,
            load_despesas,
            lambda: _s(get_settings().despesas_anos),
        ),
        _conector(
            "senado_ceaps",
            SenadoCeapsConnector,
            load_despesas,
            lambda: _s(get_settings().despesas_anos),
        ),
        Job(
            "fotos_parlamentares",
            "Fotos oficiais de deputados federais e senadores",
            coletar_fotos_casa,
            lambda: ["camara", "senado"],
        ),
        Job(
            "tse_fotos",
            "Fotos de todos os candidatos (ZIP por UF do TSE)",
            coletar_fotos_tse,
            lambda: _s(get_settings().tse_anos),
        ),
    ]
}

GRUPOS = {"federal": list(JOBS)}


def run_sync(job: Job, particoes: Sequence[str] | None = None) -> int:
    """Roda um job num event loop novo e descarta o pool no fim.

    Engine é cacheado por processo; conexões ficam presas ao loop que as abriu, então cada
    `asyncio.run` precisa terminar com o pool vazio.
    """

    async def _run() -> int:
        try:
            return await job.run(particoes)
        finally:
            await get_engine().dispose()

    return asyncio.run(_run())
