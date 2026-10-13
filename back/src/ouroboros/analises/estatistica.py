"""Funções puras usadas pelos detectores: validação de CNPJ, teste de dígitos, estatística
robusta, escalas de score e combinação de indícios. Sem banco, sem rede: testadas em
`tests/test_analises.py`."""

import math
from collections.abc import Iterable, Mapping

# Lei de Benford: P(primeiro dígito = d) = log10(1 + 1/d). Só referência: preços da cota não a
# seguem (ver `detectores.digitos_atipicos`), então o esperado vem dos pares.
BENFORD = {d: math.log10(1 + 1 / d) for d in range(1, 10)}


def cnpj_valido(doc: str | None) -> bool:
    """CNPJ com 14 dígitos e dígitos verificadores corretos (descarta 00000000000006 etc.)."""
    if not doc or len(doc) != 14 or not doc.isdigit() or doc == doc[0] * 14:
        return False
    nums = [int(c) for c in doc]
    for tamanho in (12, 13):
        pesos = list(range(tamanho - 7, 1, -1)) + list(range(9, 1, -1))
        soma = sum(n * p for n, p in zip(nums[:tamanho], pesos, strict=True))
        dv = 11 - soma % 11
        if (0 if dv >= 10 else dv) != nums[tamanho]:
            return False
    return True


def distribuicao(contagens: Mapping[int, int]) -> dict[int, float]:
    """Contagem por primeiro dígito (1-9) -> proporção."""
    n = sum(contagens.get(d, 0) for d in range(1, 10))
    return {d: (contagens.get(d, 0) / n if n else 0.0) for d in range(1, 10)}


def mistura(partes: Iterable[tuple[int, Mapping[int, float]]]) -> dict[int, float]:
    """Distribuição esperada para um conjunto com `n` valores de cada parte: média das
    distribuições das partes ponderada por `n` (ex.: 70% combustível, 30% divulgação)."""
    total = 0
    acc = dict.fromkeys(range(1, 10), 0.0)
    for n, dist in partes:
        total += n
        for d in range(1, 10):
            acc[d] += n * dist.get(d, 0.0)
    return {d: (v / total if total else 0.0) for d, v in acc.items()}


def desvio_digitos(contagens: Mapping[int, int], esperado: Mapping[int, float]) -> float:
    """Desvio absoluto médio (MAD de Nigrini) entre os primeiros dígitos e o esperado."""
    obs = distribuicao(contagens)
    return sum(abs(obs[d] - esperado.get(d, 0.0)) for d in range(1, 10)) / 9


def mediana(valores: list[float]) -> float:
    s = sorted(valores)
    n = len(s)
    if n == 0:
        raise ValueError("lista vazia")
    meio = n // 2
    return s[meio] if n % 2 else (s[meio - 1] + s[meio]) / 2


def z_robusto(valor: float, valores: list[float]) -> float:
    """Desvio em unidades de MAD (Iglewicz-Hoaglin): 0,6745·(x − mediana)/MAD.

    Robusto a outliers, ao contrário do z-score com média e desvio padrão (que os próprios
    outliers inflam). Retorna 0 se a dispersão for nula.
    """
    med = mediana(valores)
    mad = mediana([abs(v - med) for v in valores])
    if mad == 0:
        return 0.0
    return 0.6745 * (valor - med) / mad


def escala(valor: float, inicio: float, fim: float) -> float:
    """Posição de `valor` entre `inicio` (0) e `fim` (1), limitada a [0, 1]."""
    if fim == inicio:
        return 1.0 if valor >= fim else 0.0
    return min(1.0, max(0.0, (valor - inicio) / (fim - inicio)))


def escala_log(valor: float, inicio: float, fim: float) -> float:
    """Como `escala`, em escala logarítmica (dinheiro: R$ 10 mil -> R$ 1 milhão)."""
    if valor <= 0:
        return 0.0
    return escala(math.log10(valor), math.log10(inicio), math.log10(fim))


def score(base: float, *fatores: tuple[float, float]) -> float:
    """`base` + soma de (peso · fator 0-1), limitado a 0-100, uma casa decimal."""
    total = base + sum(peso * fator for peso, fator in fatores)
    return round(min(100.0, max(0.0, total)), 1)


def severidade(valor: float) -> str:
    if valor >= 70:
        return "alta"
    if valor >= 45:
        return "media"
    return "baixa"


def score_detector(scores: Iterable[float]) -> float:
    """Força de um detector para um político: o maior achado, mais um bônus pequeno por
    achados repetidos (até +10). Muitos achados fracos não viram um achado forte."""
    lista = sorted(scores, reverse=True)
    if not lista:
        return 0.0
    return min(100.0, lista[0] + min(10.0, 3.0 * (len(lista) - 1)))


def risco(por_detector: Iterable[tuple[float, float]]) -> float:
    """Risco 0-100 a partir de (peso, score) de cada detector: OU probabilístico (noisy-OR).

    Cada detector é tratado como evidência independente com probabilidade peso·score/100;
    o risco é a chance de pelo menos uma ser verdadeira. Indícios de detectores diferentes se
    reforçam; repetir o mesmo detector não (ver `score_detector`).
    """
    nada = 1.0
    for peso, s in por_detector:
        nada *= 1 - min(0.99, max(0.0, peso * s / 100))
    return round(100 * (1 - nada), 1)
