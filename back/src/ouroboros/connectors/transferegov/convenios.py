"""Transferegov discricionárias (antigo Siconv): convênios, emendas, obras e pagamentos.

Fonte: download público, sem chave, atualizado diariamente pelo Ministério da Gestão
https://repositorio.dados.gov.br/seges/detru/ (dicionário em modelo_dados_siconv.zip)

Um arquivo por tabela; usados aqui:

- siconv_convenio: situação, vigência, valores (global, repasse, empenhado, desembolsado).
- siconv_proposta: convenente, município (código IBGE), órgão concedente, objeto.
- siconv_emenda: emendas que financiam a proposta. NR_EMENDA (8 dígitos) + ano do programa
  (dígitos 6-9 de COD_PROGRAMA_EMENDA) = código da emenda no Portal da Transparência.
- siconv_meta_crono_fisico: metas com endereço, CEP e datas previstas.
- siconv_desembolso: liberações da União para a conta do convênio.
- siconv_licitacao + siconv_contrato: contratos com fornecedores (licitação -> convênio).
- siconv_coordenadas_obra: latitude/longitude da obra.
- siconv_resumo_fisico_financeiro: valor realizado e percentual de execução.
- siconv_acomp_obras_mod_empresas: medições da obra (início, última medição, dias parada).
- siconv_dados_obrasgov_geral: id da obra no Obrasgov (CIPI) por convênio.
- siconv_pagamento (conector à parte, ~1 GB): pagamentos da conta a cada fornecedor.

Partição = ano da proposta. Os arquivos são os mesmos para todas as partições: cada uma
filtra o seu ano e o download é reaproveitado no processo (como no Portal da Transparência).
"""

from collections import defaultdict
from collections.abc import AsyncIterator, Sequence
from datetime import date
from decimal import Decimal
from typing import ClassVar

from httpx import Response
from pydantic import BaseModel

from ouroboros.canonical import (
    ConvenioContratoRow,
    ConvenioDesembolsoRow,
    ConvenioEmendaRow,
    ConvenioFornecedorRow,
    ConvenioMetaRow,
    ConvenioRow,
)
from ouroboros.connectors.base import HttpConnector
from ouroboros.core.parse import clean, parse_date, parse_decimal, parse_int, zip_csv_columns
from ouroboros.core.privacy import digits
from ouroboros.core.raw_store import RawRecord
from ouroboros.core.text import nome_parlamentar

BASE_URL = "https://repositorio.dados.gov.br/seges/detru/"

ARQUIVOS = {
    "convenio": "siconv_convenio.csv.zip",
    "proposta": "siconv_proposta.csv.zip",
    "emenda": "siconv_emenda.csv.zip",
    "meta": "siconv_meta_crono_fisico.csv.zip",
    "desembolso": "siconv_desembolso.csv.zip",
    "licitacao": "siconv_licitacao.csv.zip",
    "contrato": "siconv_contrato.csv.zip",
    "coordenadas": "siconv_coordenadas_obra.zip",
    "resumo": "siconv_resumo_fisico_financeiro.zip",
    "medicoes": "siconv_acomp_obras_mod_empresas.csv.zip",
    "obrasgov": "siconv_dados_obrasgov_geral.zip",
}
PAGAMENTO = "siconv_pagamento.csv.zip"

# Caixa do Brasil com folga: fora disso a coordenada é erro de digitação (lat/long trocadas,
# vírgula perdida) e mais atrapalha que ajuda no mapa.
_LAT = (Decimal("-34.0"), Decimal("5.5"))
_LON = (Decimal("-74.5"), Decimal("-28.5"))
ZERO = Decimal("0")


def _txt(value: str | None) -> str | None:
    return clean(value)


def _valor(value: str | None) -> Decimal:
    return parse_decimal(value) or ZERO


def _data(value: str | None) -> date | None:
    """Arquivos misturam '31/12/2019' e '2024-08-21'."""
    value = (value or "").strip()
    if len(value) >= 10 and value[4] == "-":
        return parse_date(value)
    return parse_date(value, "%d/%m/%Y")


def _documento(value: str | None) -> str | None:
    """CNPJ completo; CPF vem mascarado pela fonte (***26003***) e fica como veio."""
    value = (value or "").strip()
    if not value or "*" in value:
        return value or None
    d = digits(value)
    return d if len(d) in (11, 14) else (d or None)


def _cnpj(value: str | None) -> str | None:
    d = digits(value)
    return d if len(d) == 14 and "*" not in (value or "") else None


def _coordenada(value: str | None, faixa: tuple[Decimal, Decimal]) -> Decimal | None:
    v = parse_decimal(value)
    if v is None or not faixa[0] <= v <= faixa[1]:
        return None
    return v.quantize(Decimal("0.000001"))


def _cep(value: str | None) -> str | None:
    d = digits(value)
    return f"{d[:5]}-{d[5:]}" if len(d) == 8 else None


def emenda_codigo(programa: str | None, numero: str | None) -> str | None:
    """'5400020230013' + '60110001' -> '202360110001' (código do Portal da Transparência)."""
    programa, numero = (programa or "").strip(), (numero or "").strip()
    ano = programa[5:9]
    if len(numero) != 8 or not numero.isdigit() or not ano.isdigit():
        return None
    if not 2000 <= int(ano) <= 2100:
        return None
    return ano + numero


def _bool(value: str | None) -> bool | None:
    v = (value or "").strip().upper()
    return True if v == "SIM" else False if v in ("NÃO", "NAO") else None


class TransferegovConveniosConnector(HttpConnector):
    """Convênios do Transferegov: emendas, obra (local, datas, execução), contratos e desembolsos"""

    fonte = "transferegov"
    recurso = "convenios"
    base_url = BASE_URL
    max_calls_per_minute = 30

    # (arquivo, dia) -> resposta: rodar todos os anos baixa cada arquivo uma vez só
    _cache: ClassVar[dict[tuple[str, date], Response]] = {}

    async def extract(self, particao: str) -> AsyncIterator[RawRecord]:
        hoje = date.today()
        if self._client is None and any(d != hoje for _, d in self._cache):
            self._cache.clear()
        async with self.http() as client:
            for recurso, arquivo in ARQUIVOS.items():
                r = self._cache.get((arquivo, hoje)) if self._client is None else None
                if r is None:
                    r = await client.get(arquivo)
                    if self._client is None:
                        self._cache[(arquivo, hoje)] = r
                yield self.raw(recurso, particao, r, "application/zip")

    def transform(self, records: Sequence[RawRecord]) -> Sequence[BaseModel]:
        arq = {r.recurso: r for r in records}
        ano = int(records[0].particao) if records else 0

        def lineage(recurso: str) -> dict:
            r = arq[recurso]
            return {"fonte": self.fonte, "fonte_url": r.url, "raw_hash": r.sha256}

        def ler(recurso: str, colunas: Sequence[str], member: str | None = None):
            if recurso not in arq:
                return iter(())
            return zip_csv_columns(arq[recurso].payload, colunas, member=member)

        # convênio por proposta (todas): a proposta é que diz o ano
        convenios: dict[int, tuple[str, ...]] = {}
        for c in ler(
            "convenio",
            [
                "NR_CONVENIO", "ID_PROPOSTA", "DIA_ASSIN_CONV", "SIT_CONVENIO",
                "SUBSITUACAO_CONV", "DIA_PUBL_CONV", "DIA_INIC_VIGENC_CONV",
                "DIA_FIM_VIGENC_CONV", "DIA_FIM_VIGENC_ORIGINAL_CONV", "DIA_LIMITE_PREST_CONTAS",
                "QTD_TA", "QTD_PRORROGA", "VL_GLOBAL_CONV", "VL_REPASSE_CONV",
                "VL_CONTRAPARTIDA_CONV", "VL_EMPENHADO_CONV", "VL_DESEMBOLSADO_CONV",
                "VL_SALDO_CONTA",
            ],
        ):  # fmt: skip
            numero, proposta = parse_int(c[0]), parse_int(c[1])
            if numero and proposta:
                convenios[proposta] = c

        # propostas do ano que viraram convênio
        propostas: dict[int, tuple[str, ...]] = {}
        for p in ler(
            "proposta",
            [
                "ID_PROPOSTA", "ANO_PROP", "UF_PROPONENTE", "MUNIC_PROPONENTE", "COD_MUNIC_IBGE",
                "DESC_ORGAO_SUP", "DESC_ORGAO", "NATUREZA_JURIDICA", "MODALIDADE",
                "IDENTIF_PROPONENTE", "NM_PROPONENTE", "OBJETO_PROPOSTA", "DIA_PROPOSTA",
            ],
        ):  # fmt: skip
            pid = parse_int(p[0])
            if pid in convenios and parse_int(p[1]) == ano:
                propostas[pid] = p
        numero_da_proposta = {pid: int(convenios[pid][0]) for pid in propostas}
        do_ano = set(numero_da_proposta.values())

        rows: list[BaseModel] = []
        obra = self._obra(ler, numero_da_proposta, do_ano)
        metas = self._metas(ler, numero_da_proposta, ano, lineage)
        rows.extend(metas)
        # endereço da obra = primeira meta com endereço
        local: dict[int, ConvenioMetaRow] = {}
        for m in sorted(metas, key=lambda m: (m.numero or 0, m.id)):
            if m.endereco and m.convenio_numero not in local:
                local[m.convenio_numero] = m

        for pid, p in propostas.items():
            c = convenios[pid]
            numero = int(c[0])
            o = obra.get(numero, {})
            meta = local.get(numero)
            rows.append(
                ConvenioRow(
                    numero=numero,
                    proposta_id=pid,
                    ano=ano,
                    situacao=_txt(c[3]),
                    subsituacao=_txt(c[4]),
                    modalidade=_txt(p[8]),
                    orgao_superior=_txt(p[5]),
                    orgao=_txt(p[6]),
                    proponente_cnpj=_cnpj(p[9]),
                    proponente_nome=_txt(p[10]),
                    natureza_juridica=_txt(p[7]),
                    uf=_txt(p[2]),
                    municipio_codigo_ibge=parse_int(p[4]),
                    municipio_nome=_txt(p[3]),
                    objeto=_txt(p[11]),
                    data_proposta=_data(p[12]),
                    data_assinatura=_data(c[2]),
                    data_publicacao=_data(c[5]),
                    inicio_vigencia=_data(c[6]),
                    fim_vigencia=_data(c[7]),
                    fim_vigencia_original=_data(c[8]),
                    limite_prestacao_contas=_data(c[9]),
                    aditivos=parse_int(c[10]),
                    prorrogacoes=parse_int(c[11]),
                    valor_global=_valor(c[12]),
                    valor_repasse=_valor(c[13]),
                    valor_contrapartida=_valor(c[14]),
                    valor_empenhado=_valor(c[15]),
                    valor_desembolsado=_valor(c[16]),
                    valor_saldo_conta=parse_decimal(c[17]),
                    endereco=meta.endereco if meta else None,
                    cep=meta.cep if meta else None,
                    **o,
                    **lineage("convenio"),
                )
            )

        for e in ler(
            "emenda",
            ["ID_PROPOSTA", "COD_PROGRAMA_EMENDA", "NR_EMENDA", "NOME_PARLAMENTAR",
             "TIPO_PARLAMENTAR", "IND_IMPOSITIVO", "VALOR_REPASSE_EMENDA"],
        ):  # fmt: skip
            numero = numero_da_proposta.get(parse_int(e[0]) or 0)
            if numero is None:
                continue
            nome = _txt(e[3]) or "Sem informação"
            rows.append(
                ConvenioEmendaRow(
                    convenio_numero=numero,
                    ano=ano,
                    emenda_codigo=emenda_codigo(e[1], e[2]),
                    emenda_numero=_txt(e[2]),
                    tipo=_txt(e[4]),
                    parlamentar_nome=nome,
                    parlamentar_nome_normalizado=nome_parlamentar(nome),
                    impositiva=_bool(e[5]),
                    valor_repasse=_valor(e[6]),
                    **lineage("emenda"),
                )
            )

        for d in ler(
            "desembolso", ["ID_DESEMBOLSO", "NR_CONVENIO", "DATA_DESEMBOLSO", "NR_SIAFI",
                           "VL_DESEMBOLSADO"]
        ):  # fmt: skip
            numero, did = parse_int(d[1]), parse_int(d[0])
            if numero not in do_ano or did is None:
                continue
            rows.append(
                ConvenioDesembolsoRow(
                    id=did,
                    convenio_numero=numero,
                    ano=ano,
                    data=_data(d[2]),
                    documento=(_txt(d[3]) or "")[:20] or None,
                    valor=_valor(d[4]),
                    **lineage("desembolso"),
                )
            )

        rows.extend(self._contratos(ler, do_ano, ano, lineage))
        return rows

    @staticmethod
    def _obra(ler, numero_da_proposta: dict[int, int], do_ano: set[int]) -> dict[int, dict]:
        """Campos de obra por convênio: Obrasgov, coordenadas, execução e medições."""
        obra: dict[int, dict] = defaultdict(dict)

        for id_obra, instrumento in ler("obrasgov", ["id_projeto_investimento", "nr_instrumento"]):
            numero = parse_int(instrumento)
            if numero in do_ano and _txt(id_obra):
                obra[numero].setdefault("obra_id", id_obra.strip()[:20])

        for pid, nome, lat, lon in ler(
            "coordenadas",
            ["ID_PROPOSTA", "NOME_PROJETO_CADASTRO_OBRA", "LATITUDE_CADASTRO_OBRA",
             "LONGITUDE_CADASTRO_OBRA"],
        ):  # fmt: skip
            numero = numero_da_proposta.get(parse_int(pid) or 0)
            if numero is None or "latitude" in obra[numero]:
                continue
            la, lo = _coordenada(lat, _LAT), _coordenada(lon, _LON)
            obra[numero]["obra_nome"] = _txt(nome)
            if la is not None and lo is not None:
                obra[numero]["latitude"], obra[numero]["longitude"] = la, lo

        for pid, _total, realizado, pct in ler(
            "resumo",
            ["ID_PROPOSTA", "VALOR_TOTAL_RESUMO_FISICO_FINANCEIRO",
             "VALOR_REALIZADO_RESUMO_FISICO_FINANCEIRO",
             "PERCENTUAL_EXECUCAO_RESUMO_FISICO_FINANCEIRO"],
        ):  # fmt: skip
            numero = numero_da_proposta.get(parse_int(pid) or 0)
            if numero is None:
                continue
            p = parse_decimal(pct)
            obra[numero]["percentual_execucao"] = (
                min(max(p, ZERO), Decimal("999")) if p is not None else None
            )
            obra[numero]["valor_executado"] = parse_decimal(realizado)

        for pid, inicio, fim, dias in ler(
            "medicoes",
            ["ID_PROPOSTA", "DATA_INICIO_OBRA_CONTRATO_ACOMPANHAMENTO_OBRA",
             "DATA_FIM_MEDICAO_OBJETO_ACOMPANHAMENTO_OBRA",
             "QTD_DIAS_SEM_MEDICAO_ACOMPANHAMENTO_OBRA"],
            member="contratos_medicoes",
        ):  # fmt: skip
            numero = numero_da_proposta.get(parse_int(pid) or 0)
            if numero is None:
                continue
            o = obra[numero]
            ini, fim_d, sem = _data(inicio), _data(fim), parse_int(dias)
            if ini and (o.get("inicio_obra") is None or ini < o["inicio_obra"]):
                o["inicio_obra"] = ini
            if fim_d and (o.get("ultima_medicao") is None or fim_d >= o["ultima_medicao"]):
                o["ultima_medicao"] = fim_d
                o["dias_sem_medicao"] = sem
        return obra

    def _metas(self, ler, numero_da_proposta, ano, lineage) -> list[ConvenioMetaRow]:
        out: list[ConvenioMetaRow] = []
        for m in ler(
            "meta",
            ["ID_META", "ID_PROPOSTA", "NR_META", "DESC_META", "DATA_INICIO_META",
             "DATA_FIM_META", "UF_META", "MUNICIPIO_META", "ENDERECO_META", "CEP_META",
             "QTD_META", "UND_FORNECIMENTO_META", "VL_META"],
        ):  # fmt: skip
            numero = numero_da_proposta.get(parse_int(m[1]) or 0)
            mid = parse_int(m[0])
            if numero is None or mid is None:
                continue
            out.append(
                ConvenioMetaRow(
                    id=mid,
                    convenio_numero=numero,
                    ano=ano,
                    numero=parse_int(m[2]),
                    descricao=_txt(m[3]),
                    data_inicio=_data(m[4]),
                    data_fim=_data(m[5]),
                    uf=(_txt(m[6]) or "")[:2] or None,
                    municipio_nome=(_txt(m[7]) or "")[:120] or None,
                    endereco=_txt(m[8]),
                    cep=_cep(m[9]),
                    quantidade=parse_decimal(m[10]),
                    unidade=(_txt(m[11]) or "")[:60] or None,
                    valor=_valor(m[12]),
                    **lineage("meta"),
                )
            )
        return out

    @staticmethod
    def _contratos(ler, do_ano: set[int], ano: int, lineage) -> list[ConvenioContratoRow]:
        licitacoes: dict[int, tuple[int, str | None]] = {}
        for lid, numero, modalidade, processo in ler(
            "licitacao",
            ["ID_LICITACAO", "NR_CONVENIO", "MODALIDADE_LICITACAO", "TP_PROCESSO_COMPRA"],
        ):
            n, i = parse_int(numero), parse_int(lid)
            if n in do_ano and i is not None:
                licitacoes[i] = (n, _txt(modalidade) or _txt(processo))
        out: list[ConvenioContratoRow] = []
        vistos: set[int] = set()
        for c in ler(
            "contrato",
            ["ID_LICITACAO", "ID_CONTRATO", "NR_CONTRATO", "DATA_ASSINATURA_CONTRATO",
             "DATA_INICIO_VIGENCIA_CONTRATO", "DATA_FIM_VIGENCIA_CONTRATO", "OBJETO_CONTRATO",
             "TIPO_AQUISICAO_CONTRATO", "VALOR_GLOBAL_CONTRATO", "ID_FORNECEDOR_CONTRATO",
             "NOME_FORNECEDOR_CONTRATO"],
        ):  # fmt: skip
            lic = licitacoes.get(parse_int(c[0]) or 0)
            cid = parse_int(c[1])
            if lic is None or cid is None or cid in vistos:
                continue
            vistos.add(cid)
            out.append(
                ConvenioContratoRow(
                    id=cid,
                    convenio_numero=lic[0],
                    ano=ano,
                    numero=(_txt(c[2]) or "")[:60] or None,
                    modalidade_licitacao=(lic[1] or "")[:80] or None,
                    objeto=_txt(c[6]),
                    tipo_aquisicao=(_txt(c[7]) or "")[:60] or None,
                    fornecedor_documento=_documento(c[9]),
                    fornecedor_nome=_txt(c[10]),
                    data_assinatura=_data(c[3]),
                    inicio_vigencia=_data(c[4]),
                    fim_vigencia=_data(c[5]),
                    valor=_valor(c[8]),
                    **lineage("contrato"),
                )
            )
        return out


class TransferegovPagamentosConnector(HttpConnector):
    """Pagamentos da conta dos convênios a fornecedores (Transferegov), somados por fornecedor"""

    fonte = "transferegov"
    recurso = "convenio_pagamentos"
    base_url = BASE_URL
    max_calls_per_minute = 30

    async def extract(self, particao: str) -> AsyncIterator[RawRecord]:
        async with self.http() as client:
            r = await client.get(PAGAMENTO)
            yield self.raw("pagamento", particao, r, "application/zip")

    def transform(self, records: Sequence[RawRecord]) -> Sequence[BaseModel]:
        rows: list[BaseModel] = []
        for record in records:
            lineage = {"fonte": self.fonte, "fonte_url": record.url, "raw_hash": record.sha256}
            # (convênio, CNPJ ou None p/ pessoa física) -> [nome, qtd, primeiro, último, total]
            soma: dict[tuple[int, str | None], list] = {}
            for numero, doc, nome, data, valor in zip_csv_columns(
                record.payload,
                ["NR_CONVENIO", "IDENTIF_FORNECEDOR", "NOME_FORNECEDOR", "DATA_PAG", "VL_PAGO"],
            ):
                n, v = parse_int(numero), parse_decimal(valor)
                if n is None or v is None:
                    continue
                cnpj = _cnpj(doc)
                d = _data(data)
                s = soma.get((n, cnpj))
                if s is None:
                    s = soma[(n, cnpj)] = [
                        (_txt(nome) or "Sem informação") if cnpj else "Pessoas físicas",
                        0, d, d, ZERO,
                    ]  # fmt: skip
                s[1] += 1
                if d and (s[2] is None or d < s[2]):
                    s[2] = d
                if d and (s[3] is None or d > s[3]):
                    s[3] = d
                s[4] += v
            for (n, cnpj), (nome, qtd, primeiro, ultimo, total) in soma.items():
                rows.append(
                    ConvenioFornecedorRow(
                        convenio_numero=n,
                        documento=cnpj,
                        nome=nome,
                        pagamentos=qtd,
                        primeiro_pagamento=primeiro,
                        ultimo_pagamento=ultimo,
                        valor=total,
                        **lineage,
                    )
                )
        return rows
