"""Detectores contra dados sintéticos: cada caso positivo tem um gêmeo que não pode alertar."""

from datetime import date
from decimal import Decimal

import httpx

from ouroboros.analises import gerar_alertas
from ouroboros.core.db import get_sessionmaker
from ouroboros.models import DespesaGabinete, EmendaFavorecido, Politico

LINHAGEM = {"fonte": "teste", "fonte_url": "http://t", "raw_hash": "0" * 64}
FACHADA = "11222333000181"  # CNPJ válido, só fatura para Ana
GRAFICA = "07575651000159"  # paga pela cota e favorecida de emenda de Ana
POSTO = "00000000000191"  # posto de combustível: cupons, nunca alerta


def _politico(id: int, nome: str) -> Politico:
    return Politico(id=id, nome=nome, nome_normalizado=nome.lower(), nome_origem="camara")


def _despesa(pid: int, ano: int, mes: int, doc: str, numero: str, valor: str, **kw):
    return DespesaGabinete(
        verba="CEAP",
        politico_id=pid,
        parlamentar_origem="camara",
        parlamentar_id_externo=str(pid),
        parlamentar_nome=f"P{pid}",
        parlamentar_nome_normalizado=f"p{pid}",
        ano=ano,
        mes=mes,
        data_emissao=kw.pop("data", date(ano, mes, 10)),
        categoria=kw.pop("categoria", "DIVULGAÇÃO DA ATIVIDADE PARLAMENTAR."),
        fornecedor_nome=kw.pop("nome", "EMPRESA"),
        fornecedor_documento=doc,
        documento_numero=numero,
        documento_id_fonte=kw.pop("id_fonte", f"{pid}-{doc}-{numero}-{ano}-{mes}"),
        valor_liquido=Decimal(valor),
        **LINHAGEM,
        **kw,
    )


async def _carregar() -> None:
    linhas: list = [_politico(1, "Ana"), _politico(2, "Bruno")]
    # Ana: fachada emite notas 1..12, uma por mês, só para ela
    for i in range(12):
        linhas.append(_despesa(1, 2024, i + 1, FACHADA, str(i + 1), "8000.00", nome="FACHADA"))
    # Bruno: mesma nota duas vezes (meses diferentes, mesmo documento, ids distintos)
    for mes in (3, 4):
        linhas.append(
            _despesa(
                2, 2024, mes, GRAFICA, "4521", "5000.00",
                data=date(2024, 3, 2), id_fonte=f"dup-{mes}", nome="GRAFICA",
            )
        )  # fmt: skip
    # Bruno: nota 7000 duplicada, mas com estorno publicado -> não alerta
    for mes, valor in ((5, "900.00"), (6, "900.00"), (6, "-900.00")):
        linhas.append(
            _despesa(
                2, 2024, mes, GRAFICA, "7000", valor,
                data=date(2024, 5, 2), id_fonte=f"est-{mes}-{valor}", nome="GRAFICA",
            )
        )  # fmt: skip
    # Bruno: cupons de combustível sequenciais -> varejo, não alerta
    for i in range(12):
        linhas.append(
            _despesa(
                2, 2024, i + 1, POSTO, str(100 + i), "300.00",
                categoria="COMBUSTÍVEIS E LUBRIFICANTES.", nome="POSTO",
            )
        )  # fmt: skip
    # Ana também paga a gráfica pela cota e manda emenda para ela
    linhas.append(_despesa(1, 2024, 2, GRAFICA, "88", "6000.00", nome="GRAFICA"))
    linhas.append(
        EmendaFavorecido(
            emenda_codigo="202400010001",
            ano=2024,
            mes=6,
            tipo="Emenda Individual - Transferências com Finalidade Definida",
            autor_nome="ANA",
            autor_nome_normalizado="ana",
            politico_id=1,
            favorecido_documento=GRAFICA,
            favorecido_nome="GRAFICA LTDA",
            favorecido_tipo="Pessoa Jurídica",
            natureza_juridica="Sociedade Empresária Limitada",
            valor=Decimal("250000.00"),
            **LINHAGEM,
        )
    )
    async with get_sessionmaker()() as s:
        s.add_all(linhas[:2])
        await s.flush()
        s.add_all(linhas[2:])
        await s.commit()


async def test_detectores_e_api(api: httpx.AsyncClient):
    await _carregar()
    assert await gerar_alertas() > 0

    alertas = (await api.get("/v1/alertas", params={"limit": 500})).json()["items"]
    por = {(a["detector"], a["politico_id"], a["entidade_documento"]): a for a in alertas}

    seq = por[("notas_sequenciais", 1, FACHADA)]
    assert seq["evidencias"]["metricas"]["densidade"] == 1.0
    assert seq["politico_nome"] == "Ana"

    dup = por[("nota_duplicada", 2, GRAFICA)]
    assert dup["valor"] == "5000.00"  # só a cópia a mais
    assert len(dup["evidencias"]["documentos"]) == 2
    # estorno anula; cupom de posto nunca é "sequencial"
    assert not [a for a in alertas if "7000" in a["titulo"]]
    assert all(a["entidade_documento"] != POSTO for a in alertas)

    cruz = por[("fornecedor_favorecido", 1, GRAFICA)]
    assert cruz["evidencias"]["metricas"]["recebido_de_emendas"] == 250000.0

    # filtros e paginação por (score, id)
    so_ana = (await api.get("/v1/alertas", params={"politico": 1})).json()["items"]
    assert {a["politico_id"] for a in so_ana} == {1}
    pagina = (await api.get("/v1/alertas", params={"limit": 1})).json()
    seguinte = (
        await api.get("/v1/alertas", params={"limit": 1, "cursor": pagina["next_cursor"]})
    ).json()
    assert seguinte["items"][0]["score"] <= pagina["items"][0]["score"]
    assert seguinte["items"][0]["id"] != pagina["items"][0]["id"]
    assert (await api.get("/v1/alertas", params={"detector": "x"})).status_code == 400
    um = (await api.get(f"/v1/alertas/{seq['id']}")).json()
    assert um["id"] == seq["id"] and um["evidencias"] == seq["evidencias"]
    assert (await api.get("/v1/alertas/999999")).status_code == 404

    ranking = (await api.get("/v1/alertas/ranking")).json()
    assert "indícios" in ranking["aviso"]
    nomes = [i["nome"] for i in ranking["items"]]
    assert set(nomes) == {"Ana", "Bruno"}
    ana = next(i for i in ranking["items"] if i["nome"] == "Ana")
    assert {d["detector"] for d in ana["detectores"]} >= {
        "notas_sequenciais",
        "fornecedor_favorecido",
    }
    assert 0 < ana["risco"] < 100

    cat = (await api.get("/v1/alertas/detectores")).json()
    contagem = {d["codigo"]: d["alertas"] for d in cat["detectores"]}
    assert contagem["nota_duplicada"] == 1
    assert cat["gerado_em"] is not None

    # rodar de novo substitui, não acumula
    total = len(alertas)
    await gerar_alertas()
    assert len((await api.get("/v1/alertas", params={"limit": 500})).json()["items"]) == total
