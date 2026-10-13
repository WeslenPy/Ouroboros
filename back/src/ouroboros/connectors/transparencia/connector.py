"""Portal da Transparência (CGU): emendas parlamentares ao orçamento federal.

Fonte: download público, sem chave de API, com todos os anos num ZIP só
https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares/UNICO

- EmendasParlamentares.csv: uma linha por emenda x localidade x ação, valores acumulados
  (empenhado, liquidado, pago, restos a pagar).
- EmendasParlamentares_PorFavorecido.csv: pagamentos por favorecido (CNPJ/CPF) e mês.
- EmendasParlamentares_Convenios.csv: convênios firmados com a emenda (convenente, objeto).

Partição = ano (da emenda; do pagamento no arquivo por favorecido). O ZIP é o mesmo para
todas as partições: cada uma filtra o seu ano, e o download é reaproveitado no processo.

Autor vem só como código CGU + nome parlamentar em maiúsculas ("JANDIRA FEGHALI"); a ligação
ao político é por nome contra Câmara e Senado (ver loaders.relink_emendas).
"""

import re
from collections.abc import AsyncIterator, Sequence
from datetime import date
from decimal import Decimal
from typing import ClassVar

from httpx import Response
from pydantic import BaseModel

from ouroboros.canonical import EmendaConvenioRow, EmendaFavorecidoRow, EmendaRow
from ouroboros.connectors.base import HttpConnector
from ouroboros.core.parse import (
    clean,
    parse_date,
    parse_decimal,
    parse_int,
    read_csv,
    zip_members,
)
from ouroboros.core.privacy import documento_publico
from ouroboros.core.raw_store import RawRecord
from ouroboros.core.text import normalize

DOWNLOAD_URL = "https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares/UNICO"

# "Código UF IBGE" vem como 3300000 (código da UF x 100000)
UF_POR_CODIGO = {
    11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO",
    21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL", 28: "SE", 29: "BA",
    31: "MG", 32: "ES", 33: "RJ", 35: "SP",
    41: "PR", 42: "SC", 43: "RS",
    50: "MS", 51: "MT", 52: "GO", 53: "DF",
}  # fmt: skip

# Valores que a fonte usa para "não se aplica"
_SEM = {"S/I", "Sem informação", "Sem informacao", "-1", "-2", "-99"}


def _txt(value: str | None) -> str | None:
    value = clean(value)
    return None if value is None or value in _SEM else value


def _valor(value: str | None) -> Decimal:
    return parse_decimal(value) or Decimal("0")


def _uf(codigo: str | None) -> str | None:
    n = parse_int(codigo)
    if not n:
        return None
    return UF_POR_CODIGO.get(n // 100000 if n >= 100000 else n)


def _documento(value: str | None) -> tuple[str | None, str | None]:
    """CPF já vem mascarado pela fonte (***.638.223-**); CNPJ completo."""
    value = (value or "").strip()
    if "*" in value:
        return value, "pf"
    return documento_publico(value)


_TITULO = re.compile(r"^(dep|sen|deputad[oa]|senador[a]?)\.?\s+")


def _autor(codigo: str | None, nome: str | None) -> tuple[str | None, str, str]:
    """Nome normalizado sem título ("DEP. JOSIVALDO JP" -> "josivaldo jp") para casar com o
    nome parlamentar."""
    nome = _txt(nome) or "Sem informação"
    return _txt(codigo), nome, _TITULO.sub("", normalize(nome))


class TransparenciaEmendasConnector(HttpConnector):
    """Emendas parlamentares (Portal da Transparência): destino, área e pagamentos por favorecido"""

    fonte = "transparencia"
    recurso = "emendas"
    max_calls_per_minute = 10

    # (url, dia) -> resposta: rodar todos os anos baixa o ZIP (~30 MB) uma vez só
    _cache: ClassVar[dict[tuple[str, date], Response]] = {}

    async def extract(self, particao: str) -> AsyncIterator[RawRecord]:
        chave = (DOWNLOAD_URL, date.today())
        r = self._cache.get(chave) if self._client is None else None
        if r is None:
            async with self.http() as client:
                r = await client.get(DOWNLOAD_URL)
            if self._client is None:
                self._cache.clear()
                self._cache[chave] = r
        yield self.raw("emendas_zip", particao, r, "application/zip")

    def transform(self, records: Sequence[RawRecord]) -> Sequence[BaseModel]:
        rows: list[BaseModel] = []
        for record in records:
            lineage = {"fonte": self.fonte, "fonte_url": record.url, "raw_hash": record.sha256}
            ano = int(record.particao)
            membros = zip_members(record.payload)
            emendas = next((v for k, v in membros.items() if k.endswith("Parlamentares.csv")), b"")
            favorecidos = next((v for k, v in membros.items() if "PorFavorecido" in k), b"")
            rows.extend(self._emendas(emendas, ano, lineage))
            rows.extend(self._favorecidos(favorecidos, ano, lineage))
            convenios = next((v for k, v in membros.items() if "Convenios" in k), b"")
            rows.extend(self._convenios(convenios, ano, lineage))
        return rows

    @staticmethod
    def _convenios(data: bytes, ano: int, lineage: dict) -> list[EmendaConvenioRow]:
        """Ano vem dos 4 primeiros dígitos do código da emenda (não há coluna de ano)."""
        out: list[EmendaConvenioRow] = []
        prefixo = str(ano)
        for r in read_csv(data, encoding="latin-1"):
            codigo = r["Código da Emenda"].strip()
            if not codigo.startswith(prefixo):
                continue
            out.append(
                EmendaConvenioRow(
                    emenda_codigo=codigo,
                    ano=ano,
                    tipo=_txt(r["Tipo de Emenda"]),
                    funcao=_txt(r["Nome Função"]),
                    subfuncao=_txt(r["Nome Subfunção"]),
                    localidade=_txt(r["Localidade do gasto"]),
                    data_publicacao=parse_date(r["Data Publicação Convênio"], "%d/%m/%Y"),
                    convenente=_txt(r["Convenente"]),
                    objeto=_txt(r["Objeto Convênio"]),
                    numero=_txt(r["Número Convênio"]),
                    valor=_valor(r["Valor Convênio"]),
                    **lineage,
                )
            )
        return out

    @staticmethod
    def _emendas(data: bytes, ano: int, lineage: dict) -> list[EmendaRow]:
        out: list[EmendaRow] = []
        for r in read_csv(data, encoding="latin-1"):
            if parse_int(r["Ano da Emenda"]) != ano:
                continue
            autor_codigo, autor_nome, autor_norm = _autor(
                r["Código do Autor da Emenda"], r["Nome do Autor da Emenda"]
            )
            out.append(
                EmendaRow(
                    codigo=r["Código da Emenda"].strip(),
                    ano=ano,
                    tipo=r["Tipo de Emenda"].strip(),
                    numero=_txt(r["Número da emenda"]),
                    autor_codigo=autor_codigo,
                    autor_nome=autor_nome,
                    autor_nome_normalizado=autor_norm,
                    localidade=_txt(r["Localidade de aplicação do recurso"]),
                    municipio_codigo_ibge=parse_int(_txt(r["Código Município IBGE"])),
                    municipio_nome=_txt(r["Município"]),
                    uf=_uf(r["Código UF IBGE"]),
                    regiao=_txt(r["Região"]),
                    funcao=_txt(r["Nome Função"]),
                    subfuncao=_txt(r["Nome Subfunção"]),
                    programa=_txt(r["Nome Programa"]),
                    acao=_txt(r["Nome Ação"]),
                    valor_empenhado=_valor(r["Valor Empenhado"]),
                    valor_liquidado=_valor(r["Valor Liquidado"]),
                    valor_pago=_valor(r["Valor Pago"]),
                    valor_rp_inscrito=_valor(r["Valor Restos A Pagar Inscritos"]),
                    valor_rp_cancelado=_valor(r["Valor Restos A Pagar Cancelados"]),
                    valor_rp_pago=_valor(r["Valor Restos A Pagar Pagos"]),
                    **lineage,
                )
            )
        return out

    @staticmethod
    def _favorecidos(data: bytes, ano: int, lineage: dict) -> list[EmendaFavorecidoRow]:
        out: list[EmendaFavorecidoRow] = []
        prefixo = str(ano)
        for r in read_csv(data, encoding="latin-1"):
            ano_mes = r["Ano/Mês"].strip()
            if not ano_mes.startswith(prefixo):
                continue
            valor = parse_decimal(r["Valor Recebido"])
            if valor is None:
                continue
            autor_codigo, autor_nome, autor_norm = _autor(
                r["Código do Autor da Emenda"], r["Nome do Autor da Emenda"]
            )
            documento, _ = _documento(r["Código do Favorecido"])
            out.append(
                EmendaFavorecidoRow(
                    emenda_codigo=r["Código da Emenda"].strip(),
                    ano=ano,
                    mes=parse_int(ano_mes[4:6]) or 0,
                    tipo=r["Tipo de Emenda"].strip(),
                    autor_codigo=autor_codigo,
                    autor_nome=autor_nome,
                    autor_nome_normalizado=autor_norm,
                    favorecido_documento=documento,
                    favorecido_nome=(r["Favorecido"] or "").strip() or "Sem informação",
                    favorecido_tipo=_txt(r["Tipo Favorecido"]),
                    natureza_juridica=_txt(r["Natureza Jurídica"]),
                    uf=_txt(r["UF Favorecido"]),
                    municipio_nome=_txt(r["Município Favorecido"]),
                    valor=valor,
                    **lineage,
                )
            )
        return out
