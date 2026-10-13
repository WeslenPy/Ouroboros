from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy import any_, func, select

from ouroboros.api.deps import Session
from ouroboros.api.queries import mandato_em_exercicio
from ouroboros.api.routers.fotos import servir_imagem
from ouroboros.api.schemas import LogoOut, Origem, PartidoDetalhe, PartidoOut
from ouroboros.models import Candidatura, DespesaGabinete, Mandato, Partido, PartidoLogo

router = APIRouter(prefix="/partidos", tags=["partidos"])


async def _com_logo(session: Session, partidos: Sequence[Partido]) -> list[PartidoOut]:
    ids = [p.logo_id for p in partidos if p.logo_id is not None]
    logos = (
        {
            lg.id: LogoOut.de(lg)
            for lg in await session.scalars(select(PartidoLogo).where(PartidoLogo.id.in_(ids)))
        }
        if ids
        else {}
    )
    return [
        PartidoOut.model_validate(p).model_copy(update={"logo": logos.get(p.logo_id)})
        for p in partidos
    ]


async def _por_sigla(session: Session, sigla: str) -> Partido:
    partido = await session.scalar(
        select(Partido)
        .where(Partido.sigla == sigla.upper())
        .order_by(Partido.ativo.desc())
        .limit(1)
    )
    if partido is None:
        raise HTTPException(status_code=404, detail="partido não encontrado")
    return partido


@router.get("", response_model=list[PartidoOut], summary="Partidos (registro TSE)")
async def listar_partidos(
    session: Session,
    ativo: bool | None = Query(None, description="Filtra por partido ativo/extinto"),
) -> list[PartidoOut]:
    stmt = select(Partido).order_by(Partido.sigla)
    if ativo is not None:
        stmt = stmt.where(Partido.ativo.is_(ativo))
    return await _com_logo(session, (await session.scalars(stmt)).all())


@router.get(
    "/logos/{logo_id}",
    summary="Arquivo da logo (logo manual só com URL redireciona para a origem)",
    response_class=FileResponse,
    responses={200: {"content": {"image/png": {}}}, 304: {}, 307: {}, 404: {}},
)
async def obter_logo(logo_id: int, request: Request, session: Session) -> Response:
    logo = await session.get(PartidoLogo, logo_id)
    if logo is None:
        raise HTTPException(status_code=404, detail="logo não encontrada")
    return servir_imagem(logo, request)


@router.get("/{sigla}", response_model=PartidoDetalhe, summary="Partido com totais agregados")
async def obter_partido(sigla: str, session: Session) -> PartidoDetalhe:
    partido = await _por_sigla(session, sigla)
    sigla = partido.sigla
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
    (base,) = await _com_logo(session, [partido])
    return PartidoDetalhe(
        **base.model_dump(),
        politicos_em_exercicio=em_exercicio or 0,
        mandatos=mandatos or 0,
        candidaturas=candidaturas,
        candidaturas_eleitas=eleitas,
        despesas_total=total,
        despesas_quantidade=qtd,
        origem=Origem.model_validate(partido),
    )


@router.get(
    "/{sigla}/logo",
    summary="Logo principal (redireciona para a URL da logo)",
    response_class=RedirectResponse,
    responses={307: {}, 404: {}},
)
async def logo_principal(sigla: str, session: Session) -> RedirectResponse:
    partido = await _por_sigla(session, sigla)
    logo = await session.get(PartidoLogo, partido.logo_id) if partido.logo_id else None
    if logo is None:
        raise HTTPException(status_code=404, detail="partido sem logo")
    return RedirectResponse(LogoOut.de(logo).url, status_code=307)
