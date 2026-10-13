"""Presidentes + cartão da Presidência: atribuição pela data ao presidente em exercício."""

import fontes
import httpx
from test_presidencia import CPGF_CSV, HISTORICO, _zip

from ouroboros.connectors.presidencia import (
    CartaoHistoricoConnector,
    CpgfPresidenciaConnector,
    PresidentesConnector,
)
from ouroboros.core.raw_store import RawStore
from ouroboros.pipelines.loaders import load_entes, load_parlamentares
from ouroboros.pipelines.presidencia import load_gastos_presidencia
from ouroboros.pipelines.runner import run_connector


async def test_gastos_por_presidente(api: httpx.AsyncClient, tmp_path):
    store = RawStore(tmp_path)
    historico = fontes.com_fixtures(CartaoHistoricoConnector, [("cartao", HISTORICO)])
    portal = fontes.com_fixtures(
        CpgfPresidenciaConnector, [("cpgf_202401", _zip("202401_CPGF.csv", CPGF_CSV))]
    )
    # gastos antes dos presidentes: atribuição é na consulta, ordem não importa
    await run_connector(historico, load_gastos_presidencia, "2003-2022", store=store)
    await run_connector(portal, load_gastos_presidencia, "2024", store=store)
    await run_connector(fontes.ibge(), load_entes, "atual", store=store)
    await run_connector(PresidentesConnector(), load_parlamentares, "atual", store=store)
    # recarregar a partição substitui, não duplica
    await run_connector(historico, load_gastos_presidencia, "2003-2022", store=store)

    presidentes = (await api.get("/v1/presidencia/presidentes")).json()
    por_mandato = {m["id_externo"]: m for p in presidentes for m in p["mandatos"]}
    assert [p["nome"] for p in presidentes] == ["Lula", "Dilma Rousseff", "Michel Temer",
                                                "Jair Bolsonaro"]  # fmt: skip
    assert por_mandato["lula-2003"]["total"] == "2590.00"
    assert por_mandato["bolsonaro-2019"]["total"] == "291.67"  # 300 - 8,33
    assert por_mandato["bolsonaro-2019"]["saques"] == "300.00"
    # Portal: sigiloso sem data vale pelo extrato (jan/2024); o saque de 02/12/2023 também é Lula
    assert por_mandato["lula-2023"]["total"] == "27751.70"
    assert por_mandato["lula-2023"]["sigiloso"] == "27251.70"
    assert por_mandato["temer-2016"]["quantidade"] == 0

    bolsonaro = next(p["politico_id"] for p in presidentes if p["nome"] == "Jair Bolsonaro")
    gastos = (await api.get("/v1/presidencia/gastos", params={"politico": bolsonaro})).json()
    assert len(gastos["items"]) == 2
    assert {g["presidente"] for g in gastos["items"]} == {"Jair Bolsonaro"}

    resumo = (await api.get("/v1/presidencia/resumo", params={"mandato": "lula-2003"})).json()
    assert resumo["por_categoria"][0]["chave"] == "HOSPEDAGENS"
    assert resumo["maiores_favorecidos"][0]["chave"] == "HOTEL FICTÍCIO"
    assert "nominais" in resumo["aviso"]

    perfil = (await api.get(f"/v1/politicos/{bolsonaro}/mandatos")).json()
    assert any(m["cargo"] == "presidente" for m in perfil)
