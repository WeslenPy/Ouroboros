from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

from loguru import logger
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ouroboros.connectors.base import Connector
from ouroboros.core.db import get_sessionmaker
from ouroboros.core.raw_store import RawRecord, RawStore
from ouroboros.models.fonte import FonteExecucao, StatusExecucao

Loader = Callable[[AsyncSession, Sequence[BaseModel], str], Awaitable[int]]


async def _iniciar(fonte: str, recurso: str, particao: str) -> FonteExecucao:
    async with get_sessionmaker()() as session:
        execucao = FonteExecucao(
            fonte=fonte,
            recurso=recurso,
            particao=particao,
            status=StatusExecucao.RODANDO,
            registros=0,
        )
        session.add(execucao)
        await session.commit()
    return execucao


async def _finalizar(
    execucao: FonteExecucao,
    status: StatusExecucao,
    *,
    registros: int = 0,
    erro: str | None = None,
    session: AsyncSession | None = None,
) -> None:
    execucao.status = status
    execucao.registros = registros
    execucao.erro = erro[:4000] if erro else None
    execucao.finalizado_em = datetime.now(UTC)
    if session is not None:
        session.add(execucao)
        return
    async with get_sessionmaker()() as s:
        s.add(execucao)
        await s.commit()


@dataclass
class Contador:
    registros: int = 0


@asynccontextmanager
async def registrar_execucao(fonte: str, recurso: str, particao: str) -> AsyncIterator[Contador]:
    """Para jobs que não são conector+loader (ex.: coleta de fotos): registra início, fim e
    erro em fonte_execucao. O job atualiza `contador.registros`."""
    execucao = await _iniciar(fonte, recurso, particao)
    contador = Contador()
    try:
        yield contador
    except Exception as exc:
        await _finalizar(
            execucao, StatusExecucao.FALHA, registros=contador.registros, erro=repr(exc)
        )
        raise
    await _finalizar(execucao, StatusExecucao.SUCESSO, registros=contador.registros)
    logger.info("{}/{}/{}: {} registros", fonte, recurso, particao, contador.registros)


async def run_connector(
    connector: Connector,
    loader: Loader,
    particao: str,
    *,
    store: RawStore | None = None,
) -> int:
    """extract -> salva brutos -> transform -> load numa transação, registrando em fonte_execucao.

    A partição é atômica: ou entra inteira ou nada muda no banco.
    """
    store = store or RawStore()
    execucao = await _iniciar(connector.fonte, connector.recurso, particao)
    try:
        records: list[RawRecord] = []
        async for record in connector.extract(particao):
            store.save(record)
            records.append(record)
        logger.info(
            "{}/{}/{}: {} arquivos brutos",
            connector.fonte,
            connector.recurso,
            particao,
            len(records),
        )
        rows = connector.transform(records)
        async with get_sessionmaker()() as session:
            count = await loader(session, rows, particao)
            await _finalizar(execucao, StatusExecucao.SUCESSO, registros=count, session=session)
            await session.commit()
    except Exception as exc:
        await _finalizar(execucao, StatusExecucao.FALHA, erro=repr(exc))
        raise

    logger.info("{}/{}/{}: {} registros", connector.fonte, connector.recurso, particao, count)
    return count
