import pytest

from ouroboros.analises.detectores import CATALOGO
from ouroboros.analises.estatistica import (
    BENFORD,
    cnpj_valido,
    desvio_digitos,
    distribuicao,
    escala,
    escala_log,
    mistura,
    risco,
    score,
    score_detector,
    severidade,
    z_robusto,
)


@pytest.mark.parametrize(
    ("doc", "ok"),
    [
        ("07575651000159", True),  # GOL
        ("00000000000191", True),  # Banco do Brasil
        ("07575651000158", False),  # dígito errado
        ("00000000000006", False),  # placeholder da Câmara
        ("11111111111111", False),
        ("0757565100015", False),
        ("***.456.789-**", False),
        (None, False),
    ],
)
def test_cnpj_valido(doc, ok):
    assert cnpj_valido(doc) is ok


def test_desvio_digitos_zero_quando_igual_ao_esperado():
    contagens = {d: round(1000 * p) for d, p in BENFORD.items()}
    assert desvio_digitos(contagens, BENFORD) < 0.001
    # tudo começando com 9: muito longe de Benford
    assert desvio_digitos({9: 500}, BENFORD) > 0.15


def test_mistura_pondera_pelo_tamanho_de_cada_parte():
    so_um = {1: 1.0}
    so_dois = {2: 1.0}
    esperado = mistura([(30, so_um), (10, so_dois)])
    assert esperado[1] == pytest.approx(0.75)
    assert esperado[2] == pytest.approx(0.25)
    assert sum(esperado.values()) == pytest.approx(1.0)
    assert distribuicao({1: 3, 2: 1})[1] == 0.75


def test_z_robusto_nao_e_distorcido_pelo_proprio_outlier():
    pares = [10.0, 11, 9, 10, 12, 10, 9, 11, 10, 1000]
    assert z_robusto(1000, pares) > 100
    assert abs(z_robusto(10, pares)) < 1
    assert z_robusto(5, [3.0, 3, 3]) == 0  # sem dispersão


def test_escalas_e_score():
    assert escala(5, 0, 10) == 0.5
    assert escala(-1, 0, 10) == 0 and escala(99, 0, 10) == 1
    assert escala_log(100_000, 10_000, 1_000_000) == pytest.approx(0.5)
    assert escala_log(0, 1, 10) == 0
    assert score(40, (40, 1.0), (30, 1.0)) == 100  # limitado
    assert score(40, (-50, 1.0)) == 0
    assert [severidade(s) for s in (70, 69.9, 45, 44.9)] == ["alta", "media", "media", "baixa"]


def test_score_detector_repeticao_nao_vira_achado_forte():
    assert score_detector([]) == 0
    assert score_detector([60]) == 60
    assert score_detector([60, 30, 30]) == 66
    assert score_detector([30] * 50) == 40  # bônus limitado a +10


def test_risco_combina_detectores_independentes():
    assert risco([]) == 0
    assert risco([(1.0, 50)]) == 50
    # dois indícios de 50% -> 75%
    assert risco([(1.0, 50), (1.0, 50)]) == 75
    # peso baixo contribui pouco
    assert risco([(0.25, 40)]) == 10
    assert risco([(1.0, 100)]) == 99  # nunca certeza


def test_catalogo_consistente():
    for codigo, det in CATALOGO.items():
        assert det.codigo == codigo
        assert 0 < det.peso <= 1
        assert det.area in {"gabinete", "emendas", "obras", "eleicoes"}
        assert len(det.metodologia) > 80
