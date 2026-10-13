"""Detectores de indícios de fraude e desvio sobre os dados carregados.

Cada detector é uma regra explicável, calibrada contra os dados reais (CEAP/CEAPS 2015+ e
emendas 2014+), com limiares conservadores para que um alerta valha a leitura:

- Categorias de preço tabelado ou cobrança impessoal (passagens, telefonia, pedágio, Correios)
  ficam fora: nelas repetição e concentração são normais.
- Valores e quantidades mínimas evitam alertar sobre centavos e amostras pequenas.
- Todo alerta traz as métricas que o dispararam e os links dos documentos oficiais.

`score` (0-100) mede a força do indício dentro do detector; `peso` (0-1) é a confiança no
detector em si (nota duplicada é fato verificável; desvio de Benford é só estatística).
O risco de um político combina os detectores em `estatistica.risco`.
"""

import re
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ouroboros.analises.estatistica import (
    BENFORD,
    cnpj_valido,
    desvio_digitos,
    distribuicao,
    escala,
    escala_log,
    mistura,
    score,
    severidade,
    z_robusto,
)

# Cobrança impessoal ou preço tabelado: repetição, concentração e números de documento
# repetidos são normais (bilhete aéreo, conta de telefone, pedágio, Correios, auxílio-moradia).
IMPESSOAL = (
    r"(passage|telefon|t[áa]xi|ped[áa]gio|postais|aux[íi]lio-moradia|assinatura de publica"
    r"|tokens)"
)
# Varejo de cupom fiscal: numeração é do caixa da loja, não diz nada sobre o cliente.
VAREJO = r"(combust|alimenta|hospedagem|locomo[çc])"
# Serviços sob encomenda, onde empresa de fachada costuma aparecer (casos da CEAP já julgados
# envolvem divulgação, consultoria, locação de veículos e segurança).
SOB_ENCOMENDA = (
    r"(divulga|consultori|trabalhos t[ée]cnicos|loca[çc][ãa]o ou fretamento|seguran[çc]a"
    r"|fretamento)"
)
# Aluguel: o locador emite recibo só para o inquilino, sequencial e exclusivo por natureza.
IMOVEL = r"(imobili|administra[çc][ãa]o de (bens|im[óo])|condom|alugu|loca[çc][ãa]o de im)"
# Entidades públicas (prefeitura, fundo, autarquia) e grandes sociedades anônimas.
PUBLICA = (
    r"(munic|estad|federal|p[úu]blic|autarquia|fundo|[óo]rg[ãa]o|economia mista|an[ôo]nima"
    r"|cons[óo]rcio|internacional|cart[óo]rio|servi[çc]o social aut)"
)
SEM_FINS_LUCRATIVOS = (
    r"(associa[çc][ãa]o privada|funda[çc][ãa]o privada|religiosa|organiza[çc][ãa]o social)"
)
PRIVADA = (
    SEM_FINS_LUCRATIVOS[:-1]
    + r"|limitada|empres[áa]rio|eireli|responsabilidade limitada|sociedade simples)"
)
FIRMA_INDIVIDUAL = r"(empres[áa]rio|eireli|individual de responsabilidade)"
CNPJ = r"^[0-9]{14}$"

PARAMS = {
    "impessoal": IMPESSOAL,
    "varejo": VAREJO,
    "sob_encomenda": SOB_ENCOMENDA,
    "imovel": IMOVEL,
    "publica": PUBLICA,
    "privada": PRIVADA,
    "sfl": SEM_FINS_LUCRATIVOS,
    "cnpj": CNPJ,
}


@dataclass(frozen=True)
class Detector:
    codigo: str
    titulo: str
    area: str  # gabinete, emendas, eleicoes
    peso: float
    metodologia: str
    executar: Callable[[AsyncSession], Awaitable[list[dict]]]


def _json(valor: Any) -> Any:
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, date | datetime):
        return valor.isoformat()
    if isinstance(valor, dict):
        return {k: _json(v) for k, v in valor.items()}
    if isinstance(valor, list | tuple):
        return [_json(v) for v in valor]
    return valor


def _alerta(
    detector: str,
    chave: str,
    s: float,
    *,
    politico_id: int | None,
    titulo: str,
    descricao: str,
    evidencias: dict,
    ano_inicio: int | None = None,
    ano_fim: int | None = None,
    documento: str | None = None,
    nome: str | None = None,
    valor: Decimal | float | None = None,
) -> dict:
    return {
        "chave": f"{detector}:{chave}"[:300],
        "detector": detector,
        "severidade": severidade(s),
        "score": s,
        "peso": CATALOGO[detector].peso,
        "politico_id": politico_id,
        "ano_inicio": ano_inicio,
        "ano_fim": ano_fim if ano_fim is not None else ano_inicio,
        "entidade_documento": documento,
        "entidade_nome": nome,
        "valor": None if valor is None else Decimal(str(valor)).quantize(Decimal("0.01")),
        "titulo": titulo,
        "descricao": descricao,
        "evidencias": _json(evidencias),
    }


def _brl(valor: Decimal | float) -> str:
    s = f"{float(valor):,.2f}"
    return "R$ " + s.replace(",", "_").replace(".", ",").replace("_", ".")


def _pct(valor: float) -> str:
    return f"{100 * valor:.0f}%"


async def _rows(session: AsyncSession, sql: str) -> list[Any]:
    return list((await session.execute(text(sql), PARAMS)).mappings().all())


# ----------------------------------------------------------------------------- gabinete


async def nota_duplicada(session: AsyncSession) -> list[dict]:
    """Mesma nota (fornecedor + número + valor + data) reembolsada mais de uma vez."""
    rows = await _rows(
        session,
        r"""
        with grupos as (
            select fornecedor_documento, documento_numero, valor_liquido, data_emissao,
                   max(fornecedor_nome) as nome, max(categoria) as categoria,
                   count(*) as copias,
                   count(distinct politico_id) as politicos,
                   jsonb_agg(jsonb_build_object(
                       'despesa_id', id, 'politico_id', politico_id,
                       'parlamentar', parlamentar_nome,
                       'verba', verba, 'ano', ano, 'mes', mes, 'documento_id', documento_id_fonte,
                       'url', documento_url) order by id) as linhas
            from despesa_gabinete
            where valor_liquido >= 100
              and data_emissao is not null
              and fornecedor_documento is not null
              and length(regexp_replace(documento_numero, '\D', '', 'g')) >= 3
              and categoria !~* :impessoal
            group by fornecedor_documento, documento_numero, valor_liquido, data_emissao
            having count(*) > 1
               and count(distinct coalesce(documento_id_fonte, id::text)) = count(*)
        )
        select g.* from grupos g
        -- estorno publicado depois (valor negativo para a mesma nota) anula a duplicidade
        where not exists (
            select 1 from despesa_gabinete x
            where x.fornecedor_documento = g.fornecedor_documento
              and x.documento_numero = g.documento_numero
              and x.valor_liquido < 0
        )
        """,
    )
    out = []
    for r in rows:
        linhas = r["linhas"]
        valor = r["valor_liquido"]
        excedente = valor * (r["copias"] - 1)
        por_politico: dict[int | None, list] = defaultdict(list)
        for linha in linhas:
            por_politico[linha["politico_id"]].append(linha)
        varios = r["politicos"] > 1
        s = score(
            62,
            (20, escala_log(float(excedente), 200, 20_000)),
            (8, escala(r["copias"], 2, 4)),
            (8, 1.0 if varios else 0.0),
        )
        for pid, proprias in por_politico.items():
            if pid is None:
                continue
            onde = (
                f"lançada por {r['politicos']} gabinetes diferentes"
                if varios
                else f"reembolsada {len(proprias)} vezes ao mesmo gabinete"
            )
            out.append(
                _alerta(
                    "nota_duplicada",
                    f"{pid}:{r['fornecedor_documento']}:{r['documento_numero']}:{valor}:"
                    f"{r['data_emissao']}",
                    s,
                    politico_id=pid,
                    titulo=f"Nota fiscal {r['documento_numero']} {onde}",
                    descricao=(
                        f"A nota {r['documento_numero']} de {r['nome']} "
                        f"({r['data_emissao']:%d/%m/%Y}, {_brl(valor)}) aparece {r['copias']} "
                        f"vezes na cota, com identificadores de documento diferentes e sem "
                        f"estorno publicado. Valor pago a mais: {_brl(excedente)}."
                    ),
                    evidencias={
                        "metricas": {
                            "copias": r["copias"],
                            "gabinetes": r["politicos"],
                            "valor_nota": valor,
                            "valor_excedente": excedente,
                            "categoria": r["categoria"],
                        },
                        "documentos": linhas,
                    },
                    ano_inicio=min(x["ano"] for x in linhas),
                    ano_fim=max(x["ano"] for x in linhas),
                    documento=r["fornecedor_documento"],
                    nome=r["nome"],
                    valor=excedente,
                )
            )
    return out


async def notas_sequenciais(session: AsyncSession) -> list[dict]:
    """Fornecedor cujas notas ao gabinete são quase toda a numeração que ele emite."""
    rows = await _rows(
        session,
        r"""
        with base as (
            select politico_id, fornecedor_documento as doc,
                   max(fornecedor_nome) as nome,
                   mode() within group (order by categoria) as categoria,
                   count(distinct documento_numero::bigint) as notas,
                   count(distinct ano * 12 + mes) as meses,
                   min(documento_numero::bigint) as primeira,
                   max(documento_numero::bigint) as ultima,
                   sum(valor_liquido) as total,
                   min(ano) as ano_inicio, max(ano) as ano_fim,
                   (array_agg(documento_url order by documento_numero::bigint)
                        filter (where documento_url is not null))[1:5] as urls
            from despesa_gabinete
            where politico_id is not null
              and documento_numero ~ '^[0-9]{1,12}$'
              and fornecedor_documento ~ :cnpj
              and valor_liquido > 0
              and categoria !~* :impessoal
              and categoria !~* :varejo
              and categoria !~* 'alugu'
              and coalesce(fornecedor_nome, '') !~* :imovel
            group by politico_id, fornecedor_documento
        ),
        candidatos as (
            select * from base
            where notas >= 6 and meses >= 6 and total >= 30000
              and notas::float / (ultima - primeira + 1) >= 0.5
        ),
        fornecedor as (
            select fornecedor_documento as doc, sum(valor_liquido) as total_fornecedor,
                   count(distinct politico_id) as clientes
            from despesa_gabinete
            where fornecedor_documento in (select doc from candidatos) and valor_liquido > 0
            group by fornecedor_documento
        )
        select c.*, f.total_fornecedor, f.clientes
        from candidatos c join fornecedor f using (doc)
        """,
    )
    out = []
    for r in rows:
        if not cnpj_valido(r["doc"]):
            continue
        faixa = r["ultima"] - r["primeira"] + 1
        densidade = r["notas"] / faixa
        participacao = float(r["total"] / r["total_fornecedor"]) if r["total_fornecedor"] else 1
        s = score(
            20,
            (30, escala(densidade, 0.5, 0.95)),
            (15, escala(r["meses"], 6, 36)),
            (20, escala_log(float(r["total"]), 30_000, 1_000_000)),
            (15, escala(participacao, 0.5, 1.0)),
        )
        out.append(
            _alerta(
                "notas_sequenciais",
                f"{r['politico_id']}:{r['doc']}",
                s,
                politico_id=r["politico_id"],
                titulo=f"{r['nome']} emite notas quase só para este gabinete",
                descricao=(
                    f"Em {r['meses']} meses, o gabinete recebeu {r['notas']} das "
                    f"{faixa} notas numeradas de {r['primeira']} a {r['ultima']} "
                    f"({_pct(densidade)} da numeração), somando {_brl(r['total'])}. "
                    f"Uma empresa com outros clientes emitiria notas para eles entre essas. "
                    f"Este gabinete responde por {_pct(participacao)} do que o fornecedor "
                    f"recebeu da cota ({r['clientes']} gabinete(s) no total)."
                ),
                evidencias={
                    "metricas": {
                        "notas": r["notas"],
                        "numeracao_inicio": r["primeira"],
                        "numeracao_fim": r["ultima"],
                        "densidade": round(densidade, 3),
                        "meses": r["meses"],
                        "total": r["total"],
                        "participacao_no_fornecedor": round(participacao, 3),
                        "gabinetes_clientes": r["clientes"],
                        "categoria": r["categoria"],
                    },
                    "documentos": [{"url": u} for u in (r["urls"] or [])],
                },
                ano_inicio=r["ano_inicio"],
                ano_fim=r["ano_fim"],
                documento=r["doc"],
                nome=r["nome"],
                valor=r["total"],
            )
        )
    return out


async def fornecedor_exclusivo(session: AsyncSession) -> list[dict]:
    """Fornecedor de serviço sob encomenda que vive de um único gabinete."""
    rows = await _rows(
        session,
        r"""
        with forn as (
            select fornecedor_documento as doc, max(fornecedor_nome) as nome,
                   sum(valor_liquido) as total, count(distinct politico_id) as clientes,
                   count(distinct ano * 12 + mes) as meses
            from despesa_gabinete
            where fornecedor_documento ~ :cnpj and valor_liquido > 0
              and categoria ~* :sob_encomenda
              and coalesce(fornecedor_nome, '') !~* :imovel
            group by fornecedor_documento
            having sum(valor_liquido) >= 100000
        ),
        top as (
            select distinct on (fornecedor_documento)
                   fornecedor_documento as doc, politico_id, sum(valor_liquido) as total_politico,
                   min(ano) as ano_inicio, max(ano) as ano_fim,
                   mode() within group (order by categoria) as categoria
            from despesa_gabinete
            where fornecedor_documento in (select doc from forn) and valor_liquido > 0
              and categoria ~* :sob_encomenda and politico_id is not null
            group by fornecedor_documento, politico_id
            order by fornecedor_documento, sum(valor_liquido) desc
        )
        select f.*, t.politico_id, t.total_politico, t.ano_inicio, t.ano_fim, t.categoria
        from forn f join top t using (doc)
        where t.total_politico / f.total >= 0.9 and f.meses >= 12
        """,
    )
    out = []
    for r in rows:
        if not cnpj_valido(r["doc"]):
            continue
        participacao = float(r["total_politico"] / r["total"])
        s = score(
            20,
            (15, escala(participacao, 0.9, 1.0)),
            (30, escala_log(float(r["total_politico"]), 100_000, 3_000_000)),
            (10, escala(r["meses"], 12, 60)),
        )
        out.append(
            _alerta(
                "fornecedor_exclusivo",
                f"{r['politico_id']}:{r['doc']}",
                s,
                politico_id=r["politico_id"],
                titulo=f"{r['nome']} recebe da cota quase só deste gabinete",
                descricao=(
                    f"{_pct(participacao)} dos {_brl(r['total'])} que o fornecedor recebeu da "
                    f"cota parlamentar ({r['categoria'].lower().rstrip('.')}) vieram deste "
                    f"gabinete, ao longo de {r['meses']} meses. Exclusividade sozinha não prova "
                    f"irregularidade, mas é o padrão das empresas de fachada já identificadas "
                    f"na cota."
                ),
                evidencias={
                    "metricas": {
                        "participacao": round(participacao, 3),
                        "total_fornecedor": r["total"],
                        "total_gabinete": r["total_politico"],
                        "gabinetes_clientes": r["clientes"],
                        "meses": r["meses"],
                        "categoria": r["categoria"],
                    }
                },
                ano_inicio=r["ano_inicio"],
                ano_fim=r["ano_fim"],
                documento=r["doc"],
                nome=r["nome"],
                valor=r["total_politico"],
            )
        )
    return out


async def valor_atipico_nota(session: AsyncSession) -> list[dict]:
    """Nota isolada muito acima do que a categoria costuma ter (ex.: refeição de R$ 27 mil)."""
    rows = await _rows(
        session,
        r"""
        with p as (
            select verba, categoria,
                   percentile_cont(0.5) within group (order by valor_liquido) as p50,
                   percentile_cont(0.99) within group (order by valor_liquido) as p99
            from despesa_gabinete
            where valor_liquido > 0
            group by verba, categoria
            having count(*) >= 1000
        )
        select d.politico_id, count(*) as notas, sum(d.valor_liquido) as total,
               max(d.valor_liquido / p.p99::numeric) as maior_razao,
               min(d.ano) as ano_inicio, max(d.ano) as ano_fim,
               jsonb_agg(jsonb_build_object(
                   'despesa_id', d.id, 'ano', d.ano, 'mes', d.mes, 'categoria', d.categoria,
                   'valor', d.valor_liquido, 'mediana_categoria', round(p.p50::numeric, 2),
                   'p99_categoria', round(p.p99::numeric, 2),
                   'fornecedor', d.fornecedor_nome, 'fornecedor_documento',
                   d.fornecedor_documento, 'url', d.documento_url)
                   order by d.valor_liquido desc) as linhas
        from despesa_gabinete d join p using (verba, categoria)
        where d.politico_id is not null
          and d.categoria !~* :impessoal
          and d.valor_liquido >= greatest(5 * p.p99, 3000)
        group by d.politico_id
        """,
    )
    out = []
    for r in rows:
        maior = r["linhas"][0]
        s = score(
            35,
            (25, escala(float(r["maior_razao"]), 5, 30)),
            (20, escala_log(float(r["total"]), 3_000, 300_000)),
            (10, escala(r["notas"], 1, 5)),
        )
        out.append(
            _alerta(
                "valor_atipico_nota",
                str(r["politico_id"]),
                s,
                politico_id=r["politico_id"],
                titulo=(
                    f"{r['notas']} nota(s) com valor fora da realidade da categoria "
                    f"(maior: {_brl(maior['valor'])})"
                ),
                descricao=(
                    f"Notas de 5 a {float(r['maior_razao']):.0f} vezes o percentil 99 da própria "
                    f"categoria, somando {_brl(r['total'])}. A maior, em "
                    f"{maior['categoria'].lower().rstrip('.')}, tem {_brl(maior['valor'])} "
                    f"quando a nota típica é {_brl(maior['mediana_categoria'])}."
                ),
                evidencias={
                    "metricas": {
                        "notas": r["notas"],
                        "total": r["total"],
                        "maior_razao_p99": round(float(r["maior_razao"]), 1),
                    },
                    "documentos": r["linhas"][:20],
                },
                ano_inicio=r["ano_inicio"],
                ano_fim=r["ano_fim"],
                valor=r["total"],
            )
        )
    return out


async def digitos_atipicos(session: AsyncSession) -> list[dict]:
    """Primeiros dígitos dos valores muito diferentes dos de outros gabinetes com o mesmo
    perfil de gasto (teste de Benford ajustado aos pares)."""
    rows = await _rows(
        session,
        r"""
        with v as (
            select distinct politico_id, verba, categoria, fornecedor_documento, valor_liquido
            from despesa_gabinete
            where politico_id is not null and valor_liquido >= 10
              and categoria !~* :impessoal
        )
        select politico_id, verba, categoria,
               left(floor(valor_liquido)::bigint::text, 1)::int as digito, count(*) as n
        from v group by 1, 2, 3, 4
        """,
    )
    # contagens por político e categoria; a base junta todos os gabinetes
    por_politico: dict[int, dict[tuple[str, str], dict[int, int]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    base: dict[tuple[str, str], dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        cat = (r["verba"], r["categoria"])
        por_politico[r["politico_id"]][cat][r["digito"]] = r["n"]
        base[cat][r["digito"]] += r["n"]
    base_dist = {cat: distribuicao(c) for cat, c in base.items()}

    medidas: dict[int, tuple[float, int, dict[int, int], dict[int, float]]] = {}
    for pid, cats in por_politico.items():
        n = sum(sum(c.values()) for c in cats.values())
        if n < 300:
            continue
        esperado = mistura([(sum(c.values()), base_dist[cat]) for cat, c in cats.items()])
        observado: dict[int, int] = defaultdict(int)
        for c in cats.values():
            for d, q in c.items():
                observado[d] += q
        medidas[pid] = (desvio_digitos(observado, esperado), n, dict(observado), esperado)

    todos = [m[0] for m in medidas.values()]
    if len(todos) < 30:
        return []
    out = []
    for pid, (mad, n, observado, esperado) in medidas.items():
        z = z_robusto(mad, todos)
        if z < 3.5:
            continue
        excesso = max(range(1, 10), key=lambda d: observado.get(d, 0) / n - esperado[d])
        s = score(25, (35, escala(z, 3.5, 10)), (5, escala(n, 300, 2000)))
        out.append(
            _alerta(
                "digitos_atipicos",
                str(pid),
                s,
                politico_id=pid,
                titulo="Valores das notas com padrão de dígitos atípico",
                descricao=(
                    f"Em {n} valores distintos, os primeiros dígitos se afastam do esperado "
                    f"para o mesmo perfil de gasto (desvio {mad:.4f}, {z:.1f} desvios robustos "
                    f"acima dos demais gabinetes). O dígito {excesso} aparece em "
                    f"{_pct(observado.get(excesso, 0) / n)} dos valores, contra "
                    f"{_pct(esperado[excesso])} esperados. Valores escolhidos, e não medidos, "
                    f"deixam essa marca; confira as notas que começam com {excesso}."
                ),
                evidencias={
                    "metricas": {
                        "valores": n,
                        "desvio": round(mad, 5),
                        "z_robusto": round(z, 2),
                        "digito_em_excesso": excesso,
                    },
                    "distribuicao": {
                        str(d): {
                            "observado": round(observado.get(d, 0) / n, 4),
                            "esperado": round(esperado[d], 4),
                            "benford": round(BENFORD[d], 4),
                        }
                        for d in range(1, 10)
                    },
                },
            )
        )
    return out


async def nota_extemporanea(session: AsyncSession) -> list[dict]:
    """Nota emitida muito antes do mês em que foi reembolsada (prazo da cota é 90 dias)."""
    rows = await _rows(
        session,
        r"""
        select politico_id, count(*) as notas, sum(valor_liquido) as total,
               min(ano) as ano_inicio, max(ano) as ano_fim,
               max(make_date(ano, mes, 1) - data_emissao) as maior_atraso,
               (jsonb_agg(jsonb_build_object(
                   'despesa_id', id, 'ano', ano, 'mes', mes, 'data_emissao', data_emissao,
                   'valor', valor_liquido, 'fornecedor', fornecedor_nome, 'url', documento_url)
                   order by valor_liquido desc)) as linhas
        from despesa_gabinete
        where politico_id is not null and valor_liquido > 0
          and data_emissao >= date '2000-01-01'
          and data_emissao < make_date(ano, mes, 1) - 120
          and categoria !~* :impessoal
        group by politico_id
        having sum(valor_liquido) >= 1000
        """,
    )
    out = []
    for r in rows:
        s = score(
            20,
            (25, escala_log(float(r["total"]), 1_000, 100_000)),
            (10, escala(r["notas"], 1, 20)),
        )
        out.append(
            _alerta(
                "nota_extemporanea",
                str(r["politico_id"]),
                s,
                politico_id=r["politico_id"],
                titulo=f"{r['notas']} nota(s) reembolsada(s) mais de 4 meses após a emissão",
                descricao=(
                    f"{_brl(r['total'])} em notas emitidas mais de 120 dias antes do mês do "
                    f"reembolso (maior atraso: {r['maior_atraso']} dias). A cota exige "
                    f"apresentação em até 90 dias; nota antiga pode ser de outra finalidade ou "
                    f"de antes do mandato."
                ),
                evidencias={
                    "metricas": {"notas": r["notas"], "total": r["total"]},
                    "documentos": r["linhas"][:20],
                },
                ano_inicio=r["ano_inicio"],
                ano_fim=r["ano_fim"],
                valor=r["total"],
            )
        )
    return out


# ----------------------------------------------------------------------------- emendas


async def fornecedor_favorecido(session: AsyncSession) -> list[dict]:
    """Mesma entidade privada é paga pelo gabinete e recebe emenda do mesmo parlamentar."""
    rows = await _rows(
        session,
        r"""
        with g as (
            select politico_id, fornecedor_documento as doc, sum(valor_liquido) as gabinete,
                   max(fornecedor_nome) as nome_gabinete, count(*) as notas,
                   min(ano) as a0, max(ano) as a1
            from despesa_gabinete
            where politico_id is not null and fornecedor_documento ~ :cnpj
              and categoria !~* :impessoal
            group by politico_id, fornecedor_documento
            having sum(valor_liquido) >= 5000
        ),
        e as (
            select politico_id, favorecido_documento as doc, sum(valor) as emendas,
                   max(favorecido_nome) as nome, max(natureza_juridica) as natureza,
                   count(distinct emenda_codigo) as qtd_emendas,
                   array_agg(distinct emenda_codigo) as codigos,
                   min(ano) as a0, max(ano) as a1
            from emenda_favorecido
            where politico_id is not null and favorecido_documento ~ :cnpj
            group by politico_id, favorecido_documento
            having sum(valor) >= 10000
        )
        select g.politico_id, g.doc, g.gabinete, g.nome_gabinete, g.notas, e.emendas, e.nome,
               e.natureza, e.qtd_emendas, e.codigos,
               least(g.a0, e.a0) as ano_inicio, greatest(g.a1, e.a1) as ano_fim
        from g join e using (politico_id, doc)
        where coalesce(e.natureza, '') !~* :publica
        """,
    )
    out = []
    for r in rows:
        if not cnpj_valido(r["doc"]):
            continue
        sfl = _casa(SEM_FINS_LUCRATIVOS, r["natureza"])
        s = score(
            50,
            (15, 1.0 if sfl else 0.0),
            (20, escala_log(float(r["emendas"]), 10_000, 2_000_000)),
            (15, escala_log(float(r["gabinete"]), 5_000, 300_000)),
        )
        out.append(
            _alerta(
                "fornecedor_favorecido",
                f"{r['politico_id']}:{r['doc']}",
                s,
                politico_id=r["politico_id"],
                titulo=f"{r['nome']}: paga pelo gabinete e beneficiada por emenda do mesmo autor",
                descricao=(
                    f"O gabinete pagou {_brl(r['gabinete'])} a esta entidade em {r['notas']} "
                    f"notas da cota, e emendas do mesmo parlamentar transferiram "
                    f"{_brl(r['emendas'])} a ela ({r['qtd_emendas']} emenda(s)). Natureza: "
                    f"{r['natureza'] or 'não informada'}. Dinheiro público chegando à mesma "
                    f"entidade por dois caminhos controlados pela mesma pessoa."
                ),
                evidencias={
                    "metricas": {
                        "pago_pelo_gabinete": r["gabinete"],
                        "recebido_de_emendas": r["emendas"],
                        "notas_gabinete": r["notas"],
                        "emendas": r["qtd_emendas"],
                        "natureza_juridica": r["natureza"],
                        "nome_na_cota": r["nome_gabinete"],
                    },
                    "emendas": (r["codigos"] or [])[:20],
                },
                ano_inicio=r["ano_inicio"],
                ano_fim=r["ano_fim"],
                documento=r["doc"],
                nome=r["nome"],
                valor=r["gabinete"] + r["emendas"],
            )
        )
    return out


async def favorecido_dependente(session: AsyncSession) -> list[dict]:
    """Entidade privada (ONG, associação, empresa) que recebe emendas quase só de um autor."""
    rows = await _rows(
        session,
        r"""
        with tot as (
            select favorecido_documento as doc, max(favorecido_nome) as nome,
                   max(natureza_juridica) as natureza, sum(valor) as total,
                   count(distinct politico_id) as autores
            from emenda_favorecido
            where favorecido_documento ~ :cnpj
            group by favorecido_documento
            having sum(valor) >= 500000
        ),
        por as (
            select favorecido_documento as doc, politico_id, sum(valor) as do_autor,
                   count(distinct emenda_codigo) as qtd_emendas,
                   (array_agg(distinct emenda_codigo))[1:20] as codigos,
                   min(ano) as ano_inicio, max(ano) as ano_fim
            from emenda_favorecido
            where politico_id is not null
              and favorecido_documento in (select doc from tot)
            group by favorecido_documento, politico_id
        )
        select tot.*, por.politico_id, por.do_autor, por.qtd_emendas, por.codigos,
               por.ano_inicio, por.ano_fim
        from por join tot using (doc)
        where por.do_autor / tot.total >= 0.8
          and coalesce(tot.natureza, '') ~* :privada
          and coalesce(tot.natureza, '') !~* :publica
        """,
    )
    out = []
    for r in rows:
        sfl = _casa(SEM_FINS_LUCRATIVOS, r["natureza"])
        minimo = 500_000 if sfl else 1_000_000
        # uma doação isolada a entidade conhecida é comum; dependência é repetição
        if float(r["do_autor"]) < minimo or r["qtd_emendas"] < 2 or not cnpj_valido(r["doc"]):
            continue
        participacao = float(r["do_autor"] / r["total"])
        anos = r["ano_fim"] - r["ano_inicio"] + 1
        s = score(
            20,
            (10, 1.0 if sfl else 0.0),
            # firma de uma pessoa só recebendo milhões de emenda
            (10, 1.0 if _casa(FIRMA_INDIVIDUAL, r["natureza"]) else 0.0),
            (10, escala(participacao, 0.8, 1.0)),
            (30, escala_log(float(r["do_autor"]), minimo, 20_000_000)),
            (15, escala(anos, 1, 4)),
        )
        tipo = "Entidade sem fins lucrativos" if sfl else "Empresa"
        out.append(
            _alerta(
                "favorecido_dependente",
                f"{r['politico_id']}:{r['doc']}",
                s,
                politico_id=r["politico_id"],
                titulo=f"{tipo} {r['nome']} depende das emendas de um só parlamentar",
                descricao=(
                    f"{_pct(participacao)} dos {_brl(r['total'])} em emendas recebidos por "
                    f"{r['nome']} ({r['natureza']}) vieram deste autor, em "
                    f"{r['qtd_emendas']} emenda(s). Entidade privada financiada por um único "
                    f"padrinho é o arranjo típico de desvio via ONG/empresa intermediária."
                ),
                evidencias={
                    "metricas": {
                        "participacao": round(participacao, 3),
                        "do_autor": r["do_autor"],
                        "total_recebido": r["total"],
                        "autores": r["autores"],
                        "natureza_juridica": r["natureza"],
                    },
                    "emendas": r["codigos"] or [],
                },
                ano_inicio=r["ano_inicio"],
                ano_fim=r["ano_fim"],
                documento=r["doc"],
                nome=r["nome"],
                valor=r["do_autor"],
            )
        )
    return out


async def emenda_fora_da_base(session: AsyncSession) -> list[dict]:
    """Emendas individuais pagas, em boa parte, fora da UF pela qual o autor foi eleito."""
    rows = await _rows(
        session,
        r"""
        with e as (
            select e.politico_id, e.ano, e.uf, e.municipio_nome,
                   e.valor_pago + e.valor_rp_pago as pago,
                   coalesce(
                       (select m.uf from mandato m
                        where m.politico_id = e.politico_id and m.uf is not null
                          and make_date(e.ano, 7, 1)
                              between m.inicio and coalesce(m.fim, 'infinity')
                        order by m.inicio desc limit 1),
                       (select m.uf from mandato m
                        where m.politico_id = e.politico_id and m.uf is not null
                        order by m.inicio desc limit 1)
                   ) as uf_autor
            from emenda e
            where e.politico_id is not null and e.tipo ilike '%individual%'
              and e.uf is not null
        )
        select politico_id, ano, max(uf_autor) as uf_autor, sum(pago) as total,
               sum(pago) filter (where uf <> uf_autor) as fora,
               jsonb_object_agg(coalesce(uf, '?'), pago_uf) as por_uf
        from (
            select politico_id, ano, uf, uf_autor, pago,
                   sum(pago) over (partition by politico_id, ano, uf) as pago_uf
            from e where uf_autor is not null
        ) x
        group by politico_id, ano
        having sum(pago) filter (where uf <> uf_autor) >= 500000
           and sum(pago) filter (where uf <> uf_autor) / nullif(sum(pago), 0) >= 0.25
        """,
    )
    out = []
    for r in rows:
        participacao = float(r["fora"] / r["total"])
        s = score(
            25,
            (20, escala(participacao, 0.25, 1.0)),
            (20, escala_log(float(r["fora"]), 500_000, 20_000_000)),
        )
        destinos = sorted(
            ((uf, v) for uf, v in r["por_uf"].items() if uf != r["uf_autor"]),
            key=lambda x: -x[1],
        )
        out.append(
            _alerta(
                "emenda_fora_da_base",
                f"{r['politico_id']}:{r['ano']}",
                s,
                politico_id=r["politico_id"],
                titulo=f"{_pct(participacao)} das emendas individuais de {r['ano']} fora de "
                f"{r['uf_autor']}",
                descricao=(
                    f"{_brl(r['fora'])} de {_brl(r['total'])} pagos em emendas individuais "
                    f"foram para fora da UF de eleição ({r['uf_autor']}), principalmente "
                    f"{', '.join(uf for uf, _ in destinos[:3])}. Pode ser legítimo, mas foge do "
                    f"padrão e merece saber quem recebeu."
                ),
                evidencias={
                    "metricas": {
                        "uf_autor": r["uf_autor"],
                        "total_pago": r["total"],
                        "fora_da_uf": r["fora"],
                        "participacao": round(participacao, 3),
                    },
                    "por_uf": dict(destinos[:10]),
                },
                ano_inicio=r["ano"],
                valor=r["fora"],
            )
        )
    return out


# ----------------------------------------------------------------------------- eleições

MOTIVOS_GRAVES = {
    "Compra de voto (Lei 9.504/97)": 85,
    "Abuso de poder (LC 64/90)": 80,
    "Gasto ilícito de recursos (Lei 9.504/97)": 75,
    "Ficha limpa (LC 64/90)": 70,
    "Conduta vedada (Lei 9.504/97)": 60,
}


async def historico_eleitoral(session: AsyncSession) -> list[dict]:
    """Candidatura barrada pelo TSE por compra de voto, abuso de poder, ficha limpa..."""
    rows = await _rows(
        session,
        r"""
        select politico_id, sq_candidato, ano, cargo, uf, ue_nome, situacao_candidatura,
               motivos_situacao
        from candidatura
        where motivos_situacao && array[
                'Compra de voto (Lei 9.504/97)', 'Abuso de poder (LC 64/90)',
                'Gasto ilícito de recursos (Lei 9.504/97)', 'Ficha limpa (LC 64/90)',
                'Conduta vedada (Lei 9.504/97)']::varchar[]
          and coalesce(situacao_candidatura, '') <> 'APTO'
        """,
    )
    out = []
    for r in rows:
        graves = [m for m in r["motivos_situacao"] if m in MOTIVOS_GRAVES]
        s = float(max(MOTIVOS_GRAVES[m] for m in graves))
        out.append(
            _alerta(
                "historico_eleitoral",
                str(r["sq_candidato"]),
                s,
                politico_id=r["politico_id"],
                titulo=f"Candidatura de {r['ano']} barrada: {', '.join(graves)}",
                descricao=(
                    f"Candidatura a {r['cargo'].lower()} em {r['ue_nome']} ({r['ano']}) ficou "
                    f"{(r['situacao_candidatura'] or '').lower()} pelo TSE. Motivos registrados: "
                    f"{', '.join(r['motivos_situacao'])}. Fato registrado pela Justiça Eleitoral, "
                    f"não inferência; confira se houve recurso."
                ),
                evidencias={
                    "metricas": {
                        "sq_candidato": r["sq_candidato"],
                        "situacao": r["situacao_candidatura"],
                        "motivos": r["motivos_situacao"],
                    }
                },
                ano_inicio=r["ano"],
            )
        )
    return out


def _casa(padrao: str, texto: str | None) -> bool:
    return bool(texto and re.search(padrao, texto, re.IGNORECASE))


CATALOGO: dict[str, Detector] = {
    d.codigo: d
    for d in [
        Detector(
            "nota_duplicada",
            "Nota fiscal reembolsada em duplicidade",
            "gabinete",
            1.0,
            "Agrupa despesas por fornecedor, número da nota, valor e data de emissão. Mais de uma "
            "linha com identificadores de documento diferentes, sem estorno (valor negativo) "
            "para a mesma nota, é reembolso em dobro. Ignora notas abaixo de R$ 100, números com "
            "menos de 3 dígitos e categorias de cobrança impessoal (passagens, telefonia, "
            "pedágio, Correios).",
            nota_duplicada,
        ),
        Detector(
            "notas_sequenciais",
            "Fornecedor que só emite notas para o gabinete",
            "gabinete",
            0.8,
            "Para cada par gabinete-fornecedor com 6+ notas numéricas em 6+ meses e R$ 30 mil+, "
            "compara a quantidade de notas recebidas com a faixa de numeração usada (primeira a "
            "última). Empresa com outros clientes emite notas para eles no intervalo; se o "
            "gabinete tem metade ou mais da numeração, ele é praticamente o único cliente. "
            "Exclui varejo de cupom fiscal (combustível, alimentação, hospedagem) e aluguel.",
            notas_sequenciais,
        ),
        Detector(
            "fornecedor_exclusivo",
            "Fornecedor que vive de um único gabinete",
            "gabinete",
            0.4,
            "Fornecedores de serviço sob encomenda (divulgação, consultoria, locação de "
            "veículos, segurança, fretamento) com R$ 100 mil+ recebidos da cota em 12+ meses, "
            "dos quais 90%+ vieram de um só gabinete.",
            fornecedor_exclusivo,
        ),
        Detector(
            "valor_atipico_nota",
            "Nota com valor fora da realidade da categoria",
            "gabinete",
            0.5,
            "Notas de R$ 3 mil+ com valor 5x+ o percentil 99 da própria categoria e casa "
            "(categorias com 1.000+ notas). Pega, por exemplo, refeição do parlamentar ou "
            "hospedagem de dezenas de milhares de reais numa nota só.",
            valor_atipico_nota,
        ),
        Detector(
            "digitos_atipicos",
            "Padrão de dígitos atípico nos valores",
            "gabinete",
            0.25,
            "Teste de Benford ajustado aos pares: preços da cota não seguem Benford puro "
            "(combustível e refeição concentram valores em 1 e 2), então o esperado para cada "
            "gabinete é a distribuição de primeiros dígitos de todos os gabinetes, ponderada "
            "pelo seu próprio mix de categorias. Mede o desvio absoluto médio e alerta quando "
            "ele fica 3,5+ desvios robustos acima do dos demais. Cada par fornecedor-valor conta "
            "uma vez; exige 300+ valores.",
            digitos_atipicos,
        ),
        Detector(
            "nota_extemporanea",
            "Nota reembolsada muito depois da emissão",
            "gabinete",
            0.25,
            "Notas emitidas mais de 120 dias antes do mês de reembolso (a cota dá 90 dias), "
            "somando R$ 1 mil+ por parlamentar.",
            nota_extemporanea,
        ),
        Detector(
            "fornecedor_favorecido",
            "Fornecedor do gabinete também recebe emenda do parlamentar",
            "emendas",
            0.9,
            "Cruza CNPJs pagos pela cota (R$ 5 mil+) com favorecidos de emendas do mesmo autor "
            "(R$ 10 mil+). Exclui entes públicos, fundos, autarquias e sociedades anônimas; "
            "associações e fundações privadas pesam mais.",
            fornecedor_favorecido,
        ),
        Detector(
            "favorecido_dependente",
            "Entidade privada financiada por um só parlamentar",
            "emendas",
            0.5,
            "Associações, fundações, organizações religiosas/sociais (R$ 500 mil+) e empresas "
            "(R$ 1 milhão+) que receberam 80%+ do dinheiro de emendas de um único autor, em 2+ "
            "emendas. Pesa mais quanto mais anos de dependência e quando é firma individual.",
            favorecido_dependente,
        ),
        Detector(
            "emenda_fora_da_base",
            "Emendas fora da UF de eleição",
            "emendas",
            0.3,
            "Emendas individuais pagas no ano: alerta quando 25%+ (e R$ 500 mil+) foram para "
            "outra UF que não a do mandato do autor naquele ano.",
            emenda_fora_da_base,
        ),
        Detector(
            "historico_eleitoral",
            "Candidatura barrada por ilícito eleitoral",
            "eleicoes",
            0.6,
            "Candidaturas não aptas no TSE com motivo de compra de voto, abuso de poder, gasto "
            "ilícito, conduta vedada ou ficha limpa (arquivo motivo_cassacao).",
            historico_eleitoral,
        ),
    ]
}
