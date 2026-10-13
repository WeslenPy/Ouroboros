from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on

from ouroboros.api.deps import Session
from ouroboros.api.schemas import FonteStatus
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
