"""Gravação das linhas canônicas. Todo loader é idempotente: rodar a mesma partição de novo
produz o mesmo estado no banco."""

from collections.abc import Sequence
from typing import TypeVar

from loguru import logger
from pydantic import BaseModel
from sqlalchemy import delete, func, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ouroboros.canonical import (
    CandidaturaRow,
    ConvenioContratoRow,
    ConvenioDesembolsoRow,
    ConvenioEmendaRow,
    ConvenioFornecedorRow,
    ConvenioMetaRow,
    ConvenioRow,
    CpfPessoaRow,
    DespesaRow,
    EmendaConvenioRow,
    EmendaFavorecidoRow,
    EmendaRow,
    EnteRow,
    MandatoRow,
    PartidoRow,
    PessoaRow,
    TransferenciaEspecialEmpenhoRow,
    TransferenciaEspecialExecutorRow,
    TransferenciaEspecialMetaRow,
    TransferenciaEspecialPagamentoRow,
    TransferenciaEspecialRow,
)
from ouroboros.models.convenio import (
    Convenio,
    ConvenioContrato,
    ConvenioDesembolso,
    ConvenioEmenda,
    ConvenioFornecedor,
    ConvenioMeta,
)
from ouroboros.models.despesa import DespesaGabinete
from ouroboros.models.emenda import (
    Emenda,
    EmendaConvenio,
    EmendaFavorecido,
    TransferenciaEspecial,
    TransferenciaEspecialEmpenho,
    TransferenciaEspecialExecutor,
    TransferenciaEspecialMeta,
    TransferenciaEspecialPagamento,
)
from ouroboros.models.ente import Ente
from ouroboros.models.mandato import Candidatura, Mandato
from ouroboros.models.partido import Partido
from ouroboros.resolution.nomes import tokens
from ouroboros.resolution.politicos import aplicar_cpfs, resolver_pessoas

# asyncpg aceita no máximo 32767 parâmetros por statement.
_MAX_PARAMS = 30000

T = TypeVar("T", bound=BaseModel)


def _of(rows: Sequence[BaseModel], kind: type[T]) -> list[T]:
    return [r for r in rows if isinstance(r, kind)]


async def _upsert(
    session: AsyncSession,
    model: type,
    values: list[dict],
    conflict: list[str],
    *,
    keep: Sequence[str] = (),
) -> None:
    """INSERT ... ON CONFLICT DO UPDATE em blocos. `keep` = colunas que não são sobrescritas."""
    if not values:
        return
    chunk = max(1, _MAX_PARAMS // len(values[0]))
    for start in range(0, len(values), chunk):
        stmt = insert(model).values(values[start : start + chunk])
        updatable = {c: stmt.excluded[c] for c in values[0] if c not in conflict and c not in keep}
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=conflict, set_={**updatable, "ingerido_em": func.now()}
            )
        )


async def load_entes(session: AsyncSession, rows: Sequence[BaseModel], particao: str) -> int:
    entes = _of(rows, EnteRow)
    await _upsert(session, Ente, [r.model_dump() for r in entes], ["codigo_ibge"])
    return len(entes)


async def _upsert_mandatos(
    session: AsyncSession, mandatos: Sequence[MandatoRow], politico_por_id: dict[str, int]
) -> None:
    values = []
    for m in mandatos:
        v = m.model_dump(exclude={"pessoa_id_externo"})
        v["politico_id"] = politico_por_id[m.pessoa_id_externo]
        v["partido_sigla"] = m.partidos[0] if len(m.partidos) == 1 else None
        values.append(v)
    await _upsert(session, Mandato, values, ["origem", "id_externo"])


async def load_parlamentares(
    session: AsyncSession, rows: Sequence[BaseModel], particao: str
) -> int:
    """Pessoas + mandatos de uma casa legislativa (Câmara, Senado; depois ALEs e câmaras)."""
    resolucao = await resolver_pessoas(session, _of(rows, PessoaRow))
    mandatos = _of(rows, MandatoRow)
    await _upsert_mandatos(session, mandatos, resolucao.politico_por_id_externo)
    await relink_despesas(session)
    await relink_emendas(session)
    return len(mandatos)


async def load_candidaturas(session: AsyncSession, rows: Sequence[BaseModel], particao: str) -> int:
    partidos = _of(rows, PartidoRow)
    await _upsert(session, Partido, [p.model_dump() for p in partidos], ["numero_tse"])

    resolucao = await resolver_pessoas(session, _of(rows, PessoaRow))
    candidaturas = _of(rows, CandidaturaRow)
    values = []
    for c in candidaturas:
        v = c.model_dump(exclude={"pessoa_id_externo"})
        v["politico_id"] = resolucao.politico_por_id_externo[c.pessoa_id_externo]
        values.append(v)
    await _upsert(session, Candidatura, values, ["sq_candidato"])
    await relink_despesas(session)
    return len(candidaturas)


_DESPESA_COLS = [
    "fonte",
    "fonte_url",
    "raw_hash",
    "verba",
    "parlamentar_origem",
    "parlamentar_id_externo",
    "parlamentar_nome",
    "parlamentar_nome_normalizado",
    "uf",
    "partido_sigla",
    "ano",
    "mes",
    "data_emissao",
    "categoria",
    "subcategoria",
    "fornecedor_nome",
    "fornecedor_documento",
    "fornecedor_tipo",
    "documento_numero",
    "documento_url",
    "documento_id_fonte",
    "valor_documento",
    "valor_glosa",
    "valor_liquido",
]


async def load_despesas(session: AsyncSession, rows: Sequence[BaseModel], particao: str) -> int:
    """Substitui a partição (fonte, verba, ano) inteira: as fontes não têm chave única por linha."""
    despesas = _of(rows, DespesaRow)
    pares = {(d.fonte, d.verba) for d in despesas}
    ano = int(particao)
    for fonte, verba in pares:
        await session.execute(
            delete(DespesaGabinete).where(
                DespesaGabinete.fonte == fonte,
                DespesaGabinete.verba == verba,
                DespesaGabinete.ano == ano,
            )
        )
    fora = sum(1 for d in despesas if d.ano != ano)
    if fora:
        logger.warning("{} despesas com ano diferente da partição {}", fora, ano)

    conn = await session.connection()
    raw = await conn.get_raw_connection()
    await raw.driver_connection.copy_records_to_table(
        DespesaGabinete.__tablename__,
        columns=_DESPESA_COLS,
        records=[tuple(getattr(d, c) for c in _DESPESA_COLS) for d in despesas],
    )
    await aplicar_cpfs(session, _of(rows, CpfPessoaRow))
    await relink_despesas(session)
    return len(despesas)


async def relink_despesas(session: AsyncSession) -> None:
    """Liga despesas ainda sem político: por id do parlamentar na fonte, ou por nome quando a
    fonte só traz o nome (CEAPS) e o nome aponta para um único político daquela origem."""
    await session.execute(
        text(
            """
            UPDATE despesa_gabinete d SET politico_id = i.politico_id
            FROM politico_identificador i
            WHERE d.politico_id IS NULL
              AND d.parlamentar_id_externo IS NOT NULL
              AND i.origem = d.parlamentar_origem
              AND i.id_externo = d.parlamentar_id_externo
            """
        )
    )
    await session.execute(
        text(
            """
            UPDATE despesa_gabinete d SET politico_id = m.politico_id
            FROM (
                SELECT origem, nome_na_fonte_normalizado, min(politico_id) AS politico_id
                FROM politico_identificador
                GROUP BY origem, nome_na_fonte_normalizado
                HAVING count(DISTINCT politico_id) = 1
            ) m
            WHERE d.politico_id IS NULL
              AND d.parlamentar_id_externo IS NULL
              AND m.origem = d.parlamentar_origem
              AND m.nome_na_fonte_normalizado = d.parlamentar_nome_normalizado
            """
        )
    )
    await _relink_por_tokens(session)


async def _relink_por_tokens(session: AsyncSession) -> None:
    """Último recurso para fontes que só trazem nome (CEAPS usa "WEVERTON ROCHA" onde a API do
    Senado diz "Weverton"): liga se todos os tokens do nome da despesa estão no nome civil ou
    parlamentar de exatamente um político daquela origem."""
    pendentes = (
        await session.execute(
            text(
                """
                SELECT DISTINCT parlamentar_origem, parlamentar_nome_normalizado
                FROM despesa_gabinete
                WHERE politico_id IS NULL AND parlamentar_id_externo IS NULL
                """
            )
        )
    ).all()
    if not pendentes:
        return
    origens = sorted({o for o, _ in pendentes})
    pessoas = (
        await session.execute(
            text(
                """
                SELECT i.origem, i.politico_id, i.nome_na_fonte, p.nome_civil
                FROM politico_identificador i JOIN politico p ON p.id = i.politico_id
                WHERE i.origem = ANY(:origens)
                """
            ),
            {"origens": origens},
        )
    ).all()
    conhecidos: dict[str, list[tuple[int, set[str]]]] = {}
    for origem, pid, nome_fonte, nome_civil in pessoas:
        toks = set(tokens(nome_fonte)) | set(tokens(nome_civil or ""))
        conhecidos.setdefault(origem, []).append((pid, toks))

    for origem, nome in pendentes:
        alvo = set(tokens(nome))
        if len(alvo) < 2:
            continue
        achados = {pid for pid, toks in conhecidos.get(origem, []) if alvo <= toks}
        if len(achados) != 1:
            continue
        await session.execute(
            update(DespesaGabinete)
            .where(
                DespesaGabinete.politico_id.is_(None),
                DespesaGabinete.parlamentar_id_externo.is_(None),
                DespesaGabinete.parlamentar_origem == origem,
                DespesaGabinete.parlamentar_nome_normalizado == nome,
            )
            .values(politico_id=achados.pop())
            .execution_options(synchronize_session=False)
        )


async def _copy(session: AsyncSession, table: str, columns: list[str], rows: Sequence) -> None:
    conn = await session.connection()
    raw = await conn.get_raw_connection()
    await raw.driver_connection.copy_records_to_table(
        table, columns=columns, records=[tuple(getattr(r, c) for c in columns) for r in rows]
    )


async def _copy_rows(session: AsyncSession, model: type, kind: type[T], rows: Sequence) -> None:
    if rows:
        await _copy(session, model.__tablename__, list(kind.model_fields), rows)


async def load_emendas(session: AsyncSession, rows: Sequence[BaseModel], particao: str) -> int:
    """Substitui o ano inteiro de emendas, pagamentos a favorecidos e convênios (sem chave por
    linha)."""
    ano = int(particao)
    emendas = _of(rows, EmendaRow)
    favorecidos = _of(rows, EmendaFavorecidoRow)
    convenios = _of(rows, EmendaConvenioRow)
    for model in (Emenda, EmendaFavorecido, EmendaConvenio):
        await session.execute(delete(model).where(model.ano == ano))
    await _copy_rows(session, Emenda, EmendaRow, emendas)
    await _copy_rows(session, EmendaFavorecido, EmendaFavorecidoRow, favorecidos)
    await _copy_rows(session, EmendaConvenio, EmendaConvenioRow, convenios)
    await relink_emendas(session, ano)
    return len(emendas) + len(favorecidos) + len(convenios)


_TRANSFERENCIAS = [
    (TransferenciaEspecial, TransferenciaEspecialRow),
    (TransferenciaEspecialExecutor, TransferenciaEspecialExecutorRow),
    (TransferenciaEspecialMeta, TransferenciaEspecialMetaRow),
    (TransferenciaEspecialEmpenho, TransferenciaEspecialEmpenhoRow),
    (TransferenciaEspecialPagamento, TransferenciaEspecialPagamentoRow),
]


async def load_transferencias_especiais(
    session: AsyncSession, rows: Sequence[BaseModel], particao: str
) -> int:
    """Emendas Pix: partição única, substitui tudo e liga beneficiário ao município (ente)."""
    total = 0
    for model, kind in _TRANSFERENCIAS:
        await session.execute(delete(model))
        linhas = _of(rows, kind)
        await _copy_rows(session, model, kind, linhas)
        total += len(linhas)
    await session.execute(
        text(
            """
            UPDATE transferencia_especial t SET municipio_codigo_ibge = e.codigo_ibge
            FROM ente e
            WHERE t.municipio_codigo_ibge IS NULL
              AND e.esfera = 'municipal'
              AND e.uf = t.uf
              AND e.nome_normalizado = regexp_replace(
                    lower(unaccent(t.beneficiario_nome)),
                    '^(prefeitura municipal de|municipio de|prefeitura de) ', ''
                  )
            """
        )
    )
    await relink_emendas(session)
    return total


_CONVENIOS = [
    (Convenio, ConvenioRow),
    (ConvenioEmenda, ConvenioEmendaRow),
    (ConvenioMeta, ConvenioMetaRow),
    (ConvenioDesembolso, ConvenioDesembolsoRow),
    (ConvenioContrato, ConvenioContratoRow),
]


async def load_convenios(session: AsyncSession, rows: Sequence[BaseModel], particao: str) -> int:
    """Substitui o ano (da proposta) de convênios e tudo que pende deles."""
    ano = int(particao)
    total = 0
    for model, kind in _CONVENIOS:
        await session.execute(delete(model).where(model.ano == ano))
        linhas = _of(rows, kind)
        await _copy_rows(session, model, kind, linhas)
        total += len(linhas)
    await relink_emendas(session, ano)
    return total


async def load_convenio_pagamentos(
    session: AsyncSession, rows: Sequence[BaseModel], particao: str
) -> int:
    """Pagamentos somados por convênio x fornecedor: partição única, substitui tudo."""
    linhas = _of(rows, ConvenioFornecedorRow)
    await session.execute(delete(ConvenioFornecedor))
    await _copy_rows(session, ConvenioFornecedor, ConvenioFornecedorRow, linhas)
    return len(linhas)


# Nome parlamentar (Câmara/Senado) que aponta para um único político.
_NOMES_PARLAMENTARES = """
    SELECT nome, min(politico_id) AS politico_id FROM (
        SELECT i.nome_na_fonte_normalizado AS nome, i.politico_id
        FROM politico_identificador i WHERE i.origem IN ('camara', 'senado')
        UNION ALL
        SELECT p.nome_normalizado, p.id FROM politico p
        WHERE EXISTS (
            SELECT 1 FROM politico_identificador i
            WHERE i.politico_id = p.id AND i.origem IN ('camara', 'senado')
        )
    ) n
    GROUP BY nome
    HAVING count(DISTINCT politico_id) = 1
"""


async def relink_emendas(session: AsyncSession, ano: int | None = None) -> None:
    """Liga autor da emenda (só nome + código CGU) ao político pelo nome parlamentar.

    Emendas de bancada, comissão e relator não casam (autor coletivo) e ficam sem político.
    Convênios e transferências especiais herdam o político da emenda pelo código (mais seguro
    que o nome); sem emenda carregada, caem no nome também.
    """
    filtro_ano = "AND e.ano = :ano" if ano is not None else ""
    params = {"ano": ano} if ano is not None else {}

    async def por_nome(tabela: str, coluna: str) -> None:
        await session.execute(
            text(
                f"""
                UPDATE {tabela} e SET politico_id = m.politico_id
                FROM ({_NOMES_PARLAMENTARES}) m
                WHERE e.politico_id IS NULL
                  AND e.{coluna} = m.nome
                  {filtro_ano}
                """
            ),
            params,
        )

    await por_nome(Emenda.__tablename__, "autor_nome_normalizado")
    await por_nome(EmendaFavorecido.__tablename__, "autor_nome_normalizado")
    for tabela in (
        EmendaConvenio.__tablename__,
        ConvenioEmenda.__tablename__,
        TransferenciaEspecial.__tablename__,
    ):
        await session.execute(
            text(
                f"""
                UPDATE {tabela} e SET politico_id = m.politico_id
                FROM (
                    SELECT codigo, min(politico_id) AS politico_id FROM emenda
                    WHERE politico_id IS NOT NULL
                    GROUP BY codigo HAVING count(DISTINCT politico_id) = 1
                ) m
                WHERE e.politico_id IS NULL AND e.emenda_codigo = m.codigo
                  {filtro_ano}
                """
            ),
            params,
        )
    await por_nome(ConvenioEmenda.__tablename__, "parlamentar_nome_normalizado")
    await por_nome(TransferenciaEspecial.__tablename__, "parlamentar_nome_normalizado")
