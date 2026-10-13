from fastapi import APIRouter
from sqlalchemy import text

from ouroboros.api.deps import Session

router = APIRouter(tags=["infra"])


@router.get("/health", summary="Saúde da API e do banco")
async def health(session: Session) -> dict[str, str]:
    await session.execute(text("select 1"))
    return {"status": "ok", "db": "ok"}
