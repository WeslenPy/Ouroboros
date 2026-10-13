"""Gastos da Presidência da República (cartão de pagamento) por presidente em exercício.

O presidente de cada lançamento é quem exercia o cargo na data (ou no meio do mês do extrato,
quando a data é sigilosa): junção com `mandato` de presidente na consulta, então carregar os
presidentes depois dos gastos não muda o resultado.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import Select, and_, desc, func, select

from ouroboros.api.deps import Paging, Session
from ouroboros.api.export import page_or_csv
from ouroboros.api.pagination import Page, encode_cursor
from ouroboros.api.schemas import (
    GastoPresidenciaOut,
    MandatoPresidente,
    Origem,
    PresidenteGastos,
    ResumoPresidencia,
    TotalRotulo,
)
from ouroboros.models import GastoPresidencia, Mandato, Politico
from ouroboros.models.mandato import Cargo

router = APIRouter(prefix="/presidencia", tags=["presidência"])

G = GastoPresidencia
REFERENCIA = func.coalesce(G.data, func.make_date(G.ano, G.mes, 15))
NO_MANDATO = and_(
    Mandato.cargo == Cargo.PRESIDENTE,
    REFERENCIA >= Mandato.inicio,
    REFERENCIA <= Mandato.fim,
)
ZERO = Decimal("0")


@dataclass
class FiltroGasto:
    politico: int | None = Query(None, description="ID do político (presidente em exercício)")
    mandato: str | None = Query(None, description="ID do mandato: lula-2003, bolsonaro-2019...")
    ano: int | None = Query(None, ge=2003, le=2100)
    categoria: str | None = Query(None, description="Trecho do subelemento de despesa")
    favorecido: str | None = Query(None, description="Trecho do nome ou documento")
    tipo: str | None = Query(None, description="credito ou saque")
    sigiloso: bool | None = Query(None)

    def aplicar(self, stmt: Select) -> Select:
        if self.politico is not None or self.mandato:
            stmt = stmt.join(Mandato, NO_MANDATO)
            if self.politico is not None:
                stmt = stmt.where(Mandato.politico_id == self.politico)
            if self.mandato:
                stmt = stmt.where(Mandato.id_externo == self.mandato)
        if self.ano:
            stmt = stmt.where(G.ano == self.ano)
        if self.categoria:
            stmt = stmt.where(G.categoria.icontains(self.categoria, autoescape=True))
        if self.favorecido:
            termo = self.favorecido.strip()
            stmt = stmt.where(
                G.favorecido_nome.icontains(termo, autoescape=True)
                | (G.favorecido_documento == "".join(c for c in termo if c.isdigit()))
            )
        if self.tipo:
            stmt = stmt.where(G.tipo == self.tipo)
        if self.sigiloso is not None:
            stmt = stmt.where(G.sigiloso.is_(self.sigiloso))
        return stmt


Filtro = Annotated[FiltroGasto, Depends()]


@router.get(
    "/presidentes",
    response_model=list[PresidenteGastos],
    summary="Gasto do cartão da Presidência por presidente e mandato",
)
async def presidentes(session: Session) -> list[PresidenteGastos]:
    rows = await session.execute(
        select(
            Mandato.politico_id,
            Mandato.id_externo,
            Mandato.inicio,
            Mandato.fim,
            Mandato.condicao,
            Mandato.partidos,
            func.coalesce(func.sum(G.valor), 0),
            func.count(G.id),
            func.coalesce(func.sum(G.valor).filter(G.tipo == "saque"), 0),
            # 2003-2022 já foi revelado; "sigiloso" que conta é o que ainda não tem detalhe
            func.coalesce(func.sum(G.valor).filter(G.sigiloso, G.data.is_(None)), 0),
        )
        .select_from(Mandato)
        .outerjoin(G, NO_MANDATO)
        .where(Mandato.cargo == Cargo.PRESIDENTE)
        .group_by(Mandato.id)
        .order_by(Mandato.inicio)
    )
    hoje = date.today()
    por_politico: dict[int, list[MandatoPresidente]] = {}
    for pid, mid, inicio, fim, condicao, partidos, total, qtd, saques, sigiloso in rows:
        dias = max(1, ((min(fim, hoje) if fim else hoje) - inicio).days + 1)
        por_politico.setdefault(pid, []).append(
            MandatoPresidente(
                id_externo=mid,
                inicio=inicio,
                fim=fim,
                condicao=condicao,
                partidos=partidos,
                dias=dias,
                total=total,
                quantidade=qtd,
                saques=saques,
                sigiloso=sigiloso,
                por_dia=(Decimal(total) / dias).quantize(Decimal("0.01")),
            )
        )
    politicos = {
        p.id: p
        for p in await session.scalars(select(Politico).where(Politico.id.in_(por_politico)))
    }
    out = [
        PresidenteGastos(
            politico_id=pid,
            nome=politicos[pid].nome,
            foto_id=politicos[pid].foto_id,
            total=sum((m.total for m in ms), ZERO),
            quantidade=sum(m.quantidade for m in ms),
            mandatos=ms,
        )
        for pid, ms in por_politico.items()
    ]
    out.sort(key=lambda p: p.mandatos[0].inicio)
    return out


@router.get(
    "/gastos",
    response_model=Page[GastoPresidenciaOut],
    summary="Lançamentos do cartão da Presidência",
)
async def listar_gastos(request: Request, session: Session, paging: Paging, filtro: Filtro):
    stmt = filtro.aplicar(select(G)).order_by(G.id).limit(paging.limit + 1)
    if paging.after is not None:
        stmt = stmt.where(G.id > int(paging.after))
    rows = list((await session.scalars(stmt)).all())
    has_more = len(rows) > paging.limit
    rows = rows[: paging.limit]

    # presidente de cada linha (uma consulta para a página)
    quem: dict[int, tuple[int, str]] = {}
    if rows:
        for gid, pid, nome in await session.execute(
            select(G.id, Politico.id, Politico.nome)
            .join(Mandato, NO_MANDATO)
            .join(Politico, Politico.id == Mandato.politico_id)
            .where(G.id.in_([r.id for r in rows]))
        ):
            quem[gid] = (pid, nome)
    items = []
    for r in rows:
        item = GastoPresidenciaOut.model_validate(
            {**r.__dict__, "origem": Origem.model_validate(r)}
        )
        if r.id in quem:
            item.presidente_id, item.presidente = quem[r.id]
        items.append(item)
    page = Page(items=items, next_cursor=encode_cursor(rows[-1].id) if has_more else None)
    return page_or_csv(request, page, "gastos_presidencia")


async def _por(session: Session, filtro: FiltroGasto, coluna, *, ordem=None, limite=None):
    soma = func.sum(G.valor)
    stmt = (
        filtro.aplicar(select(coluna, soma, func.count()).select_from(G))
        .group_by(coluna)
        .order_by(ordem if ordem is not None else desc(soma))
        .limit(limite)
    )
    return [
        TotalRotulo(chave=None if k is None else str(k), total=t, quantidade=q)
        for k, t, q in await session.execute(stmt)
    ]


@router.get(
    "/resumo",
    response_model=ResumoPresidencia,
    summary="Totais por ano, categoria, unidade e maiores favorecidos",
)
async def resumo(session: Session, filtro: Filtro) -> ResumoPresidencia:
    total, qtd, saques, sigiloso = (
        await session.execute(
            filtro.aplicar(
                select(
                    func.coalesce(func.sum(G.valor), 0),
                    func.count(),
                    func.coalesce(func.sum(G.valor).filter(G.tipo == "saque"), 0),
                    func.coalesce(func.sum(G.valor).filter(G.sigiloso, G.data.is_(None)), 0),
                ).select_from(G)
            )
        )
    ).one()
    # sem CNPJ na fonte, agrupa por nome: grafias diferentes do mesmo fornecedor ficam separadas
    nome = func.upper(func.trim(G.favorecido_nome))
    favorecidos = await _por(session, filtro, nome, limite=20)
    return ResumoPresidencia(
        total=total,
        quantidade=qtd,
        saques=saques,
        sigiloso=sigiloso,
        por_ano=await _por(session, filtro, G.ano, ordem=G.ano),
        por_categoria=await _por(session, filtro, G.categoria, limite=25),
        por_unidade=await _por(session, filtro, G.unidade_gestora),
        maiores_favorecidos=[f for f in favorecidos if f.chave],
    )
