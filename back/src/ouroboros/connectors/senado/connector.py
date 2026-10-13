"""Senado Federal: senadores/mandatos por legislatura e CEAPS por ano.

Fontes:
- API https://legis.senado.leg.br/dadosabertos (lista por legislatura + detalhe do senador)
- CEAPS https://www.senado.leg.br/transparencia/LAI/verba/despesa_ceaps_{ano}.csv

O JSON do Senado é conversão de XML: campo com um item vem como objeto, com vários vem como
lista. Sempre passar por `_lista`.

Limitação conhecida: o CEAPS identifica o senador só pelo nome parlamentar (sem código);
a ligação é feita por nome normalizado contra os senadores carregados.
"""

import json
from collections.abc import AsyncIterator, Sequence
from datetime import date
from typing import Any

from pydantic import BaseModel

from ouroboros.canonical import DespesaRow, MandatoRow, PessoaRow
from ouroboros.connectors.base import HttpConnector
from ouroboros.core.parse import clean, parse_date, parse_decimal, parse_int, read_csv
from ouroboros.core.privacy import documento_publico
from ouroboros.core.raw_store import RawRecord
from ouroboros.core.text import normalize
from ouroboros.models.ente import CODIGO_UNIAO, Esfera
from ouroboros.models.mandato import Cargo

API_URL = "https://legis.senado.leg.br/dadosabertos"
CEAPS_URL = "https://www.senado.leg.br/transparencia/LAI/verba/despesa_ceaps_{ano}.csv"

ORIGEM = "senado"
GENERO = {"Masculino": "M", "Feminino": "F"}


def _lista(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _exercicios(mandato: dict[str, Any]) -> list[dict[str, Any]]:
    return _lista((mandato.get("Exercicios") or {}).get("Exercicio"))


def _parlamentares(lista_payload: bytes) -> list[dict[str, Any]]:
    data = json.loads(lista_payload)["ListaParlamentarLegislatura"]
    return _lista((data.get("Parlamentares") or {}).get("Parlamentar"))


class SenadoSenadoresConnector(HttpConnector):
    """Partição = número da legislatura (ex.: '57'). Só entra quem exerceu o mandato."""

    fonte = "senado"
    recurso = "senadores"
    base_url = API_URL
    max_calls_per_minute = 120
    headers = {"Accept": "application/json"}

    async def extract(self, particao: str) -> AsyncIterator[RawRecord]:
        async with self.http() as client:
            r = await client.get(f"/senador/lista/legislatura/{particao}")
            yield self.raw("lista", particao, r, "application/json")
            codigos = sorted(
                {
                    p["IdentificacaoParlamentar"]["CodigoParlamentar"]
                    for p in _parlamentares(r.content)
                    if any(_exercicios(m) for m in _lista(p["Mandatos"]["Mandato"]))
                }
            )
            for codigo in codigos:
                r = await client.get(f"/senador/{codigo}")
                yield self.raw("senador", particao, r, "application/json")

    def transform(self, records: Sequence[RawRecord]) -> Sequence[BaseModel]:
        detalhes: dict[str, dict[str, Any]] = {}
        for record in records:
            if record.recurso == "senador":
                p = json.loads(record.payload)["DetalheParlamentar"]["Parlamentar"]
                detalhes[p["IdentificacaoParlamentar"]["CodigoParlamentar"]] = p

        lista = next(r for r in records if r.recurso == "lista")
        lineage = {"fonte": self.fonte, "fonte_url": lista.url, "raw_hash": lista.sha256}
        hoje = date.today()
        pessoas: dict[str, PessoaRow] = {}
        mandatos: list[MandatoRow] = []
        for p in _parlamentares(lista.payload):
            ident = p["IdentificacaoParlamentar"]
            codigo = ident["CodigoParlamentar"]
            det = detalhes.get(codigo, {})
            det_ident = det.get("IdentificacaoParlamentar", {})
            for m in _lista(p["Mandatos"]["Mandato"]):
                exercicios = _exercicios(m)
                if not exercicios:
                    continue  # suplente que não assumiu
                legs = [
                    leg
                    for leg in (
                        m.get("PrimeiraLegislaturaDoMandato"),
                        m.get("SegundaLegislaturaDoMandato"),
                    )
                    if leg
                ]
                fim_mandato = max(date.fromisoformat(leg["DataFim"]) for leg in legs)
                inicios = [parse_date(e.get("DataInicio")) for e in exercicios]
                fins = [parse_date(e.get("DataFim")) for e in exercicios]
                fim = fim_mandato if any(f is None for f in fins) else max(fins)
                # API só informa o partido atual; vale apenas para mandato em curso.
                partido = det_ident.get("SiglaPartidoParlamentar") if fim >= hoje else None
                mandatos.append(
                    MandatoRow(
                        origem=ORIGEM,
                        id_externo=f"{m['CodigoMandato']}:{codigo}",
                        pessoa_id_externo=codigo,
                        cargo=Cargo.SENADOR,
                        esfera=Esfera.FEDERAL,
                        ente_codigo_ibge=CODIGO_UNIAO,
                        uf=m.get("UfParlamentar"),
                        partidos=[partido] if partido else [],
                        legislatura=int(legs[0]["NumeroLegislatura"]),
                        condicao=m.get("DescricaoParticipacao"),
                        inicio=min(i for i in inicios if i) if any(inicios) else None,
                        fim=fim,
                        **lineage,
                    )
                )
                pessoas[codigo] = PessoaRow(
                    origem=ORIGEM,
                    id_externo=codigo,
                    nome=ident["NomeParlamentar"],
                    nome_civil=ident.get("NomeCompletoParlamentar"),
                    data_nascimento=parse_date(
                        det.get("DadosBasicosParlamentar", {}).get("DataNascimento")
                    ),
                    genero=GENERO.get(ident.get("SexoParlamentar", "")),
                    foto_url=det_ident.get("UrlFotoParlamentar"),
                    **lineage,
                )
        return [*pessoas.values(), *mandatos]


class SenadoCeapsConnector(HttpConnector):
    """Cota para o Exercício da Atividade Parlamentar dos Senadores. Partição = ano."""

    fonte = "senado"
    recurso = "ceaps"
    max_calls_per_minute = 30

    async def extract(self, particao: str) -> AsyncIterator[RawRecord]:
        async with self.http() as client:
            r = await client.get(CEAPS_URL.format(ano=particao))
            yield self.raw("ceaps", particao, r, "text/csv")

    def transform(self, records: Sequence[RawRecord]) -> Sequence[BaseModel]:
        rows: list[BaseModel] = []
        for record in records:
            lineage = {"fonte": self.fonte, "fonte_url": record.url, "raw_hash": record.sha256}
            # 1ª linha: "ULTIMA ATUALIZACAO";"<data>"
            for r in read_csv(record.payload, encoding="latin-1", skip_lines=1):
                valor = parse_decimal(r["VALOR_REEMBOLSADO"])
                if valor is None:
                    continue
                documento, tipo = documento_publico(r["CNPJ_CPF"])
                rows.append(
                    DespesaRow(
                        verba="CEAPS",
                        parlamentar_origem=ORIGEM,
                        parlamentar_id_externo=None,
                        parlamentar_nome=r["SENADOR"].strip(),
                        parlamentar_nome_normalizado=normalize(r["SENADOR"]),
                        uf=None,
                        partido_sigla=None,
                        ano=int(r["ANO"]),
                        mes=parse_int(r["MES"]) or 0,
                        data_emissao=parse_date(r["DATA"], "%d/%m/%Y"),
                        categoria=r["TIPO_DESPESA"].strip(),
                        subcategoria=clean(r["DETALHAMENTO"]),
                        fornecedor_nome=clean(r["FORNECEDOR"]),
                        fornecedor_documento=documento,
                        fornecedor_tipo=tipo,
                        documento_numero=clean(r["DOCUMENTO"]),
                        documento_url=None,
                        documento_id_fonte=clean(r["COD_DOCUMENTO"]),
                        valor_documento=None,
                        valor_glosa=None,
                        valor_liquido=valor,
                        **lineage,
                    )
                )
        return rows
