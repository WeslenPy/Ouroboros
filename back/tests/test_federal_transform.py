from datetime import date
from decimal import Decimal

import fontes

from ouroboros.canonical import (
    CandidaturaRow,
    CpfPessoaRow,
    DespesaRow,
    MandatoRow,
    PartidoRow,
    PessoaRow,
)
from ouroboros.core.privacy import cpf_hmac
from ouroboros.models.mandato import Cargo


async def _rows(connector, particao):
    records = [r async for r in connector.extract(particao)]
    return connector.transform(records)


def _of(rows, kind):
    return [r for r in rows if isinstance(r, kind)]


async def test_camara_deputados_junta_lista_e_csv():
    rows = await _rows(fontes.camara_deputados(), "57")
    pessoas = {p.id_externo: p for p in _of(rows, PessoaRow)}
    mandatos = {m.pessoa_id_externo: m for m in _of(rows, MandatoRow)}

    assert set(pessoas) == {"204534", "209787", "228272"}  # duplicatas da lista viram uma pessoa
    tabata = pessoas["204534"]
    assert (tabata.nome, tabata.nome_civil, tabata.data_nascimento, tabata.genero) == (
        "Tabata Amaral",
        "TABATA CLAUDIA AMARAL DE PONTES",
        date(1993, 11, 14),
        "F",
    )
    m = mandatos["204534"]
    assert (m.cargo, m.uf, m.partidos, m.legislatura) == (Cargo.DEPUTADO_FEDERAL, "SP", ["PSB"], 57)
    assert (m.inicio, m.fim) == (date(2023, 2, 1), date(2027, 1, 31))
    assert m.id_externo == "204534:57"


async def test_camara_ceap():
    rows = await _rows(fontes.camara_ceap(), "2024")
    despesas = _of(rows, DespesaRow)
    cpfs = _of(rows, CpfPessoaRow)

    assert len(despesas) == 5
    lideranca = next(d for d in despesas if d.parlamentar_nome == "LID.GOV-CD")
    assert lideranca.parlamentar_id_externo is None
    assert lideranca.uf is None  # "NA" na fonte
    assert lideranca.fornecedor_tipo == "pj"
    estorno = next(d for d in despesas if d.valor_liquido < 0)
    assert estorno.valor_liquido == Decimal("-45.09")
    tabata = [d for d in despesas if d.parlamentar_id_externo == "204534"]
    assert {d.mes for d in tabata} == {1, 2, 4}
    assert tabata[0].data_emissao == date(2024, 1, 23)
    assert all(d.verba == "CEAP" and d.fonte == "camara" for d in despesas)
    # CPF do deputado vira hint de identidade; nunca aparece em claro
    assert {c.id_externo for c in cpfs} == {"204534", "160674"}
    assert next(c for c in cpfs if c.id_externo == "204534").cpf_hmac == cpf_hmac("90000000000")


async def test_senado_so_quem_exerceu_e_partido_do_mandato_atual():
    rows = await _rows(fontes.senado_senadores(), "57")
    pessoas = _of(rows, PessoaRow)
    mandatos = _of(rows, MandatoRow)

    assert [p.id_externo for p in pessoas] == ["5411"]  # suplente que não assumiu fica de fora
    weverton = pessoas[0]
    assert (weverton.nome, weverton.nome_civil, weverton.data_nascimento) == (
        "Weverton",
        "Weverton Rocha Marques de Sousa",
        date(1979, 10, 8),
    )
    (m,) = mandatos
    assert (m.cargo, m.uf, m.condicao, m.legislatura) == (Cargo.SENADOR, "MA", "Titular", 56)
    assert m.inicio == date(2019, 2, 1)
    assert m.fim == date(2027, 1, 31)
    assert m.partidos == ["PDT"]


async def test_senado_ceaps_latin1_e_decimal_brasileiro():
    rows = await _rows(fontes.senado_ceaps(), "2024")
    despesas = _of(rows, DespesaRow)
    assert len(despesas) == 3
    d = despesas[0]
    assert (d.parlamentar_nome, d.parlamentar_nome_normalizado) == (
        "WEVERTON ROCHA",
        "weverton rocha",
    )
    assert d.parlamentar_id_externo is None
    assert d.categoria.startswith("Aluguel de imóveis")
    assert d.valor_liquido == Decimal("355")
    assert d.data_emissao == date(2023, 12, 19)
    assert d.fornecedor_documento == "26452091000190"


async def test_tse_candidatos():
    rows = await _rows(fontes.tse_candidatos(), "2022")
    pessoas = {p.nome_civil: p for p in _of(rows, PessoaRow)}
    candidaturas = {c.nome_urna: c for c in _of(rows, CandidaturaRow)}
    partidos = {p.sigla for p in _of(rows, PartidoRow)}

    tabata = pessoas["TABATA CLAUDIA AMARAL DE PONTES"]
    assert tabata.cpf_hmac == cpf_hmac("90000000000")
    assert tabata.data_nascimento == date(1993, 11, 14)
    assert tabata.nome == "TABATA AMARAL"
    weverton = candidaturas["WEVERTON"]
    assert (weverton.cargo, weverton.uf, weverton.eleito) == ("GOVERNADOR", "MA", False)
    assert candidaturas["TABATA AMARAL"].eleito is True
    assert {"PSB", "PDT", "PL"} <= partidos
