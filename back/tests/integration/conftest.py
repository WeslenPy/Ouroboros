"""Integração contra Postgres real. Só roda com OUROBOROS_TEST_DATABASE_URL apontando para um
banco descartável: as tabelas são apagadas e recriadas."""

import os
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from ouroboros.core import db, settings

TEST_DB = os.environ.get("OUROBOROS_TEST_DATABASE_URL")
BACK = Path(__file__).resolve().parents[2]

TABELAS = [
    "despesa_gabinete",
    "candidatura",
    "mandato",
    "politico_identificador",
    "match_pendente",
    "politico",
    "partido",
    "ente",
    "fonte_execucao",
]


def pytest_collection_modifyitems(items):
    if TEST_DB:
        return
    skip = pytest.mark.skip(reason="OUROBOROS_TEST_DATABASE_URL não definido")
    for item in items:
        if "integration" in str(item.path):
            item.add_marker(skip)


def _clear_caches() -> None:
    settings.get_settings.cache_clear()
    db.get_engine.cache_clear()
    db.get_sessionmaker.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def banco_migrado():
    if not TEST_DB:
        yield
        return
    mp = pytest.MonkeyPatch()
    mp.setenv("OUROBOROS_DATABASE_URL", TEST_DB)
    _clear_caches()
    cfg = Config(str(BACK / "alembic.ini"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield
    command.downgrade(cfg, "base")
    mp.undo()
    _clear_caches()


@pytest.fixture(autouse=True)
async def banco_limpo():
    """Cada teste começa com o banco vazio e termina com o pool fechado (loop por teste)."""
    async with db.get_engine().begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(TABELAS)} RESTART IDENTITY CASCADE"))
    yield
    await db.get_engine().dispose()


@pytest.fixture
async def api() -> AsyncIterator[httpx.AsyncClient]:
    from ouroboros.api.main import create_app

    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        yield client
