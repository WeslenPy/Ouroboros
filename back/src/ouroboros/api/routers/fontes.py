from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on

from ouroboros.api.deps import Paging, Session
from ouroboros.api.pagination import Page, encode_cursor
from ouroboros.api.schemas import ExecucaoOut, FonteStatus
from ouroboros.models.fonte import FonteExecucao, StatusExecucao

router = APIRouter(prefix="/fontes", tags=["fontes"])


@router.get(
    "",
    response_model=list[FonteStatus],
    summary="Status da última ingestão de cada fonte/recurso/partição",
)
async def listar_fontes(session: Session) -> list[FonteStatus]:
    chave = (FonteExecucao.fonte, FonteExecucao.recurso, FonteExecucao.particao)
    ultima = (
        select(FonteExecucao)
        .ext(distinct_on(*chave))
        .order_by(*chave, FonteExecucao.iniciado_em.desc())
        .subquery()
    )
    sucesso = (
        select(*chave, func.max(FonteExecucao.finalizado_em).label("ultimo_sucesso_em"))
        .where(FonteExecucao.status == StatusExecucao.SUCESSO)
        .group_by(*chave)
        .subquery()
    )
    stmt = (
        select(ultima, sucesso.c.ultimo_sucesso_em)
        .outerjoin(
            sucesso,
            (ultima.c.fonte == sucesso.c.fonte)
            & (ultima.c.recurso == sucesso.c.recurso)
            & (ultima.c.particao == sucesso.c.particao),
        )
        .order_by(ultima.c.fonte, ultima.c.recurso, ultima.c.particao)
    )
    rows = (await session.execute(stmt)).mappings().all()
    return [FonteStatus.model_validate(dict(r)) for r in rows]


@router.get(
    "/execucoes",
    response_model=Page[ExecucaoOut],
    summary="Histórico de execuções de ingestão (mais recentes primeiro)",
)
async def listar_execucoes(
    session: Session,
    paging: Paging,
    fonte: str | None = None,
    recurso: str | None = None,
    particao: str | None = None,
    status: StatusExecucao | None = None,
) -> Page[ExecucaoOut]:
    e = FonteExecucao
    stmt = select(e).order_by(e.id.desc()).limit(paging.limit + 1)
    if fonte:
        stmt = stmt.where(e.fonte == fonte)
    if recurso:
        stmt = stmt.where(e.recurso == recurso)
    if particao:
        stmt = stmt.where(e.particao == particao)
    if status:
        stmt = stmt.where(e.status == status)
    if paging.after is not None:
        stmt = stmt.where(e.id < int(paging.after))
    rows = list((await session.scalars(stmt)).all())
    has_more = len(rows) > paging.limit
    rows = rows[: paging.limit]
    return Page(
        items=[ExecucaoOut.model_validate(r) for r in rows],
        next_cursor=encode_cursor(rows[-1].id) if has_more else None,
    )
