"""Leitura e limpeza de arquivos tabulares das fontes (CSV solto ou dentro de ZIP)."""

import csv
import io
import zipfile
from collections.abc import Iterator
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

# marcadores de "sem valor" usados pelas fontes (TSE usa vários)
NULOS = {"", "#NULO", "#NULO#", "#NE", "#NE#", "NÃO DIVULGÁVEL", "-1", "-3", "-4", "NA", "null"}


def clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return None if value in NULOS else value


def read_csv(
    data: bytes, *, encoding: str = "utf-8-sig", delimiter: str = ";", skip_lines: int = 0
) -> Iterator[dict[str, str]]:
    text = io.TextIOWrapper(io.BytesIO(data), encoding=encoding, newline="")
    for _ in range(skip_lines):
        text.readline()
    yield from csv.DictReader(text, delimiter=delimiter)


def zip_members(data: bytes, suffix: str = ".csv") -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return {n: zf.read(n) for n in zf.namelist() if n.lower().endswith(suffix)}


def parse_date(value: str | None, fmt: str = "%Y-%m-%d") -> date | None:
    """Datas das fontes têm 10 caracteres úteis ('2024-02-07T00:00:00', '17/01/2024')."""
    value = (value or "").strip()[:10]
    if not value:
        return None
    try:
        return datetime.strptime(value, fmt).date()
    except ValueError:
        return None


def parse_decimal(value: str | None) -> Decimal | None:
    """Aceita '1148.7' (Câmara) e '1.234,56' (Senado). Não usa `clean`: '-1' é valor válido."""
    value = (value or "").strip()
    if not value:
        return None
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def parse_int(value: str | None) -> int | None:
    value = clean(value)
    try:
        return int(value) if value else None
    except ValueError:
        return None
