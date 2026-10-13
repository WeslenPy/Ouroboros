import fontes
import httpx
from sqlalchemy import select

from ouroboros.core.db import get_sessionmaker
from ouroboros.core.raw_store import RawStore
from ouroboros.models import Emenda
from ouroboros.pipelines.loaders import (
    load_despesas,
    load_emendas,
    load_entes,
    load_parlamentares,
)
from ouroboros.pipelines.runner import run_connector


async def _carregar(store: RawStore, *, emendas_primeiro: bool) -> None:
    emendas = [(fontes.transparencia_emendas(), load_emendas, "2024")]
    resto = [
        (fontes.ibge(), load_entes, "atual"),
        (fontes.camara_deputados(), load_parlamentares, "57"),
        (fontes.senado_senadores(), load_parlamentares, "57"),
        (fontes.camara_ceap(), load_despesas, "2024"),
    ]
    for connector, loader, particao in emendas + resto if emendas_primeiro else resto + emendas:
        await run_connector(connector, loader, particao, store=store)


async def _tabata(api: httpx.AsyncClient) -> int:
    return (await api.get("/v1/politicos", params={"busca": "tabata"})).json()["items"][0]["id"]


async def test_emendas_ligam_autor_mesmo_carregando_antes(api: httpx.AsyncClient, tmp_path):
    # emendas antes dos parlamentares: load_parlamentares religa depois
    await _carregar(RawStore(tmp_path), emendas_primeiro=True)
    tabata = await _tabata(api)

    async with get_sessionmaker()() as s:
        autores = dict((await s.execute(select(Emenda.autor_nome, Emenda.politico_id))).all())
    assert autores["TABATA AMARAL"] == tabata
    assert autores["DEP. TABATA AMARAL"] == tabata
    assert autores["WEVERTON"] is not None
    assert autores["BANCADA DE RONDONIA"] is None  # autor coletivo

    resumo = (await api.get("/v1/emendas/resumo", params={"ano": 2024})).json()
    assert resumo["quantidade"] == 4
    assert resumo["pago"] == "1200000.00"  # 800k + 100k (restos) + 300k
    assert {f["chave"] for f in resumo["por_funcao"]} >= {"Saúde", "Urbanismo"}
    assert resumo["maiores_autores"][0]["rotulo"] == "Tabata Amaral"

    lista = (await api.get("/v1/emendas", params={"politico": tabata})).json()
    assert {e["codigo"] for e in lista["items"]} == {"202439820001", "202439820002"}
    favs = await api.get("/v1/emendas/favorecidos", params={"favorecido": "07575651000159"})
    assert len(favs.json()["items"]) == 2


async def test_grafos(api: httpx.AsyncClient, tmp_path):
    await _carregar(RawStore(tmp_path), emendas_primeiro=False)
    tabata = await _tabata(api)

    g = (await api.get(f"/v1/grafo/politico/{tabata}")).json()
    nos = {n["id"]: n for n in g["nos"]}
    assert g["centro"] == f"politico:{tabata}"
    assert {"hub:carreira", "hub:gastos", "hub:emendas"} <= set(nos)
    assert nos["area:Saúde"]["pai"] == "hub:emendas"
    assert nos["municipio:1100015"]["pai"] == "area:Saúde"
    # GOL: fornecedor na cota e favorecido de emenda -> um nó só (mesmo CNPJ)
    gol = nos["doc:07575651000159"]
    assert gol["chave"] == "07575651000159"
    # Weverton também mandou emenda para a GOL -> conexão
    conexoes = [n for n in g["nos"] if n["grupo"] == "conexoes"]
    assert any(n["pai"] == "doc:07575651000159" for n in conexoes)
    ids = {n["id"] for n in g["nos"]}
    assert all(a["origem"] in ids and a["destino"] in ids for a in g["arestas"])

    doc = (await api.get("/v1/grafo/documento/07575651000159")).json()
    assert doc["centro"] == "doc:07575651000159"
    assert {"hub:gastos", "hub:emendas"} <= {n["id"] for n in doc["nos"]}

    mun = (await api.get("/v1/grafo/municipio/1100015")).json()
    rotulos = {n["rotulo"] for n in mun["nos"]}
    assert "Tabata Amaral" in rotulos
    assert "Bancada de Rondonia" not in rotulos  # só empenhado, nada pago: fica fora

    assert (await api.get("/v1/grafo/politico/999999")).status_code == 404
    assert (await api.get("/v1/grafo/documento/123")).status_code == 400
