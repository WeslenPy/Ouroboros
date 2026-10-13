"""Escolha da foto principal de cada político entre as fotos coletadas."""

from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def atualizar_fotos_principais(
    session: AsyncSession, politico_ids: Sequence[int] | None = None
) -> None:
    """Foto principal = a mais recente; no empate, a oficial da casa legislativa; depois a de
    maior resolução."""
    filtro = "WHERE politico_id = ANY(:ids)" if politico_ids is not None else ""
    await session.execute(
        text(
            f"""
            UPDATE politico p SET foto_id = f.id
            FROM (
                SELECT DISTINCT ON (politico_id) politico_id, id
                FROM politico_foto
                {filtro}
                ORDER BY politico_id,
                         ano DESC NULLS LAST,
                         (origem IN ('camara', 'senado')) DESC,
                         largura::int * altura::int DESC,
                         id DESC
            ) f
            WHERE p.id = f.politico_id AND p.foto_id IS DISTINCT FROM f.id
            """
        ),
        {"ids": list(politico_ids)} if politico_ids is not None else {},
    )
