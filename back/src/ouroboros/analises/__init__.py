"""Análise reversa: parte do dinheiro (notas, emendas) para apontar indícios de fraude e
desvio, com evidência e metodologia em cada alerta. Ver `detectores.py`."""

from ouroboros.analises.detectores import CATALOGO, Detector
from ouroboros.analises.executar import gerar_alertas

__all__ = ["CATALOGO", "Detector", "gerar_alertas"]
