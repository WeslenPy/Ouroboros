from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import exists, func, or_, select
from sqlalchemy.dialects.postgresql import distinct_on

from ouroboros.api.deps import Paging, Session
from ouroboros.api.export import page_or_csv
from ouroboros.api.pagination import Page, encode_cursor
from ouroboros.api.queries import FiltroDespesa, resumo_despesas
from ouroboros.api.schemas import (
    CandidaturaOut,
    DespesaOut,
    FotoOut,
    Identificador,
    MandatoOut,
    PoliticoDetalhe,
    PoliticoResumo,
    ResumoDespesas,
    TotalAno,
)
from ouroboros.core.text import normalize
from ouroboros.models.despesa import DespesaGabinete
from ouroboros.models.ente import Esfera
from ouroboros.models.foto import PoliticoFoto
from ouroboros.models.mandato import Candidatura, Cargo, Mandato
from ouroboros.models.politico import Politico, PoliticoIdentificador

router = APIRouter(prefix="/politicos", tags=["políticos"])


async def _ultimos_mandatos(session: Session, ids: list[int]) -> dict[int, MandatoOut]:
    if not ids:
        return {}
    rows = await session.scalars(
        select(Mandato)
        .ext(distinct_on(Mandato.politico_id))
        .where(Mandato.politico_id.in_(ids))
        .order_by(Mandato.politico_id, Mandato.inicio.desc().nulls_last())
    )
    return {m.politico_id: MandatoOut.model_validate(m) for m in rows}


async def _fotos(session: Session, foto_ids: list[int | None]) -> dict[int, FotoOut]:
    ids = [i for i in foto_ids if i is not None]
    if not ids:
        return {}
    rows = await session.scalars(select(PoliticoFoto).where(PoliticoFoto.id.in_(ids)))
    return {f.id: FotoOut.de(f) for f in rows}


async def _politico_ou_404(session: Session, politico_id: int) -> Politico:
    politico = await session.get(Politico, politico_id)
    if politico is None:
        raise HTTPException(status_code=404, detail="político não encontrado")
    return politico


@router.get("", response_model=Page[PoliticoResumo], summary="Busca políticos")
async def listar_politicos(
    request: Request,
    session: Session,
    paging: Paging,
    busca: str | None = Query(
        None, min_length=3, description="Trecho do nome (parlamentar ou civil)"
    ),
    cargo: Cargo | None = Query(None, description="Teve mandato neste cargo"),
    esfera: Esfera | None = Query(None, description="Teve mandato nesta esfera"),
    uf: str | None = Query(None, min_length=2, max_length=2, description="UF de algum mandato"),
    partido: str | None = Query(None, description="Sigla em algum mandato"),
    em_exercicio: bool | None = Query(
        None, description="true: só quem tem mandato em curso hoje (false = sem filtro)"
    ),
    com_mandato: bool | None = Query(
        None, description="Só quem exerceu mandato (exclui quem só foi candidato)"
    ),
):
    stmt = select(Politico).order_by(Politico.id).limit(paging.limit + 1)
    if busca:
        termo = normalize(busca)
        stmt = stmt.where(
            or_(
                Politico.nome_normalizado.contains(termo, autoescape=True),
                Politico.nome_civil_normalizado.contains(termo, autoescape=True),
            )
        )
    filtros_mandato = []
    if cargo:
        filtros_mandato.append(Mandato.cargo == cargo)
    if esfera:
        filtros_mandato.append(Mandato.esfera == esfera)
    if uf:
        filtros_mandato.append(Mandato.uf == uf.upper())
    if partido:
        filtros_mandato.append(Mandato.partidos.any(partido.upper()))
    if em_exercicio:
        hoje = date.today()
        filtros_mandato += [Mandato.inicio <= hoje, or_(Mandato.fim.is_(None), Mandato.fim >= hoje)]
    if filtros_mandato or com_mandato:
        stmt = stmt.where(exists().where(Mandato.politico_id == Politico.id, *filtros_mandato))
    if paging.after is not None:
        stmt = stmt.where(Politico.id > int(paging.after))

    rows = list((await session.scalars(stmt)).all())
    has_more = len(rows) > paging.limit
    rows = rows[: paging.limit]
    ultimos = await _ultimos_mandatos(session, [p.id for p in rows])
    fotos = await _fotos(session, [p.foto_id for p in rows])
    page = Page(
        items=[
            PoliticoResumo.model_validate(p).model_copy(
                update={"ultimo_mandato": ultimos.get(p.id), "foto": fotos.get(p.foto_id)}
            )
            for p in rows
        ],
        next_cursor=encode_cursor(rows[-1].id) if has_more else None,
    )
    return page_or_csv(request, page, "politicos")


@router.get("/{politico_id}", response_model=PoliticoDetalhe, summary="Perfil de um político")
async def obter_politico(politico_id: int, session: Session) -> PoliticoDetalhe:
    politico = await _politico_ou_404(session, politico_id)
    identificadores = await session.scalars(
        select(PoliticoIdentificador)
        .where(PoliticoIdentificador.politico_id == politico_id)
        .order_by(PoliticoIdentificador.origem, PoliticoIdentificador.id_externo)
    )
    mandatos = [
        MandatoOut.model_validate(m)
        for m in await session.scalars(
            select(Mandato)
            .where(Mandato.politico_id == politico_id)
            .order_by(Mandato.inicio.desc().nulls_last())
        )
    ]
    candidaturas = await session.scalar(
        select(func.count()).where(Candidatura.politico_id == politico_id)
    )
    d = DespesaGabinete
    por_ano = await session.execute(
        select(d.ano, func.sum(d.valor_liquido), func.count())
        .where(d.politico_id == politico_id)
        .group_by(d.ano)
        .order_by(d.ano)
    )
    fotos = await _fotos(session, [politico.foto_id])
    return PoliticoDetalhe(
        **PoliticoResumo.model_validate(politico).model_dump(exclude={"ultimo_mandato", "foto"}),
        foto=fotos.get(politico.foto_id),
        ultimo_mandato=mandatos[0] if mandatos else None,
        data_nascimento=politico.data_nascimento,
        genero=politico.genero,
        identificadores=[Identificador.model_validate(i) for i in identificadores],
        mandatos=mandatos,
        candidaturas=candidaturas or 0,
        gastos_gabinete_por_ano=[TotalAno(ano=a, total=t, quantidade=q) for a, t, q in por_ano],
    )


@router.get(
    "/{politico_id}/foto",
    summary="Foto principal (redireciona para /v1/fotos/{id})",
    response_class=RedirectResponse,
    responses={307: {"description": "Redireciona para o arquivo"}, 404: {}},
)
async def foto_principal(politico_id: int, session: Session) -> RedirectResponse:
    politico = await _politico_ou_404(session, politico_id)
    if politico.foto_id is None:
        raise HTTPException(status_code=404, detail="político sem foto")
    return RedirectResponse(f"/v1/fotos/{politico.foto_id}", status_code=307)


@router.get(
    "/{politico_id}/fotos",
    response_model=list[FotoOut],
    summary="Todas as fotos coletadas (casa legislativa, uma por eleição no TSE)",
)
async def listar_fotos(politico_id: int, session: Session) -> list[FotoOut]:
    await _politico_ou_404(session, politico_id)
    rows = await session.scalars(
        select(PoliticoFoto)
        .where(PoliticoFoto.politico_id == politico_id)
        .order_by(PoliticoFoto.ano.desc().nulls_last(), PoliticoFoto.id)
    )
    return [FotoOut.de(f) for f in rows]


@router.get("/{politico_id}/mandatos", response_model=list[MandatoOut], summary="Mandatos")
async def listar_mandatos(politico_id: int, session: Session) -> list[MandatoOut]:
    await _politico_ou_404(session, politico_id)
    rows = await session.scalars(
        select(Mandato)
        .where(Mandato.politico_id == politico_id)
        .order_by(Mandato.inicio.desc().nulls_last())
    )
    return [MandatoOut.model_validate(m) for m in rows]


@router.get(
    "/{politico_id}/candidaturas", response_model=list[CandidaturaOut], summary="Candidaturas (TSE)"
)
async def listar_candidaturas(politico_id: int, session: Session) -> list[CandidaturaOut]:
    await _politico_ou_404(session, politico_id)
    rows = await session.scalars(
        select(Candidatura)
        .where(Candidatura.politico_id == politico_id)
        .order_by(Candidatura.ano.desc())
    )
    return [CandidaturaOut.model_validate(c) for c in rows]


@router.get(
    "/{politico_id}/despesas",
    response_model=Page[DespesaOut],
    summary="Gastos de gabinete (cota parlamentar) do político",
)
async def listar_despesas_politico(
    politico_id: int,
    request: Request,
    session: Session,
    paging: Paging,
    filtro: Annotated[FiltroDespesa, Depends()],
):
    await _politico_ou_404(session, politico_id)
    stmt = filtro.aplicar(select(DespesaGabinete), politico_id)
    stmt = stmt.order_by(DespesaGabinete.id).limit(paging.limit + 1)
    if paging.after is not None:
        stmt = stmt.where(DespesaGabinete.id > int(paging.after))
    rows = list((await session.scalars(stmt)).all())
    has_more = len(rows) > paging.limit
    rows = rows[: paging.limit]
    page = Page(
        items=[DespesaOut.model_validate(r) for r in rows],
        next_cursor=encode_cursor(rows[-1].id) if has_more else None,
    )
    return page_or_csv(request, page, f"despesas_politico_{politico_id}")


@router.get(
    "/{politico_id}/despesas/resumo",
    response_model=ResumoDespesas,
    summary="Totais de gastos de gabinete por ano, categoria e fornecedor",
)
async def resumo_despesas_politico(
    politico_id: int, session: Session, filtro: Annotated[FiltroDespesa, Depends()]
) -> ResumoDespesas:
    await _politico_ou_404(session, politico_id)
    return await resumo_despesas(session, filtro, politico_id)
