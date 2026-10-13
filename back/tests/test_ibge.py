import fontes
import respx

from ouroboros.connectors.ibge import IbgeConnector
from ouroboros.connectors.ibge.connector import BASE_URL
from ouroboros.core.http import HttpClient
from ouroboros.models.ente import CODIGO_UNIAO, Esfera


async def _entes():
    connector = fontes.ibge()
    records = [r async for r in connector.extract("atual")]
    return {r.codigo_ibge: r for r in connector.transform(records)}


async def test_uniao_ufs_e_municipios():
    entes = await _entes()
    assert set(entes) == {CODIGO_UNIAO, 11, 51, 1100015, 5101837}
    assert entes[CODIGO_UNIAO].esfera is Esfera.FEDERAL
    ro = entes[11]
    assert (ro.esfera, ro.uf, ro.regiao, ro.nome_normalizado) == (
        Esfera.ESTADUAL,
        "RO",
        "Norte",
        "rondonia",
    )
    assert all(r.fonte == "ibge" and len(r.raw_hash) == 64 for r in entes.values())


async def test_municipio_sem_microrregiao_usa_regiao_imediata():
    novo = (await _entes())[5101837]
    assert (novo.esfera, novo.uf, novo.uf_codigo, novo.nome_normalizado) == (
        Esfera.MUNICIPAL,
        "MT",
        51,
        "boa esperanca do norte",
    )


@respx.mock
async def test_extract_baixa_estados_e_municipios(fixture_bytes):
    respx.get(f"{BASE_URL}/estados").respond(200, content=fixture_bytes("ibge", "estados.json"))
    respx.get(f"{BASE_URL}/municipios").respond(
        200, content=fixture_bytes("ibge", "municipios.json")
    )

    async with HttpClient(BASE_URL) as client:
        records = [r async for r in IbgeConnector(client).extract("atual")]

    assert [r.recurso for r in records] == ["estados", "municipios"]
    assert records[1].payload == fixture_bytes("ibge", "municipios.json")
