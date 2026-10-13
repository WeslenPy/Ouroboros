from decimal import Decimal

import fontes

from ouroboros.canonical import EmendaFavorecidoRow, EmendaRow
from ouroboros.core.raw_store import RawRecord


async def _rows(particao: str):
    connector = fontes.transparencia_emendas()
    records: list[RawRecord] = [r async for r in connector.extract(particao)]
    return connector.transform(records)


async def test_emendas_filtra_ano_e_normaliza():
    rows = await _rows("2024")
    emendas = [r for r in rows if isinstance(r, EmendaRow)]
    favorecidos = [r for r in rows if isinstance(r, EmendaFavorecidoRow)]

    assert len(emendas) == 4  # a de 2023 fica de fora
    assert len(favorecidos) == 4
    tabata = next(e for e in emendas if e.codigo == "202439820001")
    assert tabata.uf == "RO"
    assert tabata.municipio_codigo_ibge == 1100015
    assert tabata.funcao == "Saúde"
    assert tabata.valor_pago == Decimal("800000.00")
    assert tabata.valor_rp_pago == Decimal("100000.00")

    # título "DEP." sai do nome normalizado; município "-1"/"Sem informação" vira nulo
    estadual = next(e for e in emendas if e.codigo == "202439820002")
    assert estadual.autor_nome_normalizado == "tabata amaral"
    assert estadual.municipio_codigo_ibge is None
    assert estadual.municipio_nome is None
    assert estadual.uf == "SP"

    gol = next(f for f in favorecidos if f.autor_nome == "TABATA AMARAL")
    assert gol.favorecido_documento == "07575651000159"
    assert (gol.ano, gol.mes) == (2024, 5)
    pf = next(f for f in favorecidos if f.favorecido_tipo == "Pessoa Fisica")
    assert pf.favorecido_documento == "***.638.223-**"  # CPF já vem mascarado


async def test_emendas_outro_ano():
    rows = await _rows("2023")
    assert [r.codigo for r in rows if isinstance(r, EmendaRow)] == ["202339820001"]
    assert len([r for r in rows if isinstance(r, EmendaFavorecidoRow)]) == 1
