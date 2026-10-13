"""Presidência da República: quem exerceu o cargo e quanto a Presidência gastou no cartão
de pagamento (CPGF) em cada período.

- Mandatos: tabela fixa (poucas linhas, raramente muda) com os períodos de exercício efetivo,
  conferidos na galeria oficial de ex-presidentes. Pessoas são ligadas por nome civil + data de
  nascimento do TSE, como as demais fontes.
- 2003-2022: planilha publicada pela Casa Civil em 2023 com os gastos que eram sigilosos
  (todo lançamento tem CDIC, código de informação classificada). Extraída do Suprim, o sistema
  interno, por data de pagamento.
- 2023 em diante: arquivo mensal do CPGF do Portal da Transparência, filtrado no órgão
  Presidência da República (20101), sem a ABIN. Lançamentos ainda sigilosos vêm sem data,
  portador e fornecedor; só o valor.

Os dois não se sobrepõem: o Portal também cobre 2013-2022, mas lá os gastos da Presidência
estão mascarados, e a planilha da Casa Civil tem o detalhe.
"""

import json
import re
from collections.abc import AsyncIterator, Sequence
from datetime import date, timedelta
from decimal import Decimal

import httpx
from pydantic import BaseModel

from ouroboros.canonical import GastoPresidenciaRow, MandatoRow, PessoaRow
from ouroboros.connectors.base import Connector, HttpConnector
from ouroboros.core.http import HttpClient
from ouroboros.core.parse import clean, parse_date, parse_decimal, read_csv, zip_members
from ouroboros.core.privacy import documento_publico
from ouroboros.core.raw_store import RawRecord, RawStore
from ouroboros.models.ente import CODIGO_UNIAO, Esfera
from ouroboros.models.mandato import Cargo

GALERIA_URL = "https://www.biblioteca.presidencia.gov.br/presidencia/ex-presidentes"
HISTORICO_URL = (
    "https://www.gov.br/casacivil/pt-br/acesso-a-informacao/informacoes-classificadas/"
    "informacoes-classificadas-e-desclassificadas-publicadas-ate-23-01-2029-na-sg/"
    "despesas-com-cartao-de-pagamento-do-governo-federal-mandatos-anteriores/"
    "cartao2003-202208032023.csv/@@download/file"
)
CPGF_URL = "https://portaldatransparencia.gov.br/download-de-dados/cpgf/{ano}{mes:02d}"
ORGAO_PRESIDENCIA = "20101"

# Períodos de exercício efetivo (não de diplomação): Dilma afastada em 12/05/2016 pelo
# processo de impeachment; Temer interino a partir daí, efetivo em 31/08/2016.
PRESIDENTES = [
    {
        "id": "lula",
        "nome": "Lula",
        "nome_civil": "Luiz Inácio Lula da Silva",
        # data do registro civil, a mesma do TSE (ele comemora em 27/10)
        "nascimento": "1945-10-06",
        "genero": "M",
        "mandatos": [
            ("lula-2003", "2003-01-01", "2006-12-31", ["PT"], None),
            ("lula-2007", "2007-01-01", "2010-12-31", ["PT"], None),
            ("lula-2023", "2023-01-01", "2026-12-31", ["PT"], None),
        ],
    },
    {
        "id": "dilma",
        "nome": "Dilma Rousseff",
        "nome_civil": "Dilma Vana Rousseff",
        "nascimento": "1947-12-14",
        "genero": "F",
        "mandatos": [
            ("dilma-2011", "2011-01-01", "2014-12-31", ["PT"], None),
            (
                "dilma-2015",
                "2015-01-01",
                "2016-05-11",
                ["PT"],
                "Afastada em 12/05/2016 (impeachment)",
            ),
        ],
    },
    {
        "id": "temer",
        "nome": "Michel Temer",
        "nome_civil": "Michel Miguel Elias Temer Lulia",
        "nascimento": "1940-09-23",
        "genero": "M",
        "mandatos": [
            (
                "temer-2016",
                "2016-05-12",
                "2018-12-31",
                ["PMDB", "MDB"],
                "Interino até 31/08/2016",
            ),
        ],
    },
    {
        "id": "bolsonaro",
        "nome": "Jair Bolsonaro",
        "nome_civil": "Jair Messias Bolsonaro",
        "nascimento": "1955-03-21",
        "genero": "M",
        "mandatos": [("bolsonaro-2019", "2019-01-01", "2022-12-31", ["PSL", "PL"], None)],
    },
]


class PresidentesConnector(Connector):
    """Presidentes da República desde 2003 e seus períodos de exercício"""

    fonte = "presidencia"
    recurso = "mandatos"

    async def extract(self, particao: str) -> AsyncIterator[RawRecord]:
        payload = json.dumps(PRESIDENTES, ensure_ascii=False, sort_keys=True).encode()
        yield RawRecord(
            fonte=self.fonte,
            recurso=self.recurso,
            particao=particao,
            url=GALERIA_URL,
            payload=payload,
        )

    def transform(self, records: Sequence[RawRecord]) -> Sequence[BaseModel]:
        rows: list[BaseModel] = []
        for record in records:
            lineage = {"fonte": self.fonte, "fonte_url": record.url, "raw_hash": record.sha256}
            for p in json.loads(record.payload):
                rows.append(
                    PessoaRow(
                        origem=self.fonte,
                        id_externo=p["id"],
                        nome=p["nome"],
                        nome_civil=p["nome_civil"],
                        data_nascimento=date.fromisoformat(p["nascimento"]),
                        genero=p["genero"],
                        **lineage,
                    )
                )
                for mid, inicio, fim, partidos, condicao in p["mandatos"]:
                    rows.append(
                        MandatoRow(
                            origem=self.fonte,
                            id_externo=mid,
                            pessoa_id_externo=p["id"],
                            cargo=Cargo.PRESIDENTE,
                            esfera=Esfera.FEDERAL,
                            ente_codigo_ibge=CODIGO_UNIAO,
                            uf=None,
                            partidos=partidos,
                            condicao=condicao,
                            inicio=date.fromisoformat(inicio),
                            fim=date.fromisoformat(fim),
                            **lineage,
                        )
                    )
        return rows


# --------------------------------------------------------------------- 2003-2022 (Casa Civil)

_DATA = re.compile(r"^\d{2}/\d{2}/\d{4};")


_LETRAS_PT = set("ÁÀÂÃÉÊÍÓÔÕÚÜÇáàâãéêíóôõúüçºª")
# byte alto -> caractere: cp850 (a maior parte da planilha) quando dá letra do português;
# senão latin-1 (trechos colados de outra origem: 0xC3 = Ã, 0xE7 = ç, que em cp850 seriam ├, þ)
_BYTE = {
    b: (cp850 if (cp850 := bytes([b]).decode("cp850")) in _LETRAS_PT else chr(b))
    for b in range(0x80, 0x100)
}


def decodificar(payload: bytes) -> str:
    """A planilha mistura cp850 ("SÃO" = 53 C7 4F) com latin-1 ("SÃO" = 53 C3 4F)."""
    texto = "".join(_BYTE[b] if b >= 0x80 else chr(b) for b in payload)
    # C7 C7 = Ç em latin-1 seguido de Ã em cp850 ("ALIMENTAÇÃO"); "ÃÃ" não existe em português
    return texto.replace("ÃÃ", "ÇÃ")


def _valor_brl(texto: str) -> Decimal:
    """'R$ 1.696,90', '-R$ 8,33', 'R$ -' (zero)."""
    t = texto.replace("R$", "").replace(" ", "").strip()
    if t in {"", "-"}:
        return Decimal("0")
    return parse_decimal(t) or Decimal("0")


def _documento_historico(texto: str) -> str | None:
    """A planilha foi salva pelo Excel: CNPJ virou '3,13492E+13' (perdido). Sobra CPF (11
    dígitos, sai mascarado) e o raro CNPJ que escapou com 14 dígitos."""
    d = texto.strip()
    if not re.fullmatch(r"\d{11}|\d{14}", d):
        return None
    return documento_publico(d)[0]


class CartaoHistoricoConnector(HttpConnector):
    """Cartão de pagamento da Presidência 2003-2022 (gastos antes sigilosos, Casa Civil)"""

    fonte = "casacivil"
    recurso = "cartao_presidencia"
    headers = {"Accept": "text/csv,*/*"}

    async def extract(self, particao: str) -> AsyncIterator[RawRecord]:
        async with self.http() as client:
            r = await client.get(HISTORICO_URL)
        yield self.raw(self.recurso, particao, r, "text/csv")

    def transform(self, records: Sequence[RawRecord]) -> Sequence[BaseModel]:
        rows: list[GastoPresidenciaRow] = []
        for record in records:
            lineage = {"fonte": self.fonte, "fonte_url": record.url, "raw_hash": record.sha256}
            for linha in decodificar(record.payload).splitlines():
                # cabeçalho e glossário (antes e depois dos dados) não começam com data
                if not _DATA.match(linha):
                    continue
                c = (linha.split(";") + [""] * 8)[:8]
                data = parse_date(c[0], "%d/%m/%Y")
                if data is None:
                    continue
                rows.append(
                    GastoPresidenciaRow(
                        data=data,
                        ano=data.year,
                        mes=data.month,
                        unidade_gestora=None,
                        portador=clean(c[1]),
                        favorecido_documento=_documento_historico(c[2]),
                        favorecido_nome=clean(c[3]),
                        valor=_valor_brl(c[4]),
                        tipo="saque" if c[5].strip().upper() == "D" else "credito",
                        categoria=clean(c[6]),
                        transacao=None,
                        sigiloso=bool(clean(c[7])),
                        classificacao=clean(c[7]),
                        **lineage,
                    )
                )
        return rows


# --------------------------------------------------------------------- 2023+ (Portal CPGF)

_SEM_INFO = {"-1", "-11", "SEM INFORMACAO", "Sigiloso"}


def _txt(value: str | None) -> str | None:
    value = clean(value)
    return None if value is None or value in _SEM_INFO else value


class CpgfPresidenciaConnector(HttpConnector):
    """Cartão de pagamento da Presidência no Portal da Transparência (um ZIP por mês)"""

    fonte = "transparencia"
    recurso = "cpgf_presidencia"
    # o Portal bloqueia rajadas (405 em tudo por alguns minutos)
    max_calls_per_minute = 6

    def __init__(self, client: HttpClient | None = None, store: RawStore | None = None) -> None:
        super().__init__(client)
        self._store = store or RawStore()

    def _guardado(self, recurso: str, particao: str) -> RawRecord | None:
        """ZIP de mês já baixado. O Portal bloqueia (405) depois de ~20 downloads, então mês
        fechado não é baixado de novo a cada execução."""
        pasta = self._store.root / self.fonte / recurso / particao
        arquivos = sorted(pasta.glob("*.zip"), key=lambda p: p.stat().st_mtime)
        if not arquivos:
            return None
        ano, mes = int(recurso[-6:-2]), int(recurso[-2:])
        return RawRecord(
            fonte=self.fonte,
            recurso=recurso,
            particao=particao,
            url=CPGF_URL.format(ano=ano, mes=mes),
            payload=arquivos[-1].read_bytes(),
            content_type="application/zip",
        )

    async def extract(self, particao: str) -> AsyncIterator[RawRecord]:
        ano = int(particao)
        hoje = date.today()
        # o Portal ainda corrige os meses recentes; três meses depois o arquivo não muda mais
        fechado = date(hoje.year, hoje.month, 1) - timedelta(days=90)
        async with self.http() as client:
            for mes in range(1, 13):
                if (ano, mes) > (hoje.year, hoje.month):
                    break
                recurso = f"cpgf_{ano}{mes:02d}"
                if (ano, mes) < (fechado.year, fechado.month) and self._client is None:
                    guardado = self._guardado(recurso, particao)
                    if guardado is not None:
                        yield guardado
                        continue
                try:
                    r = await client.get(CPGF_URL.format(ano=ano, mes=mes))
                except httpx.HTTPStatusError as exc:
                    # mês ainda não publicado: 403/404. Bloqueio por excesso (405) falha o job,
                    # para não gravar o ano sem os meses que faltaram.
                    if exc.response.status_code in (403, 404):
                        continue
                    raise
                yield self.raw(recurso, particao, r, "application/zip")

    def transform(self, records: Sequence[RawRecord]) -> Sequence[BaseModel]:
        rows: list[GastoPresidenciaRow] = []
        for record in records:
            lineage = {"fonte": self.fonte, "fonte_url": record.url, "raw_hash": record.sha256}
            for dados in zip_members(record.payload).values():
                for r in read_csv(dados, encoding="latin-1"):
                    if r["CÓDIGO ÓRGÃO"].strip() != ORGAO_PRESIDENCIA:
                        continue
                    # ABIN aparece no órgão Presidência, mas é cartão de inteligência, não da
                    # Presidência em si (e não está na planilha 2003-2022): misturar inflaria
                    # a comparação entre presidentes
                    if "INTELIGENCIA" in r["NOME UNIDADE GESTORA"].upper():
                        continue
                    valor = parse_decimal(r["VALOR TRANSAÇÃO"])
                    if valor is None:
                        continue
                    sigiloso = r["NOME PORTADOR"].strip() == "Sigiloso"
                    data = parse_date(r["DATA TRANSAÇÃO"], "%d/%m/%Y")
                    doc = _txt(r["CNPJ OU CPF FAVORECIDO"])
                    transacao = _txt(r["TRANSAÇÃO"])
                    rows.append(
                        GastoPresidenciaRow(
                            data=data,
                            # sem data (sigiloso): vale o mês do extrato
                            ano=int(r["ANO EXTRATO"]),
                            mes=int(r["MÊS EXTRATO"]),
                            unidade_gestora=_txt(r["NOME UNIDADE GESTORA"]),
                            portador=_txt(r["CPF PORTADOR"]),
                            favorecido_documento=documento_publico(doc)[0] if doc else None,
                            favorecido_nome=_txt(r["NOME FAVORECIDO"]),
                            valor=valor,
                            tipo="saque" if "SAQUE" in (transacao or "").upper() else "credito",
                            categoria=None,
                            transacao=transacao,
                            sigiloso=sigiloso,
                            classificacao=None,
                            **lineage,
                        )
                    )
        return rows
