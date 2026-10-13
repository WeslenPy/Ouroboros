"""Comparação aproximada de nomes civis (abreviações, sobrenome de casamento, grafia).

Usada só entre pessoas com a mesma data de nascimento. Regra: todo token do nome mais curto
precisa casar com algum token do outro nome — igual, inicial ("A." -> "ARISTOTELES"),
abreviação conhecida ("JR" -> "JUNIOR") ou erro de grafia (FOLLETTO/FOLETTO). Nomes com 4+
partes toleram um token sem par (sobrenome trocado, ex.: casamento) desde que compartilhem
algum sobrenome pouco comum — "LUIZ ANTONIO DA SILVA NEVES" x "... SILVA SANTOS" não passa.
"""

import re

from rapidfuzz import fuzz

from ouroboros.core.text import normalize

_NAO_LETRA = re.compile(r"[^a-z ]")
_PARTICULAS = {"de", "da", "do", "das", "dos", "e"}
_ABREVIACOES = {"jr": "junior", "fo": "filho", "nt": "neto", "sobr": "sobrinho"}
_MIN_TOKENS = 3

# nomes/sobrenomes frequentes demais para servir de evidência de identidade
_COMUNS = frozenset(
    """
    silva santos oliveira souza sousa rodrigues ferreira alves pereira lima gomes costa ribeiro
    martins carvalho almeida lopes soares fernandes vieira barbosa rocha dias nascimento andrade
    moreira nunes marques machado mendes freitas cardoso ramos goncalves santana teixeira araujo
    pinto correia correa melo mello castro reis jesus batista cruz miranda farias monteiro moura
    campos cunha neves pires medeiros rezende resende siqueira aguiar azevedo coelho braga
    junior filho neto sobrinho maria jose joao antonio francisco carlos paulo pedro luiz luis
    ana aparecida
    """.split()
)
_GRAFIA = 80


def tokens(nome: str) -> list[str]:
    return [t for t in _NAO_LETRA.sub(" ", normalize(nome)).split() if t not in _PARTICULAS]


def _casa(t: str, outros: list[str]) -> bool:
    for o in outros:
        if t == o or _ABREVIACOES.get(t) == o or _ABREVIACOES.get(o) == t:
            return True
        if len(t) == 1 and o.startswith(t) or len(o) == 1 and t.startswith(o):
            return True
        if min(len(t), len(o)) >= 4 and fuzz.ratio(t, o) >= _GRAFIA:
            return True
    return False


def mesma_pessoa(a: str, b: str) -> bool:
    ta, tb = tokens(a), tokens(b)
    if min(len(ta), len(tb)) < _MIN_TOKENS or ta[0] != tb[0]:
        return False
    curto, longo = sorted((ta, tb), key=len)
    com_par = [t for t in curto if _casa(t, longo)]
    sem_par = len(curto) - len(com_par)
    if sem_par == 0:
        return True
    raro_em_comum = any(len(t) > 1 and t not in _COMUNS for t in com_par[1:])
    return sem_par == 1 and len(curto) >= 4 and raro_em_comum
