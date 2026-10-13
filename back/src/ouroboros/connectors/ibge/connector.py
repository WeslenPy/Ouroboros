from collections.abc import AsyncIterator, Sequence

from pydantic import TypeAdapter

from ouroboros.canonical import EnteRow
from ouroboros.connectors.base import HttpConnector
from ouroboros.connectors.ibge.schemas import UF, Municipio
from ouroboros.core.raw_store import RawRecord
from ouroboros.core.text import normalize
from ouroboros.models.ente import CODIGO_UNIAO, Esfera

BASE_URL = "https://servicodados.ibge.gov.br/api/v1/localidades"
RECURSOS = {"estados": "/estados", "municipios": "/municipios"}

_ufs = TypeAdapter(list[UF])
_municipios = TypeAdapter(list[Municipio])


class IbgeConnector(HttpConnector):
    """Tabela mestre de entes federativos.

    Partição única ("atual"): o IBGE só publica a divisão territorial vigente.
    """

    fonte = "ibge"
    recurso = "entes"
    base_url = BASE_URL

    async def extract(self, particao: str = "atual") -> AsyncIterator[RawRecord]:
        async with self.http() as client:
            for recurso, path in RECURSOS.items():
                yield self.raw(recurso, particao, await client.get(path), "application/json")

    def transform(self, records: Sequence[RawRecord]) -> Sequence[EnteRow]:
        rows: list[EnteRow] = []
        for record in records:
            lineage = {"fonte": self.fonte, "fonte_url": record.url, "raw_hash": record.sha256}
            if record.recurso == "estados":
                rows.append(
                    EnteRow(
                        codigo_ibge=CODIGO_UNIAO,
                        nome="União",
                        nome_normalizado=normalize("União"),
                        esfera=Esfera.FEDERAL,
                        uf=None,
                        uf_codigo=None,
                        regiao=None,
                        **lineage,
                    )
                )
                rows += [
                    EnteRow(
                        codigo_ibge=uf.id,
                        nome=uf.nome,
                        nome_normalizado=normalize(uf.nome),
                        esfera=Esfera.ESTADUAL,
                        uf=uf.sigla,
                        uf_codigo=uf.id,
                        regiao=uf.regiao.nome,
                        **lineage,
                    )
                    for uf in _ufs.validate_json(record.payload)
                ]
            elif record.recurso == "municipios":
                rows += [
                    EnteRow(
                        codigo_ibge=m.id,
                        nome=m.nome,
                        nome_normalizado=normalize(m.nome),
                        esfera=Esfera.MUNICIPAL,
                        uf=m.uf.sigla,
                        uf_codigo=m.uf.id,
                        regiao=m.uf.regiao.nome,
                        **lineage,
                    )
                    for m in _municipios.validate_json(record.payload)
                ]
            else:
                raise ValueError(f"recurso IBGE desconhecido: {record.recurso}")
        return rows
