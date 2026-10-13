from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import any_, func, select

from ouroboros.api.deps import Session
from ouroboros.api.queries import mandato_em_exercicio
from ouroboros.api.schemas import Origem, PartidoDetalhe, PartidoOut
from ouroboros.models import Candidatura, DespesaGabinete, Mandato, Partido

router = APIRouter(prefix="/partidos", tags=["partidos"])


@router.get("", response_model=list[PartidoOut], summary="Partidos (registro TSE)")
async def listar_partidos(
    session: Session,
    ativo: bool | None = Query(None, description="Filtra por partido ativo/extinto"),
) -> list[PartidoOut]:
    stmt = select(Partido).order_by(Partido.sigla)
    if ativo is not None:
        stmt = stmt.where(Partido.ativo.is_(ativo))
    return [PartidoOut.model_validate(p) for p in await session.scalars(stmt)]


@router.get("/{sigla}", response_model=PartidoDetalhe, summary="Partido com totais agregados")
async def obter_partido(sigla: str, session: Session) -> PartidoDetalhe:
    sigla = sigla.upper()
    partido = await session.scalar(
        select(Partido).where(Partido.sigla == sigla).order_by(Partido.ativo.desc()).limit(1)
    )
    if partido is None:
        raise HTTPException(status_code=404, detail="partido não encontrado")
    em_exercicio = await session.scalar(
        select(func.count(func.distinct(Mandato.politico_id))).where(
            Mandato.partido_sigla == sigla, *mandato_em_exercicio()
        )
    )
    mandatos = await session.scalar(select(func.count()).where(sigla == any_(Mandato.partidos)))
    candidaturas, eleitas = (
        await session.execute(
            select(func.count(), func.count().filter(Candidatura.eleito.is_(True))).where(
                Candidatura.partido_sigla == sigla
            )
        )
    ).one()
    d = DespesaGabinete
    total, qtd = (
        await session.execute(
            select(func.coalesce(func.sum(d.valor_liquido), 0), func.count()).where(
                d.partido_sigla == sigla
            )
        )
    ).one()
    return PartidoDetalhe(
        **PartidoOut.model_validate(partido).model_dump(),
        politicos_em_exercicio=em_exercicio or 0,
        mandatos=mandatos or 0,
        candidaturas=candidaturas,
        candidaturas_eleitas=eleitas,
        despesas_total=total,
        despesas_quantidade=qtd,
        origem=Origem.model_validate(partido),
    )
