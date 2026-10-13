"""TSE: candidaturas por eleição (consulta_cand_{ano}.zip).

Traz CPF, nome civil e nascimento de todo candidato: é a base mais forte para ligar a mesma
pessoa entre fontes. Cada SQ_CANDIDATO aparece uma vez por turno; fica a linha do último turno.
"""

from collections.abc import AsyncIterator, Sequence

from pydantic import BaseModel

from ouroboros.canonical import CandidaturaRow, PartidoRow, PessoaRow
from ouroboros.connectors.base import HttpConnector
from ouroboros.core.parse import clean, parse_date, parse_int, read_csv, zip_members
from ouroboros.core.privacy import cpf_hmac
from ouroboros.core.raw_store import RawRecord

CAND_URL = "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_{ano}.zip"

ORIGEM = "tse"
GENERO = {"MASCULINO": "M", "FEMININO": "F"}
ELEITO = {"ELEITO", "ELEITO POR QP", "ELEITO POR MÉDIA"}
UF_INVALIDA = {"BR", "ZZ", "VT"}


def _uf(value: str | None) -> str | None:
    value = clean(value)
    return value if value and len(value) == 2 and value not in UF_INVALIDA else None


class TseCandidatosConnector(HttpConnector):
    """Partição = ano da eleição (ex.: '2022')."""

    fonte = "tse"
    recurso = "candidatos"
    max_calls_per_minute = 30

    async def extract(self, particao: str) -> AsyncIterator[RawRecord]:
        async with self.http() as client:
            r = await client.get(CAND_URL.format(ano=particao))
            yield self.raw("consulta_cand", particao, r, "application/zip")

    def transform(self, records: Sequence[RawRecord]) -> Sequence[BaseModel]:
        ultimo_turno: dict[str, tuple[RawRecord, dict[str, str]]] = {}
        for record in records:
            membros = zip_members(record.payload)
            # o arquivo _BRASIL junta todas as UFs; sem ele, lê UF a UF
            brasil = [n for n in membros if n.upper().endswith("_BRASIL.CSV")]
            for nome in brasil or list(membros):
                for r in read_csv(membros[nome], encoding="latin-1"):
                    sq = r["SQ_CANDIDATO"]
                    atual = ultimo_turno.get(sq)
                    if atual is None or int(r["NR_TURNO"]) >= int(atual[1]["NR_TURNO"]):
                        ultimo_turno[sq] = (record, r)

        pessoas: list[PessoaRow] = []
        candidaturas: list[CandidaturaRow] = []
        partidos: dict[int, PartidoRow] = {}
        for sq, (record, r) in ultimo_turno.items():
            lineage = {"fonte": self.fonte, "fonte_url": record.url, "raw_hash": record.sha256}
            nome_urna = clean(r["NM_URNA_CANDIDATO"]) or r["NM_CANDIDATO"]
            pessoas.append(
                PessoaRow(
                    origem=ORIGEM,
                    id_externo=sq,
                    nome=nome_urna,
                    nome_civil=clean(r["NM_CANDIDATO"]),
                    data_nascimento=parse_date(r["DT_NASCIMENTO"], "%d/%m/%Y"),
                    genero=GENERO.get(r["DS_GENERO"]),
                    cpf_hmac=cpf_hmac(r["NR_CPF_CANDIDATO"]),
                    **lineage,
                )
            )
            partido_numero = parse_int(r["NR_PARTIDO"])
            situacao_turno = clean(r["DS_SIT_TOT_TURNO"])
            candidaturas.append(
                CandidaturaRow(
                    sq_candidato=int(sq),
                    pessoa_id_externo=sq,
                    ano=int(r["ANO_ELEICAO"]),
                    turno=int(r["NR_TURNO"]),
                    cargo=r["DS_CARGO"],
                    cargo_codigo=int(r["CD_CARGO"]),
                    uf=_uf(r["SG_UF"]),
                    ue_codigo_tse=r["SG_UE"],
                    ue_nome=r["NM_UE"],
                    numero_urna=parse_int(r["NR_CANDIDATO"]),
                    nome_urna=nome_urna,
                    partido_numero=partido_numero,
                    partido_sigla=clean(r["SG_PARTIDO"]),
                    situacao_candidatura=clean(r["DS_SITUACAO_CANDIDATURA"]),
                    situacao_turno=situacao_turno,
                    eleito=situacao_turno in ELEITO,
                    **lineage,
                )
            )
            if partido_numero and (sigla := clean(r["SG_PARTIDO"])):
                partidos[partido_numero] = PartidoRow(
                    numero_tse=partido_numero, sigla=sigla, nome=r["NM_PARTIDO"], **lineage
                )
        return [*partidos.values(), *pessoas, *candidaturas]
