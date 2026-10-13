"""Câmara dos Deputados: deputados/mandatos por legislatura e CEAP (cota parlamentar) por ano.

Fontes:
- API v2 https://dadosabertos.camara.leg.br/api/v2 (legislaturas, deputados por legislatura)
- arquivo bulk deputados.csv (nome civil, nascimento, sexo de todos os deputados da história)
- CEAP anual https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip
"""

import json
from collections.abc import AsyncIterator, Sequence
from datetime import date

from pydantic import BaseModel

from ouroboros.canonical import CpfPessoaRow, DespesaRow, MandatoRow, PessoaRow
from ouroboros.connectors.base import HttpConnector
from ouroboros.core.parse import clean, parse_date, parse_decimal, parse_int, read_csv, zip_members
from ouroboros.core.privacy import cpf_hmac, documento_publico
from ouroboros.core.raw_store import RawRecord
from ouroboros.core.text import normalize
from ouroboros.models.ente import CODIGO_UNIAO, Esfera
from ouroboros.models.mandato import Cargo

API_URL = "https://dadosabertos.camara.leg.br/api/v2"
DEPUTADOS_CSV_URL = "https://dadosabertos.camara.leg.br/arquivos/deputados/csv/deputados.csv"
CEAP_URL = "https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip"

ORIGEM = "camara"


def _id_from_uri(uri: str) -> str:
    return uri.rstrip("/").rsplit("/", 1)[-1]


class CamaraDeputadosConnector(HttpConnector):
    """Partição = número da legislatura (ex.: '57')."""

    fonte = "camara"
    recurso = "deputados"
    base_url = API_URL
    max_calls_per_minute = 120
    headers = {"Accept": "application/json"}

    async def extract(self, particao: str) -> AsyncIterator[RawRecord]:
        async with self.http() as client:
            r = await client.get(f"/legislaturas/{particao}")
            yield self.raw("legislatura", particao, r, "application/json")
            pagina = 1
            while True:
                r = await client.get(
                    "/deputados",
                    params={"idLegislatura": particao, "itens": 100, "pagina": pagina},
                )
                yield self.raw("deputados", particao, r, "application/json")
                if not any(link["rel"] == "next" for link in r.json()["links"]):
                    break
                pagina += 1
            r = await client.get(DEPUTADOS_CSV_URL)
            yield self.raw("deputados_csv", particao, r, "text/csv")

    def transform(self, records: Sequence[RawRecord]) -> Sequence[BaseModel]:
        leg = next(r for r in records if r.recurso == "legislatura")
        leg_dados = json.loads(leg.payload)["dados"]
        legislatura = int(leg_dados["id"])
        inicio, fim = (
            date.fromisoformat(leg_dados["dataInicio"]),
            date.fromisoformat(leg_dados["dataFim"]),
        )

        csv_record = next(r for r in records if r.recurso == "deputados_csv")
        cadastro = {_id_from_uri(row["uri"]): row for row in read_csv(csv_record.payload)}

        # A lista repete o deputado a cada troca de partido no período.
        vistos: dict[str, tuple[RawRecord, list[dict]]] = {}
        for record in records:
            if record.recurso != "deputados":
                continue
            for d in json.loads(record.payload)["dados"]:
                vistos.setdefault(str(d["id"]), (record, []))[1].append(d)

        rows: list[BaseModel] = []
        for id_externo, (record, entradas) in vistos.items():
            ultimo = entradas[-1]
            cad = cadastro.get(id_externo, {})
            lineage = {"fonte": self.fonte, "fonte_url": record.url, "raw_hash": record.sha256}
            rows.append(
                PessoaRow(
                    origem=ORIGEM,
                    id_externo=id_externo,
                    # legislaturas antigas vêm sem nome na lista: usa o cadastro
                    nome=ultimo["nome"] or cad.get("nome") or cad.get("nomeCivil") or id_externo,
                    nome_civil=clean(cad.get("nomeCivil")),
                    data_nascimento=parse_date(cad.get("dataNascimento")),
                    genero=clean(cad.get("siglaSexo")),
                    cpf_hmac=cpf_hmac(cad.get("cpf")),
                    foto_url=ultimo.get("urlFoto"),
                    **lineage,
                )
            )
            rows.append(
                MandatoRow(
                    origem=ORIGEM,
                    id_externo=f"{id_externo}:{legislatura}",
                    pessoa_id_externo=id_externo,
                    cargo=Cargo.DEPUTADO_FEDERAL,
                    esfera=Esfera.FEDERAL,
                    ente_codigo_ibge=CODIGO_UNIAO,
                    uf=ultimo["siglaUf"],
                    partidos=sorted({e["siglaPartido"] for e in entradas if e["siglaPartido"]}),
                    legislatura=legislatura,
                    inicio=inicio,
                    fim=fim,
                    **lineage,
                )
            )
        return rows


class CamaraCeapConnector(HttpConnector):
    """Cota para o Exercício da Atividade Parlamentar. Partição = ano (ex.: '2024')."""

    fonte = "camara"
    recurso = "ceap"
    max_calls_per_minute = 30

    async def extract(self, particao: str) -> AsyncIterator[RawRecord]:
        async with self.http() as client:
            r = await client.get(CEAP_URL.format(ano=particao))
            yield self.raw("ceap", particao, r, "application/zip")

    def transform(self, records: Sequence[RawRecord]) -> Sequence[BaseModel]:
        rows: list[BaseModel] = []
        cpfs: dict[str, CpfPessoaRow] = {}
        for record in records:
            lineage = {"fonte": self.fonte, "fonte_url": record.url, "raw_hash": record.sha256}
            for payload in zip_members(record.payload).values():
                for r in read_csv(payload):
                    id_externo = clean(r["ideCadastro"])
                    valor_liquido = parse_decimal(r["vlrLiquido"])
                    if valor_liquido is None:
                        continue
                    if id_externo and (h := cpf_hmac(r["cpf"])):
                        cpfs[id_externo] = CpfPessoaRow(
                            origem=ORIGEM, id_externo=id_externo, cpf_hmac=h
                        )
                    documento, tipo = documento_publico(r["txtCNPJCPF"])
                    uf = clean(r["sgUF"])
                    rows.append(
                        DespesaRow(
                            verba="CEAP",
                            parlamentar_origem=ORIGEM,
                            parlamentar_id_externo=id_externo,
                            parlamentar_nome=r["txNomeParlamentar"].strip(),
                            parlamentar_nome_normalizado=normalize(r["txNomeParlamentar"]),
                            uf=uf if uf and len(uf) == 2 else None,
                            partido_sigla=clean(r["sgPartido"]),
                            ano=int(r["numAno"]),
                            mes=parse_int(r["numMes"]) or 0,
                            data_emissao=parse_date(r["datEmissao"]),
                            categoria=r["txtDescricao"].strip(),
                            subcategoria=clean(r["txtDescricaoEspecificacao"]),
                            fornecedor_nome=clean(r["txtFornecedor"]),
                            fornecedor_documento=documento,
                            fornecedor_tipo=tipo,
                            documento_numero=clean(r["txtNumero"]),
                            documento_url=clean(r["urlDocumento"]),
                            documento_id_fonte=clean(r["ideDocumento"]),
                            valor_documento=parse_decimal(r["vlrDocumento"]),
                            valor_glosa=parse_decimal(r["vlrGlosa"]),
                            valor_liquido=valor_liquido,
                            **lineage,
                        )
                    )
        return [*rows, *cpfs.values()]
