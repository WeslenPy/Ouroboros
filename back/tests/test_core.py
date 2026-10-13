import os
import time

import httpx
import pytest
import respx

from ouroboros.core.http import HttpClient, RateLimiter
from ouroboros.core.raw_store import RawRecord, RawStore
from ouroboros.core.text import normalize


def test_normalize():
    assert normalize("  São   João D'Aliança ") == "sao joao d'alianca"


@respx.mock
async def test_http_retry_em_503_depois_sucesso():
    route = respx.get("https://fonte.test/x").mock(
        side_effect=[httpx.Response(503), httpx.Response(429), httpx.Response(200, json={"ok": 1})]
    )
    async with HttpClient(attempts=3, backoff_initial=0.01) as client:
        response = await client.get("https://fonte.test/x")
    assert response.json() == {"ok": 1}
    assert route.call_count == 3


@respx.mock
async def test_http_desiste_apos_tentativas():
    respx.get("https://fonte.test/x").respond(500)
    async with HttpClient(attempts=2, backoff_initial=0.01) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await client.get("https://fonte.test/x")


@respx.mock
async def test_http_nao_repete_404():
    route = respx.get("https://fonte.test/x").respond(404)
    async with HttpClient(attempts=5, backoff_initial=0.01) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await client.get("https://fonte.test/x")
    assert route.call_count == 1


async def test_rate_limiter_espaca_chamadas():
    limiter = RateLimiter(max_calls=600, period=60)  # 1 a cada 0,1s
    start = time.monotonic()
    for _ in range(4):
        await limiter.acquire()
    assert time.monotonic() - start >= 0.29


def test_raw_store_idempotente(tmp_path):
    store = RawStore(tmp_path)
    record = RawRecord(fonte="f", recurso="r", particao="2024", url="u", payload=b"[1]")
    p1 = store.save(record)
    p2 = store.save(record)
    assert p1 == p2 == tmp_path / "f" / "r" / "2024" / f"{record.sha256}.json"
    assert p1.read_bytes() == b"[1]"


def test_raw_store_mesmo_arquivo_em_outra_particao_vira_hardlink(tmp_path):
    store = RawStore(tmp_path)
    a = store.save(RawRecord("f", "r", "2023", "u", b"zip"))
    b = store.save(RawRecord("f", "r", "2024", "u", b"zip"))
    assert a != b
    assert b.read_bytes() == b"zip"
    assert os.path.samefile(a, b)
