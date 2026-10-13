from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from ouroboros.api.deps import Paging, Session
from ouroboros.api.pagination import Page, encode_cursor
from ouroboros.api.schemas import EnteDetalhe, EnteOut, Origem
from ouroboros.core.text import normalize
from ouroboros.models.ente import Ente, Esfera

router = APIRouter(prefix="/entes", tags=["entes"])


@router.get("", response_model=Page[EnteOut], summary="Lista entes federativos")
async def listar_entes(
    session: Session,
    paging: Paging,
    busca: str | None = Query(None, min_length=2, description="Parte do nome, sem acento."),
    esfera: Esfera | None = None,
    uf: str | None = Query(None, min_length=2, max_length=2),
) -> Page[EnteOut]:
    stmt = select(Ente).order_by(Ente.codigo_ibge).limit(paging.limit + 1)
    if busca:
        stmt = stmt.where(Ente.nome_normalizado.contains(normalize(busca), autoescape=True))
    if esfera:
        stmt = stmt.where(Ente.esfera == esfera)
    if uf:
        stmt = stmt.where(Ente.uf == uf.upper())
    if paging.after is not None:
        stmt = stmt.where(Ente.codigo_ibge > int(paging.after))

    rows = list((await session.scalars(stmt)).all())
    has_more = len(rows) > paging.limit
    rows = rows[: paging.limit]
    return Page(
        items=[EnteOut.model_validate(r) for r in rows],
        next_cursor=encode_cursor(rows[-1].codigo_ibge) if has_more else None,
    )


@router.get("/{codigo_ibge}", response_model=EnteDetalhe, summary="Detalhe de um ente")
async def obter_ente(codigo_ibge: int, session: Session) -> EnteDetalhe:
    ente = await session.get(Ente, codigo_ibge)
    if ente is None:
        raise HTTPException(status_code=404, detail="ente não encontrado")
    return EnteDetalhe(
        **EnteOut.model_validate(ente).model_dump(),
        uf_codigo=ente.uf_codigo,
        origem=Origem.model_validate(ente),
    )
