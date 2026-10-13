"""Export CSV: qualquer listagem paginada responde CSV quando o cliente pede `Accept: text/csv`.

O cursor da próxima página vai no header `X-Next-Cursor`.
"""

import csv
import io

from fastapi import Request
from fastapi.responses import Response

from ouroboros.api.pagination import Page


def wants_csv(request: Request) -> bool:
    return "text/csv" in request.headers.get("accept", "")


def page_or_csv(request: Request, page: Page, filename: str) -> Page | Response:
    if not wants_csv(request):
        return page
    buf = io.StringIO()
    rows = [item.model_dump(mode="json") for item in page.items]
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0]), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    headers = {"Content-Disposition": f'attachment; filename="{filename}.csv"'}
    if page.next_cursor:
        headers["X-Next-Cursor"] = page.next_cursor
    # BOM: Excel abre UTF-8 com acentos corretos
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8", headers=headers)
