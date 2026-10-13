from datetime import date
from decimal import Decimal

import fontes
import httpx
from sqlalchemy import func, select

from ouroboros.canonical import CpfPessoaRow, PessoaRow
from ouroboros.core.db import get_sessionmaker
from ouroboros.core.privacy import cpf_hmac
from ouroboros.core.raw_store import RawStore
from ouroboros.models import (
    DespesaGabinete,
    MatchPendente,
    Politico,
    PoliticoIdentificador,
)
from ouroboros.pipelines.loaders import (
    load_candidaturas,
    load_despesas,
    load_entes,
    load_parlamentares,
)
from ouroboros.pipelines.runner import run_connector
from ouroboros.resolution.politicos import aplicar_cpfs, resolver_pessoas

LINEAGE = {"fonte": "teste", "fonte_url": "fixture://", "raw_hash": "0" * 64}


async def _carregar_tudo(store: RawStore, *, despesas_primeiro: bool) -> None:
    await run_connector(fontes.ibge(), load_entes, "atual", store=store)
    despesas = [
        (fontes.senado_ceaps(), load_despesas, "2024"),
        (fontes.camara_ceap(), load_despesas, "2024"),
    ]
    pessoas = [
        (fontes.tse_candidatos(), load_candidaturas, "2022"),
        (fontes.camara_deputados(), load_parlamentares, "57"),
        (fontes.senado_senadores(), load_parlamentares, "57"),
    ]
    ordem = despesas + pessoas if despesas_primeiro else pessoas + despesas
    for connector, loader, particao in ordem:
        await run_connector(connector, loader, particao, store=store)


async def _contagens() -> dict[str, int]:
    async with get_sessionmaker()() as s:
        return {
            "politicos": await s.scalar(select(func.count()).select_from(Politico)),
            "identificadores": await s.scalar(
                select(func.count()).select_from(PoliticoIdentificador)
            ),
            "despesas": await s.scalar(select(func.count()).select_from(DespesaGabinete)),
            "despesas_ligadas": await s.scalar(select(func.count(DespesaGabinete.politico_id))),
        }


async def test_ligacao_entre_fontes_e_idempotencia(tmp_path):
    store = RawStore(tmp_path)
    # despesas antes das pessoas: o religamento posterior precisa achar o dono
    await _carregar_tudo(store, despesas_primeiro=True)
    antes = await _contagens()

    async with get_sessionmaker()() as s:
        por_origem = {}
        for origem, id_externo, pid, metodo in await s.execute(
            select(
                PoliticoIdentificador.origem,
                PoliticoIdentificador.id_externo,
                PoliticoIdentificador.politico_id,
                PoliticoIdentificador.metodo,
            )
        ):
            por_origem[(origem, id_externo)] = (pid, metodo)
        tabata = por_origem[("camara", "204534")][0]
        tse_tabata = next(v for k, v in por_origem.items() if k[0] == "tse" and v[0] == tabata)
        assert tse_tabata  # mesma pessoa no TSE e na Câmara
        assert por_origem[("camara", "204534")][1] == "nome_nascimento"
        weverton = por_origem[("senado", "5411")][0]
        assert any(k[0] == "tse" and v[0] == weverton for k, v in por_origem.items())

        politico = await s.get(Politico, tabata)
        assert politico.nome == "Tabata Amaral"  # nome parlamentar vence nome de urna
        assert politico.cpf_hmac == cpf_hmac("90000000000")

        sem_dono = {
            n
            for (n,) in await s.execute(
                select(DespesaGabinete.parlamentar_nome).where(
                    DespesaGabinete.politico_id.is_(None)
                )
            )
        }
        assert sem_dono == {"LID.GOV-CD", "Hugo Motta"}  # liderança e deputado não carregado

    # recarregar tudo, agora na ordem inversa, não muda nada
    await _carregar_tudo(store, despesas_primeiro=False)
    assert await _contagens() == antes
    assert antes["despesas"] == 8 and antes["despesas_ligadas"] == 6


async def test_api_politicos_e_despesas(api: httpx.AsyncClient, tmp_path):
    await _carregar_tudo(RawStore(tmp_path), despesas_primeiro=False)

    busca = (await api.get("/v1/politicos", params={"busca": "tabata", "com_mandato": True})).json()
    (tabata,) = busca["items"]
    assert tabata["ultimo_mandato"]["cargo"] == "deputado_federal"
    assert tabata["ultimo_mandato"]["partido_sigla"] == "PSB"

    so_candidatos = (await api.get("/v1/politicos", params={"busca": "tabata"})).json()
    assert len(so_candidatos["items"]) == 1  # uma pessoa, não uma por fonte

    senadores = (await api.get("/v1/politicos", params={"cargo": "senador"})).json()
    assert [p["nome"] for p in senadores["items"]] == ["Weverton"]
    em_exercicio = (
        await api.get("/v1/politicos", params={"em_exercicio": True, "uf": "MA"})
    ).json()
    assert [p["nome"] for p in em_exercicio["items"]] == ["Weverton"]

    detalhe = (await api.get(f"/v1/politicos/{tabata['id']}")).json()
    assert {i["origem"] for i in detalhe["identificadores"]} == {"camara", "tse"}
    assert detalhe["candidaturas"] == 1
    assert detalhe["gastos_gabinete_por_ano"] == [{"ano": 2024, "total": "672.00", "quantidade": 3}]
    assert "cpf_hmac" not in detalhe

    despesas = (await api.get(f"/v1/politicos/{tabata['id']}/despesas", params={"limit": 2})).json()
    assert len(despesas["items"]) == 2 and despesas["next_cursor"]
    resto = (
        await api.get(
            f"/v1/politicos/{tabata['id']}/despesas", params={"cursor": despesas["next_cursor"]}
        )
    ).json()
    assert len(resto["items"]) == 1 and resto["next_cursor"] is None

    resumo = (await api.get("/v1/despesas/resumo", params={"ano": 2024})).json()
    assert Decimal(resumo["total"]) == Decimal("1148.7") + 672 - Decimal("45.09") + 3 * 355
    assert resumo["quantidade"] == 8
    ceaps = (await api.get("/v1/despesas", params={"verba": "ceaps"})).json()
    assert {d["parlamentar_nome"] for d in ceaps["items"]} == {"WEVERTON ROCHA"}
    assert all(d["politico_id"] == senadores["items"][0]["id"] for d in ceaps["items"])
    por_cnpj = (await api.get("/v1/despesas", params={"fornecedor": "26.452.091/0001-90"})).json()
    assert len(por_cnpj["items"]) == 3

    csv = await api.get("/v1/despesas", params={"verba": "CEAP"}, headers={"Accept": "text/csv"})
    assert csv.headers["content-type"].startswith("text/csv")
    linhas = csv.text.lstrip("﻿").splitlines()
    assert linhas[0].startswith("id,politico_id,verba,")
    assert len(linhas) == 1 + 5

    assert (await api.get("/v1/politicos/999999")).status_code == 404


async def test_cpf_igual_funde_politicos():
    sm = get_sessionmaker()
    async with sm() as s:
        await resolver_pessoas(
            s,
            [
                PessoaRow(
                    origem="tse",
                    id_externo="1",
                    nome="ZEZINHO",
                    nome_civil="JOSÉ ESTEPHAN BARBARY FILHO",
                    data_nascimento=date(1964, 5, 28),
                    cpf_hmac=cpf_hmac("90000000999"),
                    **LINEAGE,
                )
            ],
        )
        # mesma pessoa na Câmara com data de nascimento digitada errada: vira político separado
        res = await resolver_pessoas(
            s,
            [
                PessoaRow(
                    origem="camara",
                    id_externo="9",
                    nome="Zezinho Barbary",
                    nome_civil="JOSÉ ESTEPHAN AMORIM BARBARY FILHO",
                    data_nascimento=date(1966, 5, 28),
                    **LINEAGE,
                )
            ],
        )
        assert res.criados == 1
        assert await s.scalar(select(func.count()).select_from(Politico)) == 2

        # CEAP traz o CPF do deputado: prova de que é a mesma pessoa
        await aplicar_cpfs(
            s, [CpfPessoaRow(origem="camara", id_externo="9", cpf_hmac=cpf_hmac("90000000999"))]
        )
        await s.commit()

        (unico,) = (await s.scalars(select(Politico))).all()
        assert unico.nome == "Zezinho Barbary"
        assert unico.cpf_hmac == cpf_hmac("90000000999")
        origens = set(
            (
                await s.scalars(
                    select(PoliticoIdentificador.origem).where(
                        PoliticoIdentificador.politico_id == unico.id
                    )
                )
            ).all()
        )
        assert origens == {"tse", "camara"}


async def test_homonimos_viram_pendencia():
    sm = get_sessionmaker()
    pessoa = {"nome_civil": "MARIA DE TAL", "data_nascimento": date(1970, 1, 1), **LINEAGE}
    async with sm() as s:
        # duas pessoas no TSE com mesmo nome e nascimento, CPFs diferentes
        await resolver_pessoas(
            s,
            [
                PessoaRow(
                    origem="tse",
                    id_externo="1",
                    nome="MARIA",
                    cpf_hmac=cpf_hmac("90000000001"),
                    **pessoa,
                ),
                PessoaRow(
                    origem="tse",
                    id_externo="2",
                    nome="MARIA",
                    cpf_hmac=cpf_hmac("90000000002"),
                    **pessoa,
                ),
            ],
        )
        # fonte sem CPF não tem como escolher: cria nova e registra pendência
        res = await resolver_pessoas(
            s, [PessoaRow(origem="senado", id_externo="7", nome="Maria", **pessoa)]
        )
        await s.commit()
        assert res.criados == 1
        (pendencia,) = (await s.scalars(select(MatchPendente))).all()
        assert pendencia.motivo == "nome_nascimento_ambiguo"
        assert len(pendencia.politico_ids) == 2
