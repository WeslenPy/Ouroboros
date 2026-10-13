import io

import fontes
import httpx
import pytest
import respx
from PIL import Image
from sqlalchemy import select

from ouroboros.core.db import get_sessionmaker
from ouroboros.core.raw_store import RawStore
from ouroboros.core.settings import get_settings
from ouroboros.models import PartidoLogo
from ouroboros.pipelines import logos
from ouroboros.pipelines.loaders import load_candidaturas
from ouroboros.pipelines.logos import (
    coletar_logos_wikidata,
    registrar_logo_manual,
    remover_logo_manual,
)
from ouroboros.pipelines.runner import run_connector

_NORMAL = "http://wikiba.se/ontology#NormalRank"
_PREFERIDA = "http://wikiba.se/ontology#PreferredRank"
EXTERNA = "https://exemplo.org/pdt.png"


def _png(largura: int, cor: str = "blue") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (largura, largura // 2), cor).save(buf, "PNG")
    return buf.getvalue()


def _binding(item, numero, arquivo, *, rank=_NORMAL, extinto=False, siglas=""):
    b = {
        "item": {"value": f"http://www.wikidata.org/entity/{item}"},
        "numero": {"value": str(numero)},
        "logo": {"value": f"http://commons.wikimedia.org/wiki/Special:FilePath/{arquivo}"},
        "rank": {"value": rank},
        "siglas": {"value": siglas},
    }
    if extinto:
        b["extinto"] = {"value": "2020-01-01T00:00:00Z"}
    return b


def _sparql(*bindings) -> dict:
    return {"results": {"bindings": list(bindings)}}


@pytest.fixture
async def partidos(tmp_path, monkeypatch):
    """Fixture do TSE 2022 traz PDT (12), PL (22) e PSB (40)."""
    monkeypatch.setattr(get_settings(), "fotos_dir", tmp_path / "fotos")
    monkeypatch.setattr(logos, "COMMONS_CHAMADAS_POR_MINUTO", 60_000)
    store = RawStore(tmp_path / "raw")
    await run_connector(fontes.tse_candidatos(), load_candidaturas, "2022", store=store)


async def _logos_por_sigla(api: httpx.AsyncClient) -> dict[str, dict | None]:
    return {p["sigla"]: p["logo"] for p in (await api.get("/v1/partidos")).json()}


@respx.mock
async def test_wikidata_baixa_e_manual_tem_prioridade(partidos, tmp_path, api):
    sparql = respx.get(url__startswith=logos.WIKIDATA_SPARQL).respond(
        json=_sparql(
            _binding("Q1414708", 12, "PDT%20logo.png", siglas="PDT"),
            _binding("Q2731720", 22, "PL%20a.svg", siglas="PL"),
            _binding("Q2731720", 22, "PL%20b.svg", rank=_PREFERIDA, siglas="PL"),
            # 40 reaproveitado de partido extinto com outra sigla: PSB fica sem logo
            _binding("Q999", 40, "Antigo.png", extinto=True, siglas="PXX"),
        )
    )
    commons = respx.get(url__startswith="https://commons.wikimedia.org/wiki/Special:FilePath/")
    commons.respond(200, content=_png(512), headers={"Content-Type": "image/png"})

    assert await coletar_logos_wikidata() == 2
    baixados = {str(c.request.url) for c in commons.calls}
    assert any("PL%20b.svg?width=512" in u for u in baixados)  # rank preferido
    assert not any("PL%20a.svg" in u for u in baixados)

    por_sigla = await _logos_por_sigla(api)
    assert por_sigla["PSB"] is None
    pdt = por_sigla["PDT"]
    assert pdt["origem"] == "wikidata"
    assert pdt["largura"] == 512
    assert pdt["url_origem"] == "https://commons.wikimedia.org/wiki/File:PDT_logo.png"
    assert pdt["url"] == f"/v1/partidos/logos/{pdt['id']}"

    arquivo = await api.get(pdt["url"])
    assert arquivo.status_code == 200
    assert arquivo.headers["content-type"] == "image/png"
    cache = await api.get(pdt["url"], headers={"If-None-Match": arquivo.headers["etag"]})
    assert cache.status_code == 304
    detalhe = (await api.get("/v1/partidos/pdt")).json()
    assert detalhe["logo"] == pdt

    # segunda coleta: mesmos arquivos do Commons -> nada baixado de novo
    chamadas = commons.call_count
    assert await coletar_logos_wikidata() == 0
    assert commons.call_count == chamadas

    # manual por arquivo vence a coletada; por URL sem baixar redireciona para a origem
    local = tmp_path / "psb.png"
    local.write_bytes(_png(300, "red"))
    await registrar_logo_manual("PSB", arquivo=local)
    respx.get(EXTERNA).respond(200, content=_png(200, "green"))
    await registrar_logo_manual("12", url=EXTERNA, baixar=False)

    por_sigla = await _logos_por_sigla(api)
    assert por_sigla["PSB"]["origem"] == "manual"
    assert por_sigla["PSB"]["largura"] == 300
    assert por_sigla["PSB"]["url_origem"] == "arquivo:psb.png"
    assert por_sigla["PDT"]["origem"] == "manual"
    assert por_sigla["PDT"]["url"] == EXTERNA
    redirect = await api.get("/v1/partidos/PDT/logo")
    assert redirect.status_code == 307
    assert redirect.headers["location"] == EXTERNA

    assert await remover_logo_manual("PDT")
    assert (await _logos_por_sigla(api))["PDT"]["origem"] == "wikidata"

    # PL sumiu do Wikidata: logo coletada é apagada; manual do PSB não é tocada
    sparql.respond(json=_sparql(_binding("Q1414708", 12, "PDT%20logo.png", siglas="PDT")))
    await coletar_logos_wikidata()
    por_sigla = await _logos_por_sigla(api)
    assert por_sigla["PL"] is None
    assert por_sigla["PSB"]["origem"] == "manual"
    assert (await api.get("/v1/partidos/PL/logo")).status_code == 404
    async with get_sessionmaker()() as s:
        origens = {(lg.partido_id, lg.origem) for lg in await s.scalars(select(PartidoLogo))}
    assert len(origens) == 2


async def test_manual_rejeita_imagem_invalida(partidos, tmp_path):
    local = tmp_path / "logo.png"
    local.write_bytes(b"nao e imagem")
    with pytest.raises(ValueError):
        await registrar_logo_manual("PL", arquivo=local)
    with pytest.raises(ValueError):
        await registrar_logo_manual("PL", url="file:///etc/passwd")
    local.write_bytes(_png(100))
    with pytest.raises(logos.PartidoNaoEncontrado):
        await registrar_logo_manual("XYZ", arquivo=local)
