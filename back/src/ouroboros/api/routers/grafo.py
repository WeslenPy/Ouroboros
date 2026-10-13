"""Grafos de relações para visualização: quem se liga a quem, por quanto dinheiro.

Cada grafo tem um centro (político, empresa/entidade ou município) e se ramifica em hubs
temáticos (carreira, gastos do gabinete, emendas) para ficar legível por qualquer pessoa:

    político -> Gastos do gabinete -> categoria -> fornecedor -> outros políticos que pagaram
    político -> Emendas -> área (Saúde...) -> município de destino / quem recebeu
    político -> Carreira -> partidos, cargos, eleições
    político -> Obras -> convênio/obra -> empreiteira -> outros políticos que financiaram obras dela
    obra -> emendas (autores), local (município, convenente), quem executou (empreiteiras)

`nivel` e `pai` orientam o layout radial no front; `chave` permite recentrar o grafo no nó.
"""

from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import String, cast, desc, func, select
from sqlalchemy.dialects.postgresql import distinct_on

from ouroboros.api.deps import Session
from ouroboros.api.schemas import Grafo, GrafoAresta, GrafoNo
from ouroboros.core.privacy import digits
from ouroboros.models import (
    Candidatura,
    Convenio,
    ConvenioContrato,
    ConvenioEmenda,
    ConvenioFornecedor,
    DespesaGabinete,
    Emenda,
    EmendaFavorecido,
    Ente,
    Mandato,
    Partido,
    Politico,
)

router = APIRouter(prefix="/grafo", tags=["grafo"])

CARGO = {
    "presidente": "Presidente",
    "governador": "Governador(a)",
    "prefeito": "Prefeito(a)",
    "senador": "Senador(a)",
    "deputado_federal": "Deputado(a) federal",
    "deputado_estadual": "Deputado(a) estadual",
    "vereador": "Vereador(a)",
}
ZERO = Decimal("0")
D = DespesaGabinete
E = Emenda
F = EmendaFavorecido
PAGO = E.valor_pago + E.valor_rp_pago
C = Convenio
CE = ConvenioEmenda
K = ConvenioContrato


class _Grafo:
    def __init__(self, centro: str) -> None:
        self.centro = centro
        self.nos: dict[str, GrafoNo] = {}
        self.arestas: dict[str, GrafoAresta] = {}

    def no(self, id: str, **kw) -> str:
        if id not in self.nos:
            self.nos[id] = GrafoNo(id=id, **kw)
        return id

    def aresta(self, origem: str, destino: str, tipo: str, valor: Decimal | None = None) -> None:
        key = f"{origem}>{destino}"
        atual = self.arestas.get(key)
        if atual is None:
            self.arestas[key] = GrafoAresta(
                id=key, origem=origem, destino=destino, tipo=tipo, valor=valor
            )
        elif valor is not None:
            atual.valor = (atual.valor or ZERO) + valor

    def build(self) -> Grafo:
        return Grafo(
            centro=self.centro, nos=list(self.nos.values()), arestas=list(self.arestas.values())
        )


def _titulo(texto: str | None) -> str:
    """Frase: 'SAÚDE' -> 'Saúde' (categorias, áreas). Texto já em caixa mista fica igual."""
    if not texto:
        return "—"
    if texto.isupper() and len(texto) > 4:
        return texto.capitalize()
    return texto


_MINUSCULAS = {"de", "da", "do", "das", "dos", "e", "em", "para", "a", "o"}
_SIGLAS = {"ltda", "sa", "s/a", "me", "epp", "eireli", "uf", "cia", "ong", "sus", "rj", "sp"}


def _nome(texto: str | None) -> str:
    """Nome próprio: 'RIO DE JANEIRO (UF)' -> 'Rio de Janeiro (UF)', 'TAM LINHAS SA' -> 'Tam
    Linhas SA'. Só mexe em texto todo em maiúsculas."""
    if not texto:
        return "—"
    if not texto.isupper():
        return texto
    partes = []
    for i, palavra in enumerate(texto.lower().split()):
        nucleo = palavra.strip("().,-")
        if nucleo in _SIGLAS:
            partes.append(palavra.upper())
        elif i > 0 and nucleo in _MINUSCULAS:
            partes.append(palavra)
        else:
            partes.append(palavra[:1].upper() + palavra[1:] if palavra[0].isalpha() else
                          palavra[:2].upper() + palavra[2:])  # fmt: skip
    return " ".join(partes)


def _doc_id(documento: str | None, nome: str | None) -> tuple[str, str | None]:
    """ID do nó de empresa/pessoa. CNPJ identifica; CPF mascarado não (vira chave por nome)."""
    if documento and "*" not in documento:
        return f"doc:{documento}", documento
    return f"pessoa:{documento or ''}:{nome or ''}", None


async def _politicos(session: Session, ids: set[int]) -> dict[int, dict]:
    """Nome, foto e partido atual (do último mandato) para rotular nós de político."""
    if not ids:
        return {}
    out: dict[int, dict] = {}
    for p in await session.scalars(select(Politico).where(Politico.id.in_(ids))):
        out[p.id] = {
            "nome": p.nome,
            "imagem": f"/v1/fotos/{p.foto_id}" if p.foto_id else None,
            "partido": None,
            "cargo": None,
        }
    ultimos = await session.execute(
        select(
            Mandato.politico_id, Mandato.partido_sigla, Mandato.partidos, Mandato.cargo, Mandato.uf
        )
        .ext(distinct_on(Mandato.politico_id))
        .where(Mandato.politico_id.in_(ids))
        .order_by(Mandato.politico_id, Mandato.inicio.desc().nulls_last())
    )
    for pid, sigla, partidos, cargo, uf in ultimos:
        if pid in out:
            out[pid]["partido"] = sigla or (partidos[-1] if partidos else None)
            out[pid]["cargo"] = " · ".join(x for x in (CARGO.get(cargo, cargo), uf) if x)
    return out


def _detalhe_politico(info: dict) -> str | None:
    return " · ".join(x for x in (info.get("partido"), info.get("cargo")) if x) or None


async def _conexoes_despesa(
    session: Session, g: _Grafo, docs: list[tuple[str, str]], excluir: int | None, ano: int | None
) -> set[int]:
    """Outros políticos que pagaram o mesmo fornecedor (até 3 por fornecedor)."""
    ligados: set[int] = set()
    pares: list[tuple[str, int, Decimal]] = []
    for no_id, documento in docs:
        stmt = (
            select(D.politico_id, func.sum(D.valor_liquido).label("t"))
            .where(D.fornecedor_documento == documento, D.politico_id.is_not(None))
            .group_by(D.politico_id)
            .order_by(desc("t"))
            .limit(4)
        )
        if excluir is not None:
            stmt = stmt.where(D.politico_id != excluir)
        if ano:
            stmt = stmt.where(D.ano == ano)
        for pid, total in (await session.execute(stmt)).all()[:3]:
            pares.append((no_id, pid, total))
            ligados.add(pid)
    return _ligar_politicos(g, pares, ligados, "conexao")


async def _conexoes_emenda(
    session: Session, g: _Grafo, docs: list[tuple[str, str]], excluir: int | None, ano: int | None
) -> set[int]:
    """Outros políticos que mandaram emendas ao mesmo favorecido (até 3 por favorecido)."""
    pares: list[tuple[str, int, Decimal]] = []
    ligados: set[int] = set()
    for no_id, documento in docs:
        stmt = (
            select(F.politico_id, func.sum(F.valor).label("t"))
            .where(F.favorecido_documento == documento, F.politico_id.is_not(None))
            .group_by(F.politico_id)
            .order_by(desc("t"))
            .limit(4)
        )
        if excluir is not None:
            stmt = stmt.where(F.politico_id != excluir)
        if ano:
            stmt = stmt.where(F.ano == ano)
        for pid, total in (await session.execute(stmt)).all()[:3]:
            pares.append((no_id, pid, total))
            ligados.add(pid)
    return _ligar_politicos(g, pares, ligados, "conexao")


def _ligar_politicos(
    g: _Grafo, pares: list[tuple[str, int, Decimal]], ligados: set[int], tipo: str
) -> set[int]:
    for no_id, pid, total in pares:
        pai = g.nos[no_id]
        g.no(
            f"politico:{pid}",
            tipo="politico",
            rotulo=f"#{pid}",
            nivel=pai.nivel + 1,
            grupo="conexoes",
            pai=no_id,
            chave=str(pid),
        )
        g.aresta(no_id, f"politico:{pid}", tipo, total)
    return ligados


async def _rotular_politicos(session: Session, g: _Grafo) -> None:
    ids = {int(n.chave) for n in g.nos.values() if n.tipo == "politico" and n.chave}
    infos = await _politicos(session, ids)
    for n in g.nos.values():
        if n.tipo == "politico" and n.chave and int(n.chave) in infos:
            info = infos[int(n.chave)]
            n.rotulo = info["nome"]
            n.imagem = info["imagem"]
            if n.id != g.centro:
                n.detalhe = _detalhe_politico(info)


# --------------------------------------------------------------------------- político


@router.get("/politico/{politico_id}", response_model=Grafo, summary="Rede de um político")
async def grafo_politico(
    politico_id: int,
    session: Session,
    ano: int | None = Query(None, ge=2000, le=2100, description="Só gastos/emendas deste ano"),
    limite: int = Query(8, ge=3, le=20, description="Máximo de fornecedores, destinos..."),
    conexoes: bool = Query(True, description="Incluir outros políticos ligados"),
) -> Grafo:
    p = await session.get(Politico, politico_id)
    if p is None:
        raise HTTPException(status_code=404, detail="político não encontrado")
    centro = f"politico:{p.id}"
    g = _Grafo(centro)
    g.no(centro, tipo="politico", rotulo=p.nome, nivel=0, grupo="centro", chave=str(p.id))

    await _carreira(session, g, p.id)
    fornecedores = await _gastos(session, g, p.id, ano, limite)
    favorecidos = await _emendas(session, g, p.id, ano, limite)
    financiadas = C.numero.in_(select(CE.convenio_numero).where(CE.politico_id == p.id))
    empreiteiras = await _obras(
        session,
        g,
        g.centro,
        [financiadas] + ([C.ano == ano] if ano else []),
        "Obras e convênios",
        limite,
    )
    if conexoes:
        await _conexoes_despesa(session, g, fornecedores[:4], p.id, ano)
        await _conexoes_emenda(session, g, favorecidos[:3], p.id, ano)
        await _conexoes_obra(session, g, empreiteiras[:3], p.id)
    await _rotular_politicos(session, g)
    centro_no = g.nos[centro]
    infos = await _politicos(session, {p.id})
    centro_no.detalhe = _detalhe_politico(infos.get(p.id, {}))
    return g.build()


async def _carreira(session: Session, g: _Grafo, politico_id: int) -> None:
    mandatos = list(
        await session.scalars(
            select(Mandato)
            .where(Mandato.politico_id == politico_id)
            .order_by(Mandato.inicio.desc().nulls_last())
            .limit(6)
        )
    )
    candidaturas = list(
        await session.scalars(
            select(Candidatura)
            .where(Candidatura.politico_id == politico_id)
            .order_by(Candidatura.ano.desc())
            .limit(5)
        )
    )
    if not mandatos and not candidaturas:
        return
    hub = g.no(
        "hub:carreira",
        tipo="hub",
        rotulo="Carreira política",
        detalhe=f"{len(mandatos)} mandatos · {len(candidaturas)} eleições",
        nivel=1,
        grupo="carreira",
        pai=g.centro,
    )
    g.aresta(g.centro, hub, "hub")

    siglas: list[str] = []
    for m in mandatos:
        anos = "–".join(str(d.year) for d in (m.inicio, m.fim) if d)
        no = g.no(
            f"cargo:{m.id}",
            tipo="cargo",
            rotulo=CARGO.get(m.cargo, str(m.cargo)),
            detalhe=" · ".join(x for x in (m.uf, anos) if x) or None,
            nivel=2,
            grupo="carreira",
            pai=hub,
        )
        g.aresta(hub, no, "mandato")
        siglas += m.partidos
    for c in candidaturas:
        situacao = "eleito(a)" if c.eleito else (c.situacao_turno or "não eleito(a)").lower()
        no = g.no(
            f"eleicao:{c.sq_candidato}",
            tipo="eleicao",
            rotulo=f"Eleição {c.ano}",
            detalhe=f"{_titulo(c.cargo)} · {situacao}",
            nivel=2,
            grupo="carreira",
            pai=hub,
        )
        g.aresta(hub, no, "candidatura")
        if c.partido_sigla:
            siglas.append(c.partido_sigla)

    unicas = list(dict.fromkeys(s for s in siglas if s))
    nomes = dict(
        (
            await session.execute(
                select(Partido.sigla, Partido.nome).where(Partido.sigla.in_(unicas))
            )
        ).all()
    )
    for sigla in unicas:
        no = g.no(
            f"partido:{sigla}",
            tipo="partido",
            rotulo=sigla,
            detalhe=_nome(nomes.get(sigla)),
            nivel=2,
            grupo="carreira",
            pai=hub,
            chave=sigla,
        )
        g.aresta(hub, no, "filiacao")


async def _gastos(
    session: Session, g: _Grafo, politico_id: int, ano: int | None, limite: int
) -> list[tuple[str, str]]:
    base = [D.politico_id == politico_id] + ([D.ano == ano] if ano else [])
    total, qtd = (
        await session.execute(
            select(func.coalesce(func.sum(D.valor_liquido), 0), func.count()).where(*base)
        )
    ).one()
    if not qtd:
        return []
    hub = g.no(
        "hub:gastos",
        tipo="hub",
        rotulo="Gastos do gabinete",
        detalhe=f"Cota parlamentar · {qtd} notas",
        valor=total,
        nivel=1,
        grupo="gastos",
        pai=g.centro,
    )
    g.aresta(g.centro, hub, "hub", total)

    categorias = (
        await session.execute(
            select(D.categoria, func.sum(D.valor_liquido).label("t"))
            .where(*base)
            .group_by(D.categoria)
            .order_by(desc("t"))
            .limit(6)
        )
    ).all()
    for categoria, valor in categorias:
        no = g.no(
            f"categoria:{categoria}",
            tipo="categoria",
            rotulo=_titulo(categoria),
            valor=valor,
            nivel=2,
            grupo="gastos",
            pai=hub,
        )
        g.aresta(hub, no, "gasto", valor)

    # fornecedor: total e categoria principal
    linhas = (
        await session.execute(
            select(
                D.fornecedor_documento,
                func.max(D.fornecedor_nome),
                D.categoria,
                func.sum(D.valor_liquido),
                func.count(),
            )
            .where(*base, D.fornecedor_documento.is_not(None))
            .group_by(D.fornecedor_documento, D.categoria)
        )
    ).all()
    por_doc: dict[str, dict] = {}
    for doc, nome, categoria, valor, q in linhas:
        d = por_doc.setdefault(doc, {"nome": nome, "total": ZERO, "q": 0, "cat": (ZERO, None)})
        d["total"] += valor
        d["q"] += q
        if valor > d["cat"][0]:
            d["cat"] = (valor, categoria)
    top = sorted(por_doc.items(), key=lambda kv: kv[1]["total"], reverse=True)[:limite]
    expandiveis: list[tuple[str, str]] = []
    for doc, d in top:
        no_id, chave = _doc_id(doc, d["nome"])
        pai = f"categoria:{d['cat'][1]}"
        pai = pai if pai in g.nos else hub
        g.no(
            no_id,
            tipo="fornecedor",
            rotulo=_nome(d["nome"]),
            detalhe=f"{d['q']} notas fiscais",
            valor=d["total"],
            nivel=g.nos[pai].nivel + 1,
            grupo="gastos",
            pai=pai,
            chave=chave,
        )
        g.aresta(pai, no_id, "pagamento", d["total"])
        if chave:
            expandiveis.append((no_id, chave))
    return expandiveis


async def _emendas(
    session: Session, g: _Grafo, politico_id: int, ano: int | None, limite: int
) -> list[tuple[str, str]]:
    base = [E.politico_id == politico_id] + ([E.ano == ano] if ano else [])
    qtd, empenhado, pago = (
        await session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(E.valor_empenhado), 0),
                func.coalesce(func.sum(PAGO), 0),
            ).where(*base)
        )
    ).one()
    if not qtd:
        return []
    hub = g.no(
        "hub:emendas",
        tipo="hub",
        rotulo="Emendas parlamentares",
        detalhe=f"{qtd} emendas · empenhado R$ {empenhado:,.0f}".replace(",", "."),
        valor=pago,
        nivel=1,
        grupo="emendas",
        pai=g.centro,
    )
    g.aresta(g.centro, hub, "hub", pago)

    areas = (
        await session.execute(
            select(E.funcao, func.sum(PAGO).label("t"), func.count())
            .where(*base)
            .group_by(E.funcao)
            .order_by(desc("t"))
            .limit(5)
        )
    ).all()
    for funcao, valor, q in areas:
        no = g.no(
            f"area:{funcao}",
            tipo="area",
            rotulo=_titulo(funcao) if funcao else "Sem área",
            detalhe=f"{q} emendas",
            valor=valor,
            nivel=2,
            grupo="emendas",
            pai=hub,
        )
        g.aresta(hub, no, "emenda", valor)

    # destinos (município ou localidade) com área principal
    destino = func.coalesce(cast(E.municipio_codigo_ibge, String), E.localidade)
    linhas = (
        await session.execute(
            select(
                destino,
                func.max(E.municipio_nome),
                func.max(E.uf),
                func.max(E.localidade),
                E.funcao,
                func.sum(PAGO),
            )
            .where(*base)
            .group_by(destino, E.funcao)
        )
    ).all()
    por_destino: dict[str, dict] = {}
    for chave, municipio, uf, localidade, funcao, valor in linhas:
        if chave is None:
            continue
        d = por_destino.setdefault(
            chave,
            {
                "rotulo": " - ".join(x for x in (_nome(municipio), uf) if x)
                if municipio
                else _nome(localidade),
                "municipio": bool(municipio),
                "total": ZERO,
                "area": (ZERO, None),
            },
        )
        d["total"] += valor
        if valor >= d["area"][0]:
            d["area"] = (valor, funcao)
    top = sorted(por_destino.items(), key=lambda kv: kv[1]["total"], reverse=True)[:limite]
    for chave, d in top:
        if d["total"] <= 0:
            continue
        pai = f"area:{d['area'][1]}"
        pai = pai if pai in g.nos else hub
        no_id = f"municipio:{chave}" if d["municipio"] else f"local:{chave}"
        g.no(
            no_id,
            tipo="municipio",
            rotulo=d["rotulo"],
            detalhe="destino da emenda",
            valor=d["total"],
            nivel=g.nos[pai].nivel + 1,
            grupo="emendas",
            pai=pai,
            chave=chave if d["municipio"] else None,
        )
        g.aresta(pai, no_id, "destino", d["total"])

    # quem recebeu (favorecidos), pendurado na área principal da emenda
    fav_base = [F.politico_id == politico_id] + ([F.ano == ano] if ano else [])
    areas_por_emenda = (
        select(E.codigo, func.max(E.funcao).label("funcao")).group_by(E.codigo).subquery()
    )
    linhas = (
        await session.execute(
            select(
                F.favorecido_documento,
                func.max(F.favorecido_nome),
                func.max(F.favorecido_tipo),
                areas_por_emenda.c.funcao,
                func.sum(F.valor),
            )
            .outerjoin(areas_por_emenda, areas_por_emenda.c.codigo == F.emenda_codigo)
            .where(*fav_base)
            .group_by(F.favorecido_documento, areas_por_emenda.c.funcao)
        )
    ).all()
    por_fav: dict[str, dict] = {}
    for doc, nome, tipo, funcao, valor in linhas:
        d = por_fav.setdefault(
            f"{doc}|{nome}",
            {"doc": doc, "nome": nome, "tipo": tipo, "total": ZERO, "area": (ZERO, None)},
        )
        d["total"] += valor
        if valor >= d["area"][0]:
            d["area"] = (valor, funcao)
    top_fav = sorted(por_fav.values(), key=lambda d: d["total"], reverse=True)[:limite]
    expandiveis: list[tuple[str, str]] = []
    for d in top_fav:
        pai = f"area:{d['area'][1]}"
        pai = pai if pai in g.nos else hub
        no_id, chave = _doc_id(d["doc"], d["nome"])
        g.no(
            no_id,
            tipo="favorecido",
            rotulo=_nome(d["nome"]),
            detalhe="recebeu recursos da emenda" + (f" · {d['tipo']}" if d["tipo"] else ""),
            valor=d["total"],
            nivel=g.nos[pai].nivel + 1,
            grupo="emendas",
            pai=pai,
            chave=chave,
        )
        g.aresta(pai, no_id, "recebimento", d["total"])
        if chave:
            expandiveis.append((no_id, chave))
    return expandiveis


# --------------------------------------------------------------------------- empresa/entidade


@router.get(
    "/documento/{documento}",
    response_model=Grafo,
    summary="Rede de uma empresa ou entidade (CNPJ): quem pagou e quem mandou emendas",
)
async def grafo_documento(
    documento: str,
    session: Session,
    ano: int | None = Query(None, ge=2000, le=2100),
    limite: int = Query(12, ge=3, le=30),
) -> Grafo:
    doc = digits(documento)
    if len(doc) != 14:
        raise HTTPException(status_code=400, detail="informe um CNPJ (14 dígitos)")
    centro = f"doc:{doc}"
    g = _Grafo(centro)

    d_base = [D.fornecedor_documento == doc] + ([D.ano == ano] if ano else [])
    f_base = [F.favorecido_documento == doc] + ([F.ano == ano] if ano else [])
    nome = (
        await session.scalar(select(func.max(D.fornecedor_nome)).where(*d_base))
        or await session.scalar(select(func.max(F.favorecido_nome)).where(*f_base))
        or await session.scalar(
            select(func.max(K.fornecedor_nome)).where(K.fornecedor_documento == doc)
        )
        or await session.scalar(select(func.max(C.proponente_nome)).where(C.proponente_cnpj == doc))
    )
    if nome is None:
        raise HTTPException(status_code=404, detail="documento sem despesas, emendas nem obras")
    g.no(centro, tipo="fornecedor", rotulo=_nome(nome), detalhe=_fmt_cnpj(doc), nivel=0,
         grupo="centro", chave=doc)  # fmt: skip

    # cota parlamentar: quem pagou e por quê
    total, qtd = (
        await session.execute(
            select(func.coalesce(func.sum(D.valor_liquido), 0), func.count()).where(*d_base)
        )
    ).one()
    if qtd:
        hub = g.no(
            "hub:gastos",
            tipo="hub",
            rotulo="Recebeu da cota parlamentar",
            detalhe=f"{qtd} notas fiscais",
            valor=total,
            nivel=1,
            grupo="gastos",
            pai=centro,
        )
        g.aresta(centro, hub, "hub", total)
        for categoria, valor in (
            await session.execute(
                select(D.categoria, func.sum(D.valor_liquido).label("t"))
                .where(*d_base)
                .group_by(D.categoria)
                .order_by(desc("t"))
                .limit(3)
            )
        ).all():
            no = g.no(f"categoria:{categoria}", tipo="categoria", rotulo=_titulo(categoria),
                      valor=valor, nivel=2, grupo="gastos", pai=hub)  # fmt: skip
            g.aresta(hub, no, "gasto", valor)
        pagantes = (
            await session.execute(
                select(D.politico_id, func.sum(D.valor_liquido).label("t"))
                .where(*d_base, D.politico_id.is_not(None))
                .group_by(D.politico_id)
                .order_by(desc("t"))
                .limit(limite)
            )
        ).all()
        for pid, valor in pagantes:
            no = g.no(f"politico:{pid}", tipo="politico", rotulo=f"#{pid}", nivel=2,
                      grupo="gastos", pai=hub, chave=str(pid), valor=valor)  # fmt: skip
            g.aresta(hub, no, "pagamento", valor)

    total, qtd = (
        await session.execute(
            select(func.coalesce(func.sum(F.valor), 0), func.count()).where(*f_base)
        )
    ).one()
    if qtd:
        hub = g.no(
            "hub:emendas",
            tipo="hub",
            rotulo="Recebeu emendas",
            detalhe=f"{qtd} pagamentos",
            valor=total,
            nivel=1,
            grupo="emendas",
            pai=centro,
        )
        g.aresta(centro, hub, "hub", total)
        await _autores(session, g, hub, f_base, F, limite)

    anos = [C.ano == ano] if ano else []
    contratada = C.numero.in_(select(K.convenio_numero).where(K.fornecedor_documento == doc))
    await _obras(session, g, centro, [contratada, *anos], "Contratada em obras", limite,
                 autores=True, empreiteiras=False)  # fmt: skip
    await _obras(session, g, centro, [C.proponente_cnpj == doc, *anos], "Convênios que executa",
                 limite, hub_id="hub:convenios", autores=True)  # fmt: skip

    await _partidos_dos_politicos(session, g)
    await _rotular_politicos(session, g)
    return g.build()


def _fmt_cnpj(doc: str) -> str:
    return f"CNPJ {doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"


async def _autores(session: Session, g: _Grafo, hub: str, where: list, model, limite: int):
    """Autores de emendas (político ligado ou autor coletivo: bancada, comissão, relator)."""
    valor_col = model.valor if model is F else (model.valor_pago + model.valor_rp_pago)
    linhas = (
        await session.execute(
            select(
                model.politico_id,
                func.max(model.autor_nome),
                func.sum(valor_col).label("t"),
            )
            .where(*where)
            .group_by(model.politico_id, model.autor_nome_normalizado)
            .order_by(desc("t"))
            .limit(limite)
        )
    ).all()
    for pid, autor, valor in linhas:
        if valor is None or valor <= 0:
            continue
        if pid:
            no = g.no(f"politico:{pid}", tipo="politico", rotulo=autor, nivel=2,
                      grupo="emendas", pai=hub, chave=str(pid), valor=valor)  # fmt: skip
        else:
            no = g.no(f"autor:{autor}", tipo="autor", rotulo=_nome(autor),
                      detalhe="autor coletivo", nivel=2, grupo="emendas", pai=hub,
                      valor=valor)  # fmt: skip
        g.aresta(hub, no, "emenda", valor)


async def _partidos_dos_politicos(session: Session, g: _Grafo) -> None:
    """Pendura cada político (não central) no partido atual: mostra concentração partidária."""
    ids = {
        int(n.chave)
        for n in g.nos.values()
        if n.tipo == "politico" and n.chave and n.id != g.centro
    }
    infos = await _politicos(session, ids)
    for pid, info in infos.items():
        sigla = info.get("partido")
        if not sigla:
            continue
        origem = g.nos[f"politico:{pid}"]
        no = g.no(f"partido:{sigla}", tipo="partido", rotulo=sigla, nivel=origem.nivel + 1,
                  grupo="carreira", pai=origem.id, chave=sigla)  # fmt: skip
        g.aresta(origem.id, no, "filiacao")


# --------------------------------------------------------------------------- município


@router.get(
    "/municipio/{codigo_ibge}",
    response_model=Grafo,
    summary="Rede de um município: quem mandou emendas, para quais áreas",
)
async def grafo_municipio(
    codigo_ibge: int,
    session: Session,
    ano: int | None = Query(None, ge=2000, le=2100),
    limite: int = Query(15, ge=3, le=30),
) -> Grafo:
    base = [E.municipio_codigo_ibge == codigo_ibge] + ([E.ano == ano] if ano else [])
    ente = await session.get(Ente, codigo_ibge)
    nome = (
        ente.nome if ente else await session.scalar(select(func.max(E.municipio_nome)).where(*base))
    )
    if nome is None:
        raise HTTPException(status_code=404, detail="município sem emendas")
    centro = f"municipio:{codigo_ibge}"
    g = _Grafo(centro)
    qtd, pago = (
        await session.execute(select(func.count(), func.coalesce(func.sum(PAGO), 0)).where(*base))
    ).one()
    g.no(centro, tipo="municipio", rotulo=_nome(nome) + (f" - {ente.uf}" if ente else ""),
         detalhe=f"{qtd} emendas", valor=pago, nivel=0, grupo="centro",
         chave=str(codigo_ibge))  # fmt: skip

    hub = g.no("hub:autores", tipo="hub", rotulo="Quem enviou emendas", valor=pago, nivel=1,
               grupo="emendas", pai=centro)  # fmt: skip
    g.aresta(centro, hub, "hub", pago)
    await _autores(session, g, hub, base, E, limite)

    hub_areas = g.no("hub:areas", tipo="hub", rotulo="Para quê", nivel=1, grupo="gastos",
                     pai=centro)  # fmt: skip
    g.aresta(centro, hub_areas, "hub")
    for funcao, valor, q in (
        await session.execute(
            select(E.funcao, func.sum(PAGO).label("t"), func.count())
            .where(*base)
            .group_by(E.funcao)
            .order_by(desc("t"))
            .limit(6)
        )
    ).all():
        no = g.no(f"area:{funcao}", tipo="area", rotulo=_titulo(funcao) if funcao else "Sem área",
                  detalhe=f"{q} emendas", valor=valor, nivel=2, grupo="gastos",
                  pai=hub_areas)  # fmt: skip
        g.aresta(hub_areas, no, "emenda", valor)

    obras = [C.municipio_codigo_ibge == codigo_ibge] + ([C.ano == ano] if ano else [])
    await _obras(session, g, centro, obras, "Obras no município", limite)

    await _partidos_dos_politicos(session, g)
    await _rotular_politicos(session, g)
    return g.build()


# --------------------------------------------------------------------------- obras


def _rotulo_obra(c: Convenio) -> str:
    texto = (c.obra_nome or c.objeto or f"Convênio {c.numero}").strip()
    texto = _titulo(texto)
    return texto if len(texto) <= 70 else texto[:67].rstrip() + "..."


def _detalhe_obra(c: Convenio) -> str:
    local = " - ".join(
        x for x in (_nome(c.municipio_nome) if c.municipio_nome else None, c.uf) if x
    )
    pct = f"{c.percentual_execucao:.0f}% executado" if c.percentual_execucao is not None else None
    return " · ".join(p for p in (local, c.situacao, pct) if p) or f"Convênio {c.numero}"


def _no_obra(g: _Grafo, c: Convenio, pai: str, grupo: str = "obras") -> str:
    return g.no(
        f"obra:{c.numero}",
        tipo="obra",
        rotulo=_rotulo_obra(c),
        detalhe=_detalhe_obra(c),
        valor=c.valor_global,
        nivel=g.nos[pai].nivel + 1,
        grupo=grupo,
        pai=pai,
        chave=str(c.numero),
    )


def _brl(valor: Decimal) -> str:
    return f"R$ {valor:,.0f}".replace(",", ".")


async def _obras(
    session: Session,
    g: _Grafo,
    pai: str,
    where: list,
    rotulo: str,
    limite: int,
    *,
    hub_id: str = "hub:obras",
    autores: bool = False,
    empreiteiras: bool = True,
) -> list[tuple[str, str]]:
    """Hub com as maiores obras (convênios) que casam com `where` e, de cada uma, a principal
    empreiteira contratada e/ou os autores das emendas. Devolve as empreiteiras novas no grafo
    (nó, CNPJ), para buscar outros políticos ligados a elas."""
    qtd, total, desembolsado = (
        await session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(C.valor_global), 0),
                func.coalesce(func.sum(C.valor_desembolsado), 0),
            ).where(*where)
        )
    ).one()
    if not qtd:
        return []
    hub = g.no(
        hub_id,
        tipo="hub",
        rotulo=rotulo,
        detalhe=f"{qtd} convênios · liberado {_brl(desembolsado)}",
        valor=total,
        nivel=g.nos[pai].nivel + 1,
        grupo="obras",
        pai=pai,
    )
    g.aresta(pai, hub, "hub", total)
    obras = list(
        await session.scalars(select(C).where(*where).order_by(C.valor_global.desc()).limit(limite))
    )
    for c in obras:
        no = _no_obra(g, c, hub)
        g.aresta(hub, no, "obra", c.valor_global)
        municipio = f"municipio:{c.municipio_codigo_ibge}"
        if c.municipio_codigo_ibge and municipio in g.nos and municipio != pai:
            g.aresta(no, municipio, "local")

    numeros = [c.numero for c in obras]
    saida: list[tuple[str, str]] = []
    if empreiteiras and numeros:
        principais = (
            await session.execute(
                select(K.convenio_numero, K.fornecedor_documento, K.fornecedor_nome, K.valor)
                .ext(distinct_on(K.convenio_numero))
                .where(K.convenio_numero.in_(numeros), func.length(K.fornecedor_documento) == 14)
                .order_by(K.convenio_numero, K.valor.desc())
            )
        ).all()
        for numero, doc, nome, valor in principais:
            origem = f"obra:{numero}"
            no_id = f"doc:{doc}"
            novo = no_id not in g.nos
            g.no(no_id, tipo="fornecedor", rotulo=_nome(nome), detalhe="empreiteira contratada",
                 valor=valor, nivel=g.nos[origem].nivel + 1, grupo="obras", pai=origem,
                 chave=doc)  # fmt: skip
            g.aresta(origem, no_id, "contrato", valor)
            if novo:
                saida.append((no_id, doc))
    if autores and numeros:
        linhas = (
            await session.execute(
                select(
                    CE.convenio_numero,
                    CE.politico_id,
                    func.max(CE.parlamentar_nome),
                    func.sum(CE.valor_repasse),
                )
                .where(CE.convenio_numero.in_(numeros))
                .group_by(CE.convenio_numero, CE.politico_id, CE.parlamentar_nome_normalizado)
            )
        ).all()
        for numero, pid, autor, valor in linhas:
            origem = f"obra:{numero}"
            nivel = g.nos[origem].nivel + 1
            if pid:
                no = g.no(f"politico:{pid}", tipo="politico", rotulo=autor, nivel=nivel,
                          grupo="obras", pai=origem, chave=str(pid))  # fmt: skip
            else:
                no = g.no(f"autor:{autor}", tipo="autor", rotulo=_nome(autor),
                          detalhe="autor coletivo", nivel=nivel, grupo="obras",
                          pai=origem)  # fmt: skip
            g.aresta(origem, no, "emenda", valor)
    return saida


async def _conexoes_obra(
    session: Session, g: _Grafo, docs: list[tuple[str, str]], excluir: int | None
) -> set[int]:
    """Outros políticos cujas emendas pagaram obras da mesma empreiteira (até 3 por empresa)."""
    pares: list[tuple[str, int, Decimal]] = []
    ligados: set[int] = set()
    for no_id, documento in docs:
        stmt = (
            select(CE.politico_id, func.sum(CE.valor_repasse).label("t"))
            .where(
                CE.politico_id.is_not(None),
                CE.convenio_numero.in_(
                    select(K.convenio_numero).where(K.fornecedor_documento == documento)
                ),
            )
            .group_by(CE.politico_id)
            .order_by(desc("t"))
            .limit(4)
        )
        if excluir is not None:
            stmt = stmt.where(CE.politico_id != excluir)
        for pid, total in (await session.execute(stmt)).all()[:3]:
            pares.append((no_id, pid, total))
            ligados.add(pid)
    return _ligar_politicos(g, pares, ligados, "conexao")


@router.get(
    "/obra/{numero}",
    response_model=Grafo,
    summary="Rede de uma obra/convênio: quem mandou o dinheiro, onde e quem executou",
)
async def grafo_obra(numero: int, session: Session, limite: int = Query(10, ge=3, le=30)) -> Grafo:
    c = await session.get(Convenio, numero)
    if c is None:
        raise HTTPException(status_code=404, detail="convênio não encontrado")
    centro = f"obra:{numero}"
    g = _Grafo(centro)
    g.no(centro, tipo="obra", rotulo=_rotulo_obra(c), detalhe=_detalhe_obra(c),
         valor=c.valor_global, nivel=0, grupo="centro", chave=str(numero))  # fmt: skip

    # de onde veio o dinheiro
    autores = (
        await session.execute(
            select(
                CE.politico_id,
                func.max(CE.parlamentar_nome),
                func.max(CE.tipo),
                func.sum(CE.valor_repasse).label("t"),
            )
            .where(CE.convenio_numero == numero)
            .group_by(CE.politico_id, CE.parlamentar_nome_normalizado)
            .order_by(desc("t"))
        )
    ).all()
    if autores:
        total = sum((v or ZERO for *_, v in autores), ZERO)
        hub = g.no("hub:emendas", tipo="hub", rotulo="Emendas que pagam a obra",
                   detalhe=f"{len(autores)} autores", valor=total, nivel=1, grupo="emendas",
                   pai=centro)  # fmt: skip
        g.aresta(centro, hub, "hub", total)
        for pid, nome, tipo, valor in autores:
            if pid:
                no = g.no(f"politico:{pid}", tipo="politico", rotulo=nome, nivel=2,
                          grupo="emendas", pai=hub, chave=str(pid), valor=valor)  # fmt: skip
            else:
                no = g.no(f"autor:{nome}", tipo="autor", rotulo=_nome(nome),
                          detalhe=f"emenda de {(tipo or 'autor coletivo').lower()}", nivel=2,
                          grupo="emendas", pai=hub, valor=valor)  # fmt: skip
            g.aresta(hub, no, "emenda", valor)
    else:
        hub = g.no("hub:emendas", tipo="hub", rotulo="Repasse do ministério",
                   detalhe=_nome(c.orgao_superior) if c.orgao_superior else None,
                   valor=c.valor_repasse, nivel=1, grupo="emendas", pai=centro)  # fmt: skip
        g.aresta(centro, hub, "hub", c.valor_repasse)

    # onde e quem executa o convênio
    hub_local = g.no("hub:local", tipo="hub", rotulo="Onde e quem executa",
                     detalhe=c.endereco, nivel=1, grupo="gastos", pai=centro)  # fmt: skip
    g.aresta(centro, hub_local, "hub")
    if c.municipio_codigo_ibge:
        rotulo = " - ".join(x for x in (_nome(c.municipio_nome), c.uf) if x)
        no = g.no(f"municipio:{c.municipio_codigo_ibge}", tipo="municipio", rotulo=rotulo,
                  detalhe="local da obra", nivel=2, grupo="gastos", pai=hub_local,
                  chave=str(c.municipio_codigo_ibge))  # fmt: skip
        g.aresta(hub_local, no, "local")
    if c.proponente_cnpj:
        no = g.no(f"doc:{c.proponente_cnpj}", tipo="favorecido", rotulo=_nome(c.proponente_nome),
                  detalhe="convenente (executa o convênio)", valor=c.valor_desembolsado,
                  nivel=2, grupo="gastos", pai=hub_local, chave=c.proponente_cnpj)  # fmt: skip
        g.aresta(hub_local, no, "recebimento", c.valor_desembolsado)

    # quem executou: contratado (licitação) e pago (conta do convênio), por CNPJ
    F2 = ConvenioFornecedor
    empresas: dict[str, dict] = {}
    for doc, nome, valor in (
        await session.execute(
            select(K.fornecedor_documento, func.max(K.fornecedor_nome), func.sum(K.valor))
            .where(K.convenio_numero == numero, func.length(K.fornecedor_documento) == 14)
            .group_by(K.fornecedor_documento)
        )
    ).all():
        empresas[doc] = {"nome": nome, "contratado": valor, "pago": ZERO}
    for doc, nome, valor in (
        await session.execute(
            select(F2.documento, F2.nome, F2.valor).where(
                F2.convenio_numero == numero, F2.documento.is_not(None)
            )
        )
    ).all():
        e = empresas.setdefault(doc, {"nome": nome, "contratado": ZERO, "pago": ZERO})
        e["pago"] += valor
    expandiveis: list[tuple[str, str]] = []
    if empresas:
        pago_total = sum((e["pago"] for e in empresas.values()), ZERO)
        hub_exec = g.no("hub:execucao", tipo="hub", rotulo="Quem executou",
                        detalhe="empresas contratadas e pagas", valor=pago_total or None,
                        nivel=1, grupo="obras", pai=centro)  # fmt: skip
        g.aresta(centro, hub_exec, "hub", pago_total or None)
        top = sorted(
            empresas.items(), key=lambda kv: max(kv[1]["contratado"], kv[1]["pago"]), reverse=True
        )[:limite]
        for doc, e in top:
            partes = [
                f"contratado {_brl(e['contratado'])}" if e["contratado"] else None,
                f"pago {_brl(e['pago'])}" if e["pago"] else None,
            ]
            valor = e["pago"] or e["contratado"]
            no = g.no(f"doc:{doc}", tipo="fornecedor", rotulo=_nome(e["nome"]),
                      detalhe=" · ".join(x for x in partes if x) or None, valor=valor,
                      nivel=2, grupo="obras", pai=hub_exec, chave=doc)  # fmt: skip
            g.aresta(hub_exec, no, "contrato", valor)
            expandiveis.append((no, doc))

    # outras obras das mesmas empreiteiras
    for no_id, doc in expandiveis[:3]:
        for outra in await session.scalars(
            select(C)
            .where(
                C.numero != numero,
                C.numero.in_(select(K.convenio_numero).where(K.fornecedor_documento == doc)),
            )
            .order_by(C.valor_global.desc())
            .limit(3)
        ):
            if f"obra:{outra.numero}" not in g.nos:
                g.aresta(no_id, _no_obra(g, outra, no_id, "conexoes"), "contrato")

    await _partidos_dos_politicos(session, g)
    await _rotular_politicos(session, g)
    return g.build()
