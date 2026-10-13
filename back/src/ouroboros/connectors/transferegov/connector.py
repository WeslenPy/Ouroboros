"""Transferegov: transferências especiais ("emendas Pix", EC 105/2019).

Fonte: API PostgREST pública, sem chave
https://api.transferegov.gestao.gov.br/transferenciasespeciais

O Portal da Transparência diz quanto foi pago e a quem; aqui está o que o ente prometeu fazer
com o dinheiro. Tabelas usadas:

- plano_acao_especial: um plano por emenda x beneficiário (estado/município), com áreas e valor.
- executor_especial: quem executa e o objeto ("Pavimentação de vias no bairro X").
- finalidade_especial: áreas de cada executor (Urbanismo / Infraestrutura urbana).
- meta_especial: metas físicas do executor, com valor e quantidade.
- empenho_especial: empenhos (reserva no orçamento) por plano.
- documento_habil_especial: transferências efetivas (TF) por empenho.

Partição única ("atual"): a API não filtra bem por ano e o volume é pequeno (~500 mil linhas).
"""

import json
from collections.abc import AsyncIterator, Iterator, Sequence
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from ouroboros.canonical import (
    TransferenciaEspecialEmpenhoRow,
    TransferenciaEspecialExecutorRow,
    TransferenciaEspecialMetaRow,
    TransferenciaEspecialPagamentoRow,
    TransferenciaEspecialRow,
)
from ouroboros.connectors.base import HttpConnector
from ouroboros.core.parse import clean, parse_date
from ouroboros.core.privacy import digits
from ouroboros.core.raw_store import RawRecord
from ouroboros.core.text import normalize

API_URL = "https://api.transferegov.gestao.gov.br/transferenciasespeciais"
PAGINA = 10000

# tabela -> chave de ordenação (paginação estável)
TABELAS = {
    "plano_acao_especial": "id_plano_acao",
    "executor_especial": "id_executor",
    "finalidade_especial": "id_executor,cd_area_politica_publica_pt",
    "meta_especial": "id_meta",
    "empenho_especial": "id_empenho",
    "documento_habil_especial": "id_dh",
}


def _valor(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01")) if value is not None else Decimal("0")


def _texto(value: Any) -> str | None:
    return clean(str(value)) if value is not None else None


def _cnpj(value: Any) -> str | None:
    d = digits(str(value or ""))
    return d if len(d) == 14 else None


def _areas(texto: str | None) -> list[str]:
    """'10-Saúde / 302-Assistência..., 15-Urbanismo / 451-...' -> ['Saúde', 'Urbanismo']."""
    out: list[str] = []
    for parte in (texto or "").split(","):
        funcao = parte.split("/")[0].strip()
        nome = funcao.split("-", 1)[-1].strip()
        if nome and nome not in out:
            out.append(nome)
    return out


def _linhas(records: Sequence[RawRecord], tabela: str) -> Iterator[tuple[RawRecord, dict]]:
    for record in records:
        if record.recurso == tabela:
            for linha in json.loads(record.payload):
                yield record, linha


class TransferegovEspeciaisConnector(HttpConnector):
    """Transferências especiais (emendas Pix): plano de ação, executor, metas e pagamentos"""

    fonte = "transferegov"
    recurso = "especiais"
    base_url = API_URL
    max_calls_per_minute = 60
    headers = {"Accept": "application/json"}

    async def extract(self, particao: str) -> AsyncIterator[RawRecord]:
        async with self.http() as client:
            for tabela, ordem in TABELAS.items():
                offset = 0
                while True:
                    r = await client.get(
                        f"/{tabela}", params={"order": ordem, "limit": PAGINA, "offset": offset}
                    )
                    yield self.raw(tabela, particao, r, "application/json")
                    if len(r.json()) < PAGINA:
                        break
                    offset += PAGINA

    def transform(self, records: Sequence[RawRecord]) -> Sequence[BaseModel]:
        def lineage(record: RawRecord) -> dict:
            return {"fonte": self.fonte, "fonte_url": record.url, "raw_hash": record.sha256}

        rows: list[BaseModel] = []
        for record, p in _linhas(records, "plano_acao_especial"):
            areas = _texto(p.get("codigo_descricao_areas_politicas_publicas_plano_acao"))
            nome = _texto(p.get("nome_parlamentar_emenda_plano_acao")) or "Sem informação"
            rows.append(
                TransferenciaEspecialRow(
                    id=p["id_plano_acao"],
                    codigo=p["codigo_plano_acao"],
                    ano=p["ano_plano_acao"],
                    situacao=_texto(p.get("situacao_plano_acao")),
                    emenda_codigo=_texto(p.get("numero_emenda_parlamentar_plano_acao")),
                    parlamentar_codigo=_texto(p.get("codigo_parlamentar_emenda_plano_acao")),
                    parlamentar_nome=nome,
                    parlamentar_nome_normalizado=normalize(nome),
                    beneficiario_cnpj=_cnpj(p.get("cnpj_beneficiario_plano_acao")),
                    beneficiario_nome=_texto(p.get("nome_beneficiario_plano_acao"))
                    or "Sem informação",
                    uf=_texto(p.get("uf_beneficiario_plano_acao")),
                    areas=areas,
                    funcao=next(iter(_areas(areas)), None),
                    motivo_impedimento=_texto(p.get("motivo_impedimento_plano_acao")),
                    valor_custeio=_valor(p.get("valor_custeio_plano_acao")),
                    valor_investimento=_valor(p.get("valor_investimento_plano_acao")),
                    **lineage(record),
                )
            )

        areas_executor: dict[int, list[str]] = {}
        for _, f in _linhas(records, "finalidade_especial"):
            area = _texto(f.get("area_politica_publica_tipo_pt"))
            lista = areas_executor.setdefault(f["id_executor"], [])
            if area and area not in lista:
                lista.append(area)

        for record, e in _linhas(records, "executor_especial"):
            rows.append(
                TransferenciaEspecialExecutorRow(
                    id=e["id_executor"],
                    plano_id=e["id_plano_acao"],
                    cnpj=_cnpj(e.get("cnpj_executor")),
                    nome=_texto(e.get("nome_executor")) or "Sem informação",
                    objeto=_texto(e.get("objeto_executor")),
                    areas=areas_executor.get(e["id_executor"], []),
                    valor_custeio=_valor(e.get("vl_custeio_executor")),
                    valor_investimento=_valor(e.get("vl_investimento_executor")),
                    **lineage(record),
                )
            )

        for record, m in _linhas(records, "meta_especial"):
            qtd = m.get("qt_uniade_meta")  # sic: nome do campo na fonte
            rows.append(
                TransferenciaEspecialMetaRow(
                    id=m["id_meta"],
                    executor_id=m["id_executor"],
                    sequencial=m.get("sequencial_meta"),
                    nome=_texto(m.get("nome_meta")),
                    descricao=_texto(m.get("desc_meta")),
                    unidade=(_texto(m.get("un_medida_meta")) or "")[:40] or None,
                    quantidade=Decimal(str(qtd)) if qtd is not None else None,
                    meses=m.get("qt_meses_meta"),
                    valor_custeio=_valor(m.get("vl_custeio_emenda_especial_meta")),
                    valor_investimento=_valor(m.get("vl_investimento_emenda_especial_meta")),
                    **lineage(record),
                )
            )

        plano_do_empenho: dict[int, int | None] = {}
        for record, e in _linhas(records, "empenho_especial"):
            plano_do_empenho[e["id_empenho"]] = e.get("id_plano_acao")
            rows.append(
                TransferenciaEspecialEmpenhoRow(
                    id=e["id_empenho"],
                    plano_id=e.get("id_plano_acao"),
                    numero=_texto(e.get("numero_empenho")),
                    situacao=_texto(e.get("descricao_situacao_empenho")),
                    data_emissao=parse_date(e.get("data_emissao_empenho")),
                    valor=_valor(e.get("valor_empenho")),
                    **lineage(record),
                )
            )

        for record, d in _linhas(records, "documento_habil_especial"):
            empenho = d.get("id_empenho")
            rows.append(
                TransferenciaEspecialPagamentoRow(
                    id=d["id_dh"],
                    empenho_id=empenho,
                    plano_id=plano_do_empenho.get(empenho) if empenho else None,
                    numero=_texto(d.get("numero_documento_habil")),
                    situacao=_texto(d.get("descricao_situacao_dh")),
                    data_emissao=parse_date(d.get("data_emissao_dh")),
                    valor=_valor(d.get("valor_dh")),
                    **lineage(record),
                )
            )
        return rows
