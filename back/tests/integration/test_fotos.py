import io
import re
import zipfile

import fontes
import httpx
import pytest
import respx
from PIL import Image
from sqlalchemy import select

from ouroboros.core.db import get_sessionmaker
from ouroboros.core.raw_store import RawStore
from ouroboros.core.settings import get_settings
from ouroboros.models import Candidatura, PoliticoFoto
from ouroboros.pipelines import fotos
from ouroboros.pipelines.fotos import coletar_fotos_casa, coletar_fotos_tse
from ouroboros.pipelines.loaders import load_candidaturas, load_entes, load_parlamentares
from ouroboros.pipelines.runner import run_connector

TSE_ZIP = re.compile(r"https://cdn\.tse\.jus\.br/.*/foto_cand2022_(?P<uf>[A-Z]{2})_div\.zip")


def _jpeg(cor: str) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (161, 225), cor).save(buf, "JPEG")
    return buf.getvalue()


async def _sq_por_nome() -> dict[str, tuple[str, str]]:
    async with get_sessionmaker()() as s:
        rows = await s.execute(
            select(Candidatura.nome_urna, Candidatura.sq_candidato, Candidatura.uf)
        )
        return {nome: (str(sq), uf) for nome, sq, uf in rows}


@pytest.fixture
async def carregado(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "fotos_dir", tmp_path / "fotos")
    monkeypatch.setattr(fotos, "TSE_CHAMADAS_POR_MINUTO", 60_000)
    store = RawStore(tmp_path / "raw")
    await run_connector(fontes.ibge(), load_entes, "atual", store=store)
    await run_connector(fontes.tse_candidatos(), load_candidaturas, "2022", store=store)
    await run_connector(fontes.camara_deputados(), load_parlamentares, "57", store=store)
    await run_connector(fontes.senado_senadores(), load_parlamentares, "57", store=store)


@respx.mock
async def test_casas_so_url_e_tse_baixado(carregado, api: httpx.AsyncClient):
    jpeg = {"Content-Type": "image/jpeg"}
    respx.head("https://www.camara.leg.br/internet/deputado/bandep/204534.jpg").respond(
        200, headers=jpeg
    )
    respx.head("https://www.camara.leg.br/internet/deputado/bandep/209787.jpg").respond(
        200, headers=jpeg
    )
    # Délio sem foto na Câmara: deve cair para a foto do TSE
    respx.head("https://www.camara.leg.br/internet/deputado/bandep/228272.jpg").respond(404)
    respx.head("https://www.senado.leg.br/senadores/img/fotos-oficiais/senador5411.jpg").respond(
        200, headers=jpeg
    )

    sqs = await _sq_por_nome()
    zips: dict[str, bytes] = {}
    for sq, uf in sqs.values():
        buf = io.BytesIO(zips.get(uf, b""))
        with zipfile.ZipFile(buf, "a" if uf in zips else "w") as zf:
            zf.writestr(f"F{uf}{sq}_div.jpg", _jpeg("red"))
        zips[uf] = buf.getvalue()

    def tse(request: httpx.Request, uf: str) -> httpx.Response:
        if uf not in zips:
            return httpx.Response(404)
        if request.headers.get("if-none-match") == f'"{uf}"':
            return httpx.Response(304)
        return httpx.Response(200, content=zips[uf], headers={"ETag": f'"{uf}"'})

    rota_tse = respx.get(url__regex=TSE_ZIP).mock(side_effect=tse)

    assert await coletar_fotos_casa("camara") == 2
    assert await coletar_fotos_casa("senado") == 1
    assert await coletar_fotos_tse("2022") == len(sqs)

    async with get_sessionmaker()() as s:
        fotos = (await s.scalars(select(PoliticoFoto))).all()
    casas = [f for f in fotos if f.origem in ("camara", "senado")]
    assert casas and all(f.sha256 is None for f in casas)  # casas: só URL
    assert all(f.sha256 and f.largura == 161 for f in fotos if f.origem == "tse")

    tabata = (await api.get("/v1/politicos", params={"busca": "tabata"})).json()["items"][0]
    assert tabata["foto"]["origem"] == "camara"  # mandato atual vence foto de 2022
    assert tabata["foto"]["url"] == (
        "https://www.camara.leg.br/internet/deputado/bandep/204534.jpg"
    )
    redirect = await api.get(f"/v1/politicos/{tabata['id']}/foto")
    assert redirect.status_code == 307
    assert redirect.headers["location"] == tabata["foto"]["url"]

    delio = (await api.get("/v1/politicos", params={"busca": "delio"})).json()["items"][0]
    assert delio["foto"]["origem"] == "tse"
    arquivo = await api.get(delio["foto"]["url"])
    assert arquivo.status_code == 200
    assert arquivo.headers["content-type"] == "image/jpeg"
    assert arquivo.content[:2] == b"\xff\xd8"
    cache = await api.get(delio["foto"]["url"], headers={"If-None-Match": arquivo.headers["etag"]})
    assert cache.status_code == 304

    todas = (await api.get(f"/v1/politicos/{tabata['id']}/fotos")).json()
    assert {f["origem"] for f in todas} == {"camara", "tse"}

    # segunda coleta: ZIPs não mudaram (ETag) -> nada baixado de novo
    chamadas = rota_tse.call_count
    assert await coletar_fotos_tse("2022") == 0
    assert rota_tse.call_count == chamadas + len(get_settings().tse_fotos_ufs)
