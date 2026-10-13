"""Fusão de dois `politico` que são a mesma pessoa (ex.: mesmo CPF visto em fontes diferentes)."""

from loguru import logger
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ouroboros.models.despesa import DespesaGabinete
from ouroboros.models.foto import PoliticoFoto
from ouroboros.models.mandato import Candidatura, Mandato
from ouroboros.models.politico import Politico, PoliticoIdentificador
from ouroboros.resolution.fotos import atualizar_fotos_principais

_PREENCHIVEIS = (
    "nome_civil",
    "nome_civil_normalizado",
    "data_nascimento",
    "genero",
    "cpf_hmac",
    "foto_url",
)


async def fundir_politicos(session: AsyncSession, a: int, b: int) -> int:
    """Funde `a` e `b`; fica o de menor id. Retorna o id mantido.

    Tudo que apontava para o removido passa a apontar para o mantido; campos vazios do mantido
    são preenchidos com os do removido. O nome exibido segue a regra de prioridade por fonte.
    """
    from ouroboros.resolution.politicos import _prioridade  # evita import circular

    manter, remover = min(a, b), max(a, b)
    if manter == remover:
        return manter
    rows = (
        (await session.execute(select(Politico).where(Politico.id.in_([manter, remover]))))
        .scalars()
        .all()
    )
    por_id = {p.id: p for p in rows}
    m, r = por_id[manter], por_id[remover]

    valores = {c: getattr(r, c) for c in _PREENCHIVEIS if getattr(m, c) is None}
    if _prioridade(r.nome_origem) > _prioridade(m.nome_origem):
        valores |= {"nome": r.nome, "nome_normalizado": r.nome_normalizado}
        valores["nome_origem"] = r.nome_origem

    for model in (PoliticoIdentificador, Mandato, Candidatura, DespesaGabinete, PoliticoFoto):
        await session.execute(
            update(model)
            .where(model.politico_id == remover)
            .values(politico_id=manter)
            .execution_options(synchronize_session=False)
        )
    # libera o CPF (unique) antes de copiá-lo para o mantido
    await session.execute(delete(Politico).where(Politico.id == remover))
    if valores:
        await session.execute(
            update(Politico)
            .where(Politico.id == manter)
            .values(**valores, atualizado_em=func.now())
            .execution_options(synchronize_session=False)
        )
    await atualizar_fotos_principais(session, [manter])
    session.expunge_all()
    logger.info("fusão: político {} incorporado em {}", remover, manter)
    return manter
