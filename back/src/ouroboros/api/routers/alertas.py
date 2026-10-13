"""Alertas de indícios de fraude/desvio (gerados pelo job `analises`) e ranking de risco."""

from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.dialects.postgresql import distinct_on

from ouroboros.analises.detectores import CATALOGO
from ouroboros.analises.estatistica import risco, score_detector
from ouroboros.api.deps import Paging, Session
from ouroboros.api.export import page_or_csv
from ouroboros.api.pagination import Page, encode_cursor
from ouroboros.api.schemas import (
    AlertaOut,
    Detectores,
    DetectorOut,
    DetectorRisco,
    Ranking,
    RiscoPolitico,
)
from ouroboros.core.privacy import digits
from ouroboros.models import Alerta, Mandato, Politico

router = APIRouter(prefix="/alertas", tags=["alertas"])

A = Alerta
SEVERIDADES = {"alta", "media", "baixa"}


def _filtrar(
    stmt: Select,
    detector: list[str] | None,
    severidade: list[str] | None,
    politico: int | None,
    entidade: str | None,
    ano: int | None,
    score_min: float | None,
) -> Select:
    if detector:
        desconhecidos = set(detector) - set(CATALOGO)
        if desconhecidos:
            raise HTTPException(400, f"detector desconhecido: {', '.join(sorted(desconhecidos))}")
        stmt = stmt.where(A.detector.in_(detector))
    if severidade:
        if set(severidade) - SEVERIDADES:
            raise HTTPException(400, "severidade: alta, media ou baixa")
        stmt = stmt.where(A.severidade.in_(severidade))
    if politico is not None:
        stmt = stmt.where(A.politico_id == politico)
    if entidade:
        d = digits(entidade)
        if len(d) == 14:
            stmt = stmt.where(A.entidade_documento == d)
        else:
            stmt = stmt.where(A.entidade_nome.icontains(entidade.strip(), autoescape=True))
    if ano:
        stmt = stmt.where(
            func.coalesce(A.ano_inicio, ano) <= ano, func.coalesce(A.ano_fim, ano) >= ano
        )
    if score_min is not None:
        stmt = stmt.where(A.score >= score_min)
    return stmt


@router.get(
    "",
    response_model=Page[AlertaOut],
    summary="Alertas, do mais forte ao mais fraco",
    description="Indícios, não acusação: cada alerta traz métricas e documentos oficiais.",
)
async def listar_alertas(
    request: Request,
    session: Session,
    paging: Paging,
    detector: list[str] | None = Query(None, description="Código do detector; repetível"),
    severidade: list[str] | None = Query(None, description="alta, media, baixa; repetível"),
    politico: int | None = Query(None, description="ID do político"),
    entidade: str | None = Query(None, description="CNPJ (só dígitos) ou trecho do nome"),
    ano: int | None = Query(None, ge=2000, le=2100, description="Achados que cobrem o ano"),
    score_min: float | None = Query(None, ge=0, le=100),
):
    stmt = _filtrar(
        select(A, Politico.nome).outerjoin(Politico, Politico.id == A.politico_id),
        detector,
        severidade,
        politico,
        entidade,
        ano,
        score_min,
    )
    if paging.after is not None:
        try:
            score_c, id_c = float(paging.after[0]), int(paging.after[1])
        except (TypeError, ValueError, IndexError) as exc:
            raise HTTPException(400, "cursor inválido") from exc
        stmt = stmt.where(or_(A.score < score_c, and_(A.score == score_c, A.id > id_c)))
    stmt = stmt.order_by(A.score.desc(), A.id).limit(paging.limit + 1)
    rows = (await session.execute(stmt)).all()
    has_more = len(rows) > paging.limit
    rows = rows[: paging.limit]
    items = []
    for alerta, nome in rows:
        item = AlertaOut.model_validate(alerta)
        item.politico_nome = nome
        items.append(item)
    page = Page(
        items=items,
        next_cursor=encode_cursor([rows[-1][0].score, rows[-1][0].id]) if has_more else None,
    )
    return page_or_csv(request, page, "alertas")


@router.get(
    "/detectores",
    response_model=Detectores,
    summary="Detectores: o que cada um mede, como, e quantos alertas gerou",
)
async def detectores(session: Session) -> Detectores:
    contagem: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for det, sev, n in await session.execute(
        select(A.detector, A.severidade, func.count()).group_by(A.detector, A.severidade)
    ):
        contagem[det][sev] = n
    return Detectores(
        gerado_em=await session.scalar(select(func.max(A.gerado_em))),
        detectores=[
            DetectorOut(
                codigo=d.codigo,
                titulo=d.titulo,
                area=d.area,
                peso=d.peso,
                metodologia=d.metodologia,
                alertas=sum(contagem[d.codigo].values()),
                alta=contagem[d.codigo]["alta"],
                media=contagem[d.codigo]["media"],
                baixa=contagem[d.codigo]["baixa"],
            )
            for d in CATALOGO.values()
        ],
    )


@router.get(
    "/ranking",
    response_model=Ranking,
    summary="Políticos por risco (combinação dos detectores)",
    description=(
        "Risco = OU probabilístico dos detectores: cada detector contribui com peso × força "
        "do seu achado mais forte (+ bônus pequeno por repetição). Indícios de detectores "
        "diferentes se reforçam."
    ),
)
async def ranking(
    session: Session,
    limit: int = Query(50, ge=1, le=500),
    detector: list[str] | None = Query(None, description="Só estes detectores entram na conta"),
    politico: int | None = Query(None, description="Risco de um político só"),
    uf: str | None = Query(None, min_length=2, max_length=2, description="UF do último mandato"),
    partido: str | None = Query(None, description="Partido do último mandato"),
) -> Ranking:
    stmt = _filtrar(
        select(A.politico_id, A.detector, A.score, A.peso, A.severidade, A.valor).where(
            A.politico_id.is_not(None)
        ),
        detector,
        None,
        politico,
        None,
        None,
        None,
    )
    por_politico: dict[int, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for pid, det, s, peso, sev, valor in await session.execute(stmt):
        por_politico[pid][det].append((s, peso, sev, valor or Decimal(0)))

    itens: list[RiscoPolitico] = []
    for pid, dets in por_politico.items():
        resumo = [
            DetectorRisco(
                detector=det, score=score_detector(x[0] for x in achados), alertas=len(achados)
            )
            for det, achados in dets.items()
        ]
        resumo.sort(key=lambda d: -d.score * CATALOGO[d.detector].peso)
        todos = [x for achados in dets.values() for x in achados]
        itens.append(
            RiscoPolitico(
                politico_id=pid,
                nome="",
                risco=risco((CATALOGO[d.detector].peso, d.score) for d in resumo),
                alertas=len(todos),
                alertas_alta=sum(1 for x in todos if x[2] == "alta"),
                valor=sum((x[3] for x in todos), Decimal(0)),
                detectores=resumo,
            )
        )

    info = await _info_politicos(session, [i.politico_id for i in itens])
    if uf or partido:
        itens = [
            i
            for i in itens
            if (not uf or info.get(i.politico_id, {}).get("uf") == uf.upper())
            and (not partido or info.get(i.politico_id, {}).get("partido") == partido.upper())
        ]
    itens.sort(key=lambda i: (-i.risco, -i.valor))
    itens = itens[:limit]
    for i in itens:
        dados = info.get(i.politico_id, {})
        i.nome = dados.get("nome", "")
        i.foto_id = dados.get("foto_id")
        i.partido = dados.get("partido")
        i.uf = dados.get("uf")
    return Ranking(items=itens)


async def _info_politicos(session: Session, ids: list[int]) -> dict[int, dict]:
    if not ids:
        return {}
    out: dict[int, dict] = {
        pid: {"nome": nome, "foto_id": foto}
        for pid, nome, foto in await session.execute(
            select(Politico.id, Politico.nome, Politico.foto_id).where(Politico.id.in_(ids))
        )
    }
    ultimos = await session.execute(
        select(Mandato.politico_id, Mandato.partido_sigla, Mandato.partidos, Mandato.uf)
        .ext(distinct_on(Mandato.politico_id))
        .where(Mandato.politico_id.in_(ids))
        .order_by(Mandato.politico_id, Mandato.inicio.desc().nulls_last())
    )
    for pid, sigla, partidos, uf in ultimos:
        if pid in out:
            out[pid]["partido"] = sigla or (partidos[-1] if partidos else None)
            out[pid]["uf"] = uf
    return out


@router.get("/{alerta_id}", response_model=AlertaOut, summary="Um alerta, com evidências")
async def obter_alerta(session: Session, alerta_id: int) -> AlertaOut:
    row = (
        await session.execute(
            select(A, Politico.nome)
            .outerjoin(Politico, Politico.id == A.politico_id)
            .where(A.id == alerta_id)
        )
    ).first()
    if row is None:
        raise HTTPException(404, "alerta não encontrado")
    item = AlertaOut.model_validate(row[0])
    item.politico_nome = row[1]
    return item
