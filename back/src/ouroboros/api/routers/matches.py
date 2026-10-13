from fastapi import APIRouter, Query
from sqlalchemy import select

from ouroboros.api.deps import Paging, Session
from ouroboros.api.pagination import Page, encode_cursor
from ouroboros.api.schemas import MatchPendenteOut
from ouroboros.models.politico import MatchPendente

router = APIRouter(prefix="/matches-pendentes", tags=["qualidade"])


@router.get(
    "",
    response_model=Page[MatchPendenteOut],
    summary="Ligações entre fontes que a resolução automática não decidiu",
)
async def listar_matches(
    session: Session,
    paging: Paging,
    resolvido: bool | None = Query(None, description="Omitido: todos"),
    origem: str | None = None,
    motivo: str | None = None,
) -> Page[MatchPendenteOut]:
    m = MatchPendente
    stmt = select(m).order_by(m.id).limit(paging.limit + 1)
    if resolvido is not None:
        stmt = stmt.where(m.resolvido.is_(resolvido))
    if origem:
        stmt = stmt.where(m.origem == origem)
    if motivo:
        stmt = stmt.where(m.motivo == motivo)
    if paging.after is not None:
        stmt = stmt.where(m.id > int(paging.after))
    rows = list((await session.scalars(stmt)).all())
    has_more = len(rows) > paging.limit
    rows = rows[: paging.limit]
    return Page(
        items=[MatchPendenteOut.model_validate(r) for r in rows],
        next_cursor=encode_cursor(rows[-1].id) if has_more else None,
    )
