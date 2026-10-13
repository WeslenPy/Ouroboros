from datetime import date
from decimal import Decimal

import fontes

from ouroboros.canonical import (
    ConvenioContratoRow,
    ConvenioDesembolsoRow,
    ConvenioEmendaRow,
    ConvenioFornecedorRow,
    ConvenioMetaRow,
    ConvenioRow,
)
from ouroboros.connectors.base import Connector
from ouroboros.connectors.transferegov.convenios import emenda_codigo


async def _rows(connector: Connector, particao: str):
    return connector.transform([r async for r in connector.extract(particao)])


def test_emenda_codigo_no_formato_da_transparencia():
    assert emenda_codigo("5400020230013", "60110001") == "202360110001"
    assert emenda_codigo("5400020230013", "") is None
    assert emenda_codigo("540002023", "6011") is None
    assert emenda_codigo("5400060000013", "60110001") is None  # ano impossível


async def test_convenios_do_ano_com_obra():
    rows = await _rows(fontes.transferegov_convenios(), "2024")
    convenios = {r.numero: r for r in rows if isinstance(r, ConvenioRow)}
    assert set(convenios) == {900001, 900002, 900003}  # 2023 e proposta sem convênio fora

    ubs = convenios[900001]
    assert ubs.ano == 2024
    assert ubs.municipio_codigo_ibge == 1100015
    assert ubs.proponente_cnpj == "15579000000111"
    assert ubs.objeto == "CONSTRUÇÃO DE UNIDADE BÁSICA DE SAÚDE"
    assert ubs.modalidade == "CONTRATO DE REPASSE"
    assert ubs.orgao_superior == "MINISTERIO DA SAUDE"
    assert (ubs.inicio_vigencia, ubs.fim_vigencia) == (date(2024, 3, 10), date(2025, 3, 10))
    assert ubs.valor_desembolsado == Decimal("800000")
    assert ubs.valor_saldo_conta == Decimal("15000.50")
    # obra: Obrasgov, coordenadas, execução e medições
    assert ubs.obra_id == "12345.11-22"
    assert ubs.obra_nome == "UBS Centro"
    assert (ubs.latitude, ubs.longitude) == (Decimal("-11.931200"), Decimal("-61.998100"))
    assert ubs.percentual_execucao == Decimal("35.00")
    assert ubs.valor_executado == Decimal("357000")
    assert ubs.inicio_obra == date(2024, 4, 10)
    assert (ubs.ultima_medicao, ubs.dias_sem_medicao) == (date(2024, 6, 30), 400)
    # endereço da primeira meta (por número) que tem endereço
    assert (ubs.endereco, ubs.cep) == ("Rua das Flores, 100 - Centro", "76954-000")

    hospital = convenios[900002]
    assert hospital.latitude is None  # longitude fora do Brasil descartada
    assert hospital.obra_nome == "Hospital"
    assert hospital.cep == "76870-000"


async def test_emendas_metas_contratos_e_desembolsos():
    rows = await _rows(fontes.transferegov_convenios(), "2024")
    emendas = [r for r in rows if isinstance(r, ConvenioEmendaRow)]
    assert {(e.convenio_numero, e.emenda_codigo) for e in emendas} == {
        (900001, "202439820001"),
        (900001, "202471230001"),
        (900002, "202439820003"),
        (900003, "202439820002"),
    }
    tabata = next(e for e in emendas if e.emenda_codigo == "202439820001")
    assert tabata.parlamentar_nome_normalizado == "tabata amaral"
    assert tabata.impositiva is True
    assert tabata.valor_repasse == Decimal("700000")

    metas = [r for r in rows if isinstance(r, ConvenioMetaRow)]
    assert {m.id for m in metas} == {50001, 50002, 50003}  # ligadas pela proposta
    assert {r.id for r in rows if isinstance(r, ConvenioDesembolsoRow)} == {60001, 60002, 60003}

    contratos = {r.id: r for r in rows if isinstance(r, ConvenioContratoRow)}
    assert set(contratos) == {7001, 7002, 7003, 7004}
    assert contratos[7001].fornecedor_documento == "11222333000181"
    assert contratos[7001].modalidade_licitacao == "Concorrência"
    assert contratos[7002].modalidade_licitacao == "Pregão"  # sem modalidade: tipo do processo
    assert contratos[7004].fornecedor_documento == "***26003***"  # CPF fica mascarado
    assert contratos[7001].data_assinatura == date(2024, 4, 1)


async def test_pagamentos_somados_por_fornecedor():
    rows = await _rows(fontes.transferegov_pagamentos(), "atual")
    por = {
        (r.convenio_numero, r.documento): r for r in rows if isinstance(r, ConvenioFornecedorRow)
    }
    construtora = por[(900001, "11222333000181")]
    assert construtora.valor == Decimal("500000.50")
    assert construtora.pagamentos == 2
    assert (construtora.primeiro_pagamento, construtora.ultimo_pagamento) == (
        date(2024, 5, 10),
        date(2024, 7, 10),
    )
    pf = por[(900001, None)]  # pessoas físicas numa linha só, sem CPF
    assert (pf.nome, pf.pagamentos, pf.valor) == ("Pessoas físicas", 2, Decimal("1500"))
    assert por[(900002, "11222333000181")].valor == Decimal("250000")
