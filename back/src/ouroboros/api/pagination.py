"""Paginação por cursor (keyset). Cursor é opaco para o cliente: base64 de JSON."""

import base64
import json
from typing import Any, Generic, TypeVar

from fastapi import HTTPException, Query
from pydantic import BaseModel

from ouroboros.core.settings import get_settings

T = TypeVar("T")


class Page(BaseModel, Generic[T]):  # noqa: UP046 - mantém compatível com Python 3.11
    items: list[T]
    next_cursor: str | None = None


class PageParams(BaseModel):
    limit: int
    after: Any | None


def encode_cursor(key: Any) -> str:
    return base64.urlsafe_b64encode(json.dumps({"k": key}).encode()).decode()


def decode_cursor(cursor: str) -> Any:
    try:
        return json.loads(base64.urlsafe_b64decode(cursor.encode()))["k"]
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="cursor inválido") from exc


def page_params(
    limit: int = Query(100, ge=1, description="Itens por página."),
    cursor: str | None = Query(None, description="Valor de `next_cursor` da página anterior."),
) -> PageParams:
    return PageParams(
        limit=min(limit, get_settings().api_page_max),
        after=decode_cursor(cursor) if cursor else None,
    )
