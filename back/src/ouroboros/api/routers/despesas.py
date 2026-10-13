from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from ouroboros.api.deps import Paging, Session
from ouroboros.api.export import page_or_csv
from ouroboros.api.pagination import Page, encode_cursor
from ouroboros.api.queries import FiltroDespesa, resumo_despesas
from ouroboros.api.schemas import DespesaOut, ResumoDespesas
from ouroboros.models.despesa import DespesaGabinete

router = APIRouter(prefix="/despesas", tags=["despesas"])


@router.get(
    "",
    response_model=Page[DespesaOut],
    summary="Gastos de gabinete de todos os parlamentares (CEAP, CEAPS)",
)
async def listar_despesas(
    request: Request,
    session: Session,
    paging: Paging,
    filtro: Annotated[FiltroDespesa, Depends()],
):
    stmt = filtro.aplicar(select(DespesaGabinete))
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
    return page_or_csv(request, page, "despesas")


@router.get(
    "/resumo",
    response_model=ResumoDespesas,
    summary="Totais por ano, categoria e maiores fornecedores",
)
async def resumo(session: Session, filtro: Annotated[FiltroDespesa, Depends()]) -> ResumoDespesas:
    return await resumo_despesas(session, filtro)
