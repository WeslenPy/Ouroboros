from fastapi import APIRouter
from sqlalchemy import desc, func, select

from ouroboros.api.deps import Session
from ouroboros.api.queries import mandato_em_exercicio
from ouroboros.api.schemas import Contagem, Estatisticas, TotalVerba
from ouroboros.models import (
    Candidatura,
    DespesaGabinete,
    Ente,
    FonteExecucao,
    Mandato,
    MatchPendente,
    Partido,
    Politico,
    PoliticoFoto,
    StatusExecucao,
)

router = APIRouter(prefix="/stats", tags=["estatísticas"])


async def _contar(session: Session, model, *where) -> int:
    return await session.scalar(select(func.count()).select_from(model).where(*where)) or 0


async def _em_exercicio_por(session: Session, coluna) -> list[Contagem]:
    qtd = func.count(func.distinct(Mandato.politico_id)).label("quantidade")
    rows = await session.execute(
        select(coluna, qtd)
        .where(*mandato_em_exercicio())
        .group_by(coluna)
        .order_by(desc("quantidade"))
    )
    return [Contagem(chave=None if c is None else str(c), quantidade=q) for c, q in rows]


@router.get("", response_model=Estatisticas, summary="Contagens globais e distribuições")
async def estatisticas(session: Session) -> Estatisticas:
    d = DespesaGabinete
    total_despesas, qtd_despesas = (
        await session.execute(select(func.coalesce(func.sum(d.valor_liquido), 0), func.count()))
    ).one()
    por_verba = await session.execute(
        select(d.verba, func.sum(d.valor_liquido), func.count()).group_by(d.verba).order_by(d.verba)
    )
    em_exercicio = await session.scalar(
        select(func.count(func.distinct(Mandato.politico_id))).where(*mandato_em_exercicio())
    )
    return Estatisticas(
        politicos=await _contar(session, Politico),
        politicos_em_exercicio=em_exercicio or 0,
        mandatos=await _contar(session, Mandato),
        candidaturas=await _contar(session, Candidatura),
        candidaturas_eleitas=await _contar(session, Candidatura, Candidatura.eleito.is_(True)),
        despesas=qtd_despesas,
        despesas_sem_politico=await _contar(session, d, d.politico_id.is_(None)),
        despesas_total=total_despesas,
        entes=await _contar(session, Ente),
        partidos=await _contar(session, Partido),
        fotos=await _contar(session, PoliticoFoto),
        matches_pendentes=await _contar(session, MatchPendente, MatchPendente.resolvido.is_(False)),
        em_exercicio_por_cargo=await _em_exercicio_por(session, Mandato.cargo),
        em_exercicio_por_uf=await _em_exercicio_por(session, Mandato.uf),
        em_exercicio_por_partido=await _em_exercicio_por(session, Mandato.partido_sigla),
        despesas_por_verba=[TotalVerba(verba=v, total=t, quantidade=q) for v, t, q in por_verba],
        ultima_ingestao_em=await session.scalar(
            select(func.max(FonteExecucao.finalizado_em)).where(
                FonteExecucao.status == StatusExecucao.SUCESSO
            )
        ),
    )
