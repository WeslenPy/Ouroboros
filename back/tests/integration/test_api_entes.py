import fontes
import httpx

from ouroboros.core.raw_store import RawStore
from ouroboros.pipelines.loaders import load_entes
from ouroboros.pipelines.runner import run_connector


async def test_entes_e_fontes(api: httpx.AsyncClient, tmp_path):
    store = RawStore(tmp_path)
    await run_connector(fontes.ibge(), load_entes, "atual", store=store)
    await run_connector(fontes.ibge(), load_entes, "atual", store=store)  # upsert idempotente

    assert (await api.get("/health")).json() == {"status": "ok", "db": "ok"}

    todos = (await api.get("/v1/entes", params={"limit": 2})).json()
    assert [e["codigo_ibge"] for e in todos["items"]] == [1, 11]
    resto = (await api.get("/v1/entes", params={"cursor": todos["next_cursor"]})).json()
    assert [e["codigo_ibge"] for e in resto["items"]] == [51, 1100015, 5101837]
    assert resto["next_cursor"] is None

    busca = (await api.get("/v1/entes", params={"busca": "esperança"})).json()
    assert [e["nome"] for e in busca["items"]] == ["Boa Esperança do Norte"]

    mt = (await api.get("/v1/entes", params={"uf": "mt", "esfera": "municipal"})).json()
    assert [e["codigo_ibge"] for e in mt["items"]] == [5101837]

    detalhe = (await api.get("/v1/entes/5101837")).json()
    assert detalhe["origem"]["fonte"] == "ibge"
    assert (await api.get("/v1/entes/999")).status_code == 404

    fontes_status = (await api.get("/v1/fontes")).json()
    assert [(f["recurso"], f["status"], f["registros"]) for f in fontes_status] == [
        ("entes", "sucesso", 5)
    ]
    assert fontes_status[0]["ultimo_sucesso_em"]
