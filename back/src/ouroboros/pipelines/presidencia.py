"""Loaders da Presidência: presidentes (reusa load_parlamentares) e gastos do cartão."""

from collections.abc import Sequence

from pydantic import BaseModel
from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession

from ouroboros.canonical import GastoPresidenciaRow
from ouroboros.models.presidencia import GastoPresidencia

_LOTE = 5000


async def load_gastos_presidencia(
    session: AsyncSession, rows: Sequence[BaseModel], particao: str
) -> int:
    """Substitui a partição inteira: '2003-2022' (Casa Civil) ou um ano do Portal.

    O Portal publica o mês pelo extrato; a partição é esse ano, não o da data da compra.
    """
    gastos = [r for r in rows if isinstance(r, GastoPresidenciaRow)]
    fontes = {g.fonte for g in gastos}
    if "-" in particao:
        inicio, fim = (int(x) for x in particao.split("-"))
    else:
        inicio = fim = int(particao)
    for fonte in fontes:
        stmt = delete(GastoPresidencia).where(GastoPresidencia.fonte == fonte)
        # Casa Civil é um arquivo só: apaga tudo dela. Portal: só o ano da partição.
        if "-" not in particao:
            stmt = stmt.where(GastoPresidencia.ano.between(inicio, fim))
        await session.execute(stmt)
    valores = [g.model_dump() for g in gastos]
    for i in range(0, len(valores), _LOTE):
        await session.execute(insert(GastoPresidencia), valores[i : i + _LOTE])
    return len(valores)
