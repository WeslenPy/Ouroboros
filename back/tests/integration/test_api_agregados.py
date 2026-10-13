import fontes
import httpx

from ouroboros.core.raw_store import RawStore
from ouroboros.pipelines.loaders import (
    load_candidaturas,
    load_despesas,
    load_entes,
    load_parlamentares,
)
from ouroboros.pipelines.runner import run_connector


async def _carregar(store: RawStore) -> None:
    for connector, loader, particao in [
        (fontes.ibge(), load_entes, "atual"),
        (fontes.tse_candidatos(), load_candidaturas, "2022"),
        (fontes.camara_deputados(), load_parlamentares, "57"),
        (fontes.senado_senadores(), load_parlamentares, "57"),
        (fontes.camara_ceap(), load_despesas, "2024"),
        (fontes.senado_ceaps(), load_despesas, "2024"),
    ]:
        await run_connector(connector, loader, particao, store=store)


async def test_stats_candidaturas_partidos_execucoes(api: httpx.AsyncClient, tmp_path):
    await _carregar(RawStore(tmp_path))

    stats = (await api.get("/v1/stats")).json()
    assert stats["politicos"] > 0
    assert stats["entes"] == 5
    assert stats["despesas"] > 0
    assert {v["verba"] for v in stats["despesas_por_verba"]} == {"CEAP", "CEAPS"}
    assert stats["ultima_ingestao_em"]

    cands = (await api.get("/v1/candidaturas", params={"limit": 1})).json()
    assert len(cands["items"]) == 1
    assert cands["items"][0]["politico_id"]
    resumo = (await api.get("/v1/candidaturas/resumo", params={"ano": 2022})).json()
    assert resumo["total"] == sum(a["quantidade"] for a in resumo["por_ano"])

    partidos = (await api.get("/v1/partidos")).json()
    assert partidos
    sigla = partidos[0]["sigla"]
    detalhe = (await api.get(f"/v1/partidos/{sigla.lower()}")).json()
    assert detalhe["sigla"] == sigla
    assert (await api.get("/v1/partidos/NAOEXISTE")).status_code == 404

    execucoes = (await api.get("/v1/fontes/execucoes", params={"limit": 2})).json()
    assert len(execucoes["items"]) == 2
    assert execucoes["items"][0]["id"] > execucoes["items"][1]["id"]
    resto = (
        await api.get("/v1/fontes/execucoes", params={"cursor": execucoes["next_cursor"]})
    ).json()
    assert len(resto["items"]) == 4

    assert (await api.get("/v1/matches-pendentes")).status_code == 200

    despesas = (await api.get("/v1/despesas/resumo", params={"ano": 2024})).json()
    assert sum(m["quantidade"] for m in despesas["por_mes"]) == despesas["quantidade"]
