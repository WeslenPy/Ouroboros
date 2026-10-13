from datetime import date
from decimal import Decimal

from ouroboros.core.parse import clean, parse_date, parse_decimal
from ouroboros.core.privacy import cpf_hmac, documento_publico, mask_cpf
from ouroboros.resolution.nomes import mesma_pessoa


def test_cpf_hmac_estavel_e_rejeita_invalidos():
    assert cpf_hmac("123.456.789-01") == cpf_hmac("12345678901")
    assert len(cpf_hmac("12345678901")) == 64
    assert cpf_hmac("11111111111") is None
    assert cpf_hmac("-4") is None
    assert cpf_hmac(None) is None


def test_documento_publico_mascara_pessoa_fisica():
    assert documento_publico("26.452.091/0001-90") == ("26452091000190", "pj")
    assert documento_publico("860.691.872-53") == ("***.691.872-**", "pf")
    assert mask_cpf("86069187253") == "***.691.872-**"
    assert documento_publico("") == (None, None)


def test_parse():
    assert parse_decimal("1.234,56") == Decimal("1234.56")
    assert parse_decimal("1148.7") == Decimal("1148.7")
    assert parse_decimal("-1") == Decimal("-1")  # valor legítimo, não marcador de nulo
    assert parse_date("2024-02-07T00:00:00") == date(2024, 2, 7)
    assert parse_date("17/01/2024", "%d/%m/%Y") == date(2024, 1, 17)
    assert parse_date("31/02/2024", "%d/%m/%Y") is None
    assert clean("#NULO") is None
    assert clean(" NÃO DIVULGÁVEL ") is None


# Pares reais Câmara x TSE (mesma data de nascimento) que não batiam por nome exato.
MESMA_PESSOA = [
    ("ANDREIA BRITO GONÇALVES SIQUEIRA", "ANDREIA BRITO GONÇALVES SIQUEIRA"),
    ("JOSÉ AUGUSTO PUPPIO REIS JÚNIOR", "JOSÉ AUGUSTO PUPIO REIS JÚNIOR"),
    ("CARLA SIMARA LUCIANA DA SILVA AYRES", "CARLA SIMARA LUCIANA DA SILVA SALASÁRIO AYRES"),
    ("Carlos Roberto Jordy Coelho de Mattos", "CARLOS ROBERTO COELHO DE MATTOS JUNIOR"),
    ("CRISTIANE LOPES DA LUZ", "CRISTIANE LOPES DA LUZ BENARROSH"),
    ("ELIANE DE SOUSA ALVES", "ELIANE DE SOUSA ALVES MACHADO"),
    ("EMANUEL PINHEIRO DA SILVA PRIMO", "EMANUEL PINHEIRO DA SILVA PRIMO TEIXEIRA"),
    ("FABIANO LOPES FERREIRA CAZECA", "FABIANO LOPES FERREIRA"),
    (
        "GUILHERME A. UCHOA CAVALCANTI PESSOA DE MELO JUNIOR",
        "GUILHERME ARISTOTELES UCHOA CAVALCANTI PESSOA DE MELO JUNIOR",
    ),
    ("MAURO IVAN F. SANTIAGO JR", "MAURO IVAN FARIAS DE SANTIAGO JUNIOR"),
    ("JOSE LOURENÇO BOMFIM JUNIOR", "JOSÉ LOURENÇO BONFIM JÚNIOR"),
    ("LUIZ ANTONIO C. C. CORRÊA DA SILVA", "LUIZ ANTONIO DA COSTA CARVALHO CORREA DA SILVA"),
    ("LUIZ PHILIPPE DE ORLEANS BRAGANÇA", "LUIZ PHILIPPE DE ORLEANS E BRAGANÇA"),
    ("DAÍZE MICHELE DE AGUIAR GONÇALVES COLLINS", "DAIZE MICHELE DE AGUIAR GONÇALVES"),
    ("PATRUS ANANIAS DE SOUZA", "PATRUS ANANIAS DE SOUSA"),
    ("PAULO ROBERTO FOLLETTO", "PAULO ROBERTO FOLETTO"),
    ("PEDRO HENRIQUE DE A. L. C. CAMPOS", "PEDRO HENRIQUE DE ANDRADE LIMA CARNEIRO CAMPOS"),
    ("SIMONE APARECIDA MARQUETO CURRALADAS", "SIMONE APARECIDA CURRALADAS DOS SANTOS"),
    ("SONIA BONE DE SOUSA SILVA", "SÔNIA BONE DE SOUSA SILVA SANTOS"),
    ("JOSÉ ESTEPHAN AMORIM BARBARY FILHO", "JOSÉ ESTEPHAN BARBARY FILHO"),
]
# Nome contido no outro com a mesma data de nascimento ("LUIZ ANTONIO DA SILVA" x
# "LUIZ ANTONIO DA SILVA NEVES") é aceito: é o padrão de sobrenome de casamento.
PESSOAS_DIFERENTES = [
    ("ELIANE DE SOUSA ALVES", "ELIANE SOARES DE SOUSA"),
    ("LUIZ ANTONIO DA SILVA NEVES", "LUIZ ANTONIO DA SILVA SANTOS"),
    ("JOSE DA SILVA", "MARIA DA SILVA"),
    ("MARIA SILVA", "MARIA SILVA SANTOS"),  # nomes curtos demais para arriscar
    ("ANTONIO LUIZ DA SILVA", "LUIZ ANTONIO C. C. CORRÊA DA SILVA"),
]


def test_nomes_casos_reais():
    for a, b in MESMA_PESSOA:
        assert mesma_pessoa(a, b), (a, b)
        assert mesma_pessoa(b, a), (b, a)
    for a, b in PESSOAS_DIFERENTES:
        assert not mesma_pessoa(a, b), (a, b)
