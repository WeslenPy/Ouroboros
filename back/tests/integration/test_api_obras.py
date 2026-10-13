import fontes
import httpx
from sqlalchemy import select

from ouroboros.analises.detectores import empreiteira_concentrada, obra_parada
from ouroboros.core.db import get_sessionmaker
from ouroboros.core.raw_store import RawStore
from ouroboros.models import ConvenioEmenda
from ouroboros.pipelines.loaders import (
    load_convenio_pagamentos,
    load_convenios,
    load_emendas,
    load_entes,
    load_parlamentares,
)
from ouroboros.pipelines.runner import run_connector

CONSTRUTORA = "11222333000181"


async def _carregar(store: RawStore, *, convenios_primeiro: bool) -> None:
    convenios = [
        (fontes.transferegov_convenios(), load_convenios, "2024"),
        (fontes.transferegov_pagamentos(), load_convenio_pagamentos, "atual"),
    ]
    resto = [
        (fontes.ibge(), load_entes, "atual"),
        (fontes.camara_deputados(), load_parlamentares, "57"),
        (fontes.transparencia_emendas(), load_emendas, "2024"),
    ]
    for connector, loader, particao in (
        convenios + resto if convenios_primeiro else resto + convenios
    ):
        await run_connector(connector, loader, particao, store=store)


async def _tabata(api: httpx.AsyncClient) -> int:
    return (await api.get("/v1/politicos", params={"busca": "tabata"})).json()["items"][0]["id"]


async def test_convenios_ligam_autor_mesmo_carregando_antes(api: httpx.AsyncClient, tmp_path):
    await _carregar(RawStore(tmp_path), convenios_primeiro=True)
    tabata = await _tabata(api)
    async with get_sessionmaker()() as s:
        autores = dict(
            (
                await s.execute(select(ConvenioEmenda.emenda_codigo, ConvenioEmenda.politico_id))
            ).all()
        )
    assert autores["202439820001"] == tabata  # pelo código da emenda
    assert autores["202439820003"] == tabata  # sem emenda na Transparência: pelo nome
    assert autores["202471230001"] is None  # bancada


async def test_obras_api(api: httpx.AsyncClient, tmp_path):
    await _carregar(RawStore(tmp_path), convenios_primeiro=False)
    tabata = await _tabata(api)

    lista = (await api.get("/v1/obras", params={"politico": tabata})).json()
    assert [o["numero"] for o in lista["items"]] == [900003, 900002, 900001]
    assert (await api.get("/v1/obras", params={"fornecedor": CONSTRUTORA})).json()["items"]
    assert [o["numero"] for o in (await api.get("/v1/obras?parada=true")).json()["items"]] == [
        900001
    ]
    assert len((await api.get("/v1/obras", params={"municipio": 1100015})).json()["items"]) == 2

    obra = (await api.get("/v1/obras/900001")).json()
    assert obra["latitude"] == "-11.931200"
    assert obra["percentual_execucao"] == "35.00"
    assert obra["valor_pago_fornecedores"] == "501500.50"
    assert {e["politico_nome"] for e in obra["emendas"]} == {"Tabata Amaral", None}
    assert [m["numero"] for m in obra["metas"]] == [1, 2]
    assert len(obra["desembolsos"]) == 2
    assert obra["contratos"][0]["fornecedor_documento"] == CONSTRUTORA
    assert "idProposta=1000001" in obra["link_transferegov"]
    assert (await api.get("/v1/obras/1")).status_code == 404

    resumo = (await api.get("/v1/obras/resumo", params={"uf": "RO"})).json()
    assert resumo["quantidade"] == 3
    assert resumo["com_localizacao"] == 1
    assert resumo["paradas"] == 1
    assert resumo["maiores_autores"][0]["rotulo"] == "Tabata Amaral"
    assert resumo["maiores_autores"][0]["quantidade"] == 3
    fornecedor = resumo["maiores_fornecedores"][0]
    assert (fornecedor["chave"], fornecedor["valor_global"]) == (CONSTRUTORA, "2050000.00")
    assert fornecedor["valor_desembolsado"] == "750000.50"

    mapa = (await api.get("/v1/obras/mapa")).json()
    assert [p["numero"] for p in mapa] == [900001]

    # emenda de ponta a ponta: destino (Transparência) -> convênio (Transferegov)
    emenda = (await api.get("/v1/emendas/202439820001")).json()
    assert emenda["politico_nome"] == "Tabata Amaral"
    assert [o["numero"] for o in emenda["obras"]] == [900001]
    assert (await api.get("/v1/emendas/000000000000")).status_code == 404


async def test_grafos_com_obras(api: httpx.AsyncClient, tmp_path):
    await _carregar(RawStore(tmp_path), convenios_primeiro=False)
    tabata = await _tabata(api)

    g = (await api.get(f"/v1/grafo/politico/{tabata}")).json()
    ids = {n["id"] for n in g["nos"]}
    assert {"hub:obras", "obra:900001", f"doc:{CONSTRUTORA}"} <= ids
    arestas = {(a["origem"], a["destino"], a["tipo"]) for a in g["arestas"]}
    assert ("obra:900001", "municipio:1100015", "local") in arestas  # liga ao destino da emenda

    g = (await api.get("/v1/grafo/obra/900001")).json()
    nos = {n["id"]: n for n in g["nos"]}
    assert nos["obra:900001"]["rotulo"] == "UBS Centro"
    assert nos[f"politico:{tabata}"]["rotulo"] == "Tabata Amaral"
    assert "autor:BANCADA DE RONDONIA" in nos
    assert nos["municipio:1100015"]["chave"] == "1100015"
    assert nos[f"doc:{CONSTRUTORA}"]["valor"] == "500000.50"
    # outras obras da mesma empreiteira
    assert {"obra:900002", "obra:900003"} <= set(nos)

    g = (await api.get(f"/v1/grafo/documento/{CONSTRUTORA}")).json()
    nos = {n["id"]: n for n in g["nos"]}
    assert nos[f"doc:{CONSTRUTORA}"]["rotulo"] == "Construtora Exemplo LTDA"
    assert {"hub:obras", "obra:900001", f"politico:{tabata}"} <= set(nos)

    g = (await api.get("/v1/grafo/municipio/1100015")).json()
    assert {"hub:obras", "obra:900001", "obra:900003"} <= {n["id"] for n in g["nos"]}


async def test_detectores_de_obras(api: httpx.AsyncClient, tmp_path):
    await _carregar(RawStore(tmp_path), convenios_primeiro=False)
    tabata = await _tabata(api)
    async with get_sessionmaker()() as s:
        paradas = await obra_parada(s)
        concentradas = await empreiteira_concentrada(s)

    assert [a["politico_id"] for a in paradas] == [tabata]
    assert paradas[0]["evidencias"]["obras"][0]["numero"] == 900001  # 900003 tem contas aprovadas
    assert len(concentradas) == 1
    alerta = concentradas[0]
    assert (alerta["politico_id"], alerta["entidade_documento"]) == (tabata, CONSTRUTORA)
    assert alerta["evidencias"]["metricas"]["municipios"] == 2
