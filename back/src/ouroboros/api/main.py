from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from ouroboros import __version__
from ouroboros.api.routers import (
    candidaturas,
    despesas,
    entes,
    fontes,
    fotos,
    health,
    matches,
    partidos,
    politicos,
    stats,
)
from ouroboros.core.db import get_engine
from ouroboros.core.logging import setup_logging
from ouroboros.core.settings import get_settings

DESCRIPTION = """
API unificada de dados públicos da política brasileira: mandatos, gastos de gabinete,
emendas, campanhas, patrimônio e atuação legislativa, ligados a cada político.

Todo registro traz a origem (`fonte`, `fonte_url`, `raw_hash`) para conferência na fonte oficial.
Os dados refletem o que os órgãos publicam e podem conter erros ou atrasos da própria fonte.
"""


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    yield
    await get_engine().dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Ouroboros",
        version=__version__,
        description=DESCRIPTION,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().api_cors_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
        expose_headers=["X-Next-Cursor", "Content-Disposition"],
    )
    app.include_router(health.router)
    for module in (stats, politicos, despesas, candidaturas, partidos, fotos, entes, fontes, matches):
        app.include_router(module.router, prefix="/v1")

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse("/docs")

    return app


app = create_app()
