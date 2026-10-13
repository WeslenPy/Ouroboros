"""Roda os detectores e substitui a tabela `alerta` numa transação só."""

import time

from loguru import logger
from sqlalchemy import delete, insert, text

from ouroboros.analises.detectores import CATALOGO
from ouroboros.core.db import get_sessionmaker
from ouroboros.models import Alerta
from ouroboros.pipelines.runner import registrar_execucao

LOTE = 2000


async def gerar_alertas(particao: str = "atual", detectores: list[str] | None = None) -> int:
    """Recalcula os alertas. Com `detectores`, só esses são substituídos; os demais ficam."""
    escolhidos = [CATALOGO[c] for c in detectores] if detectores else list(CATALOGO.values())
    async with registrar_execucao("ouroboros", "alertas", particao) as contador:
        async with get_sessionmaker()() as session:
            # consultas analíticas varrem milhões de linhas; não herdar timeout curto do pool
            await session.execute(text("set local statement_timeout = 0"))
            await session.execute(text("set local work_mem = '256MB'"))
            novos: dict[str, dict] = {}
            for det in escolhidos:
                inicio = time.monotonic()
                alertas = await det.executar(session)
                for a in alertas:
                    atual = novos.get(a["chave"])
                    if atual is None or a["score"] > atual["score"]:
                        novos[a["chave"]] = a
                logger.info(
                    "detector {}: {} alertas em {:.1f}s",
                    det.codigo,
                    len(alertas),
                    time.monotonic() - inicio,
                )
            await session.execute(
                delete(Alerta).where(Alerta.detector.in_([d.codigo for d in escolhidos]))
            )
            linhas = list(novos.values())
            for i in range(0, len(linhas), LOTE):
                await session.execute(insert(Alerta), linhas[i : i + LOTE])
            await session.commit()
        contador.registros = len(linhas)
    return len(linhas)
