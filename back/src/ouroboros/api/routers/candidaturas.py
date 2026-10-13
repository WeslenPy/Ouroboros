from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import Select, desc, func, select

from ouroboros.api.deps import Paging, Session
from ouroboros.api.export import page_or_csv
from ouroboros.api.pagination import Page, encode_cursor
from ouroboros.api.schemas import CandidaturaOut, Contagem, ContagemEleitos, ResumoCandidaturas
from ouroboros.models.mandato import Candidatura

router = APIRouter(prefix="/candidaturas", tags=["candidaturas"])


@dataclass
class FiltroCandidatura:
    ano: int | None = Query(None, ge=1990, le=2100)
    cargo: str | None = Query(None, description="Trecho do cargo no TSE (ex.: deputado federal)")
    uf: str | None = Query(None, min_length=2, max_length=2)
    partido: str | None = Query(None, description="Sigla do partido")
    eleito: bool | None = None
    turno: int | None = Query(None, ge=1, le=2)

    def aplicar(self, stmt: Select) -> Select:
        c = Candidatura
        if self.ano:
            stmt = stmt.where(c.ano == self.ano)
        if self.cargo:
            stmt = stmt.where(c.cargo.icontains(self.cargo, autoescape=True))
        if self.uf:
            stmt = stmt.where(c.uf == self.uf.upper())
        if self.partido:
            stmt = stmt.where(c.partido_sigla == self.partido.upper())
        if self.eleito is not None:
            stmt = stmt.where(c.eleito.is_(self.eleito))
        if self.turno:
            stmt = stmt.where(c.turno == self.turno)
        return stmt


Filtro = Annotated[FiltroCandidatura, Depends()]


@router.get("", response_model=Page[CandidaturaOut], summary="Candidaturas registradas no TSE")
async def listar_candidaturas(request: Request, session: Session, paging: Paging, filtro: Filtro):
    stmt = filtro.aplicar(select(Candidatura))
    stmt = stmt.order_by(Candidatura.sq_candidato).limit(paging.limit + 1)
    if paging.after is not None:
        stmt = stmt.where(Candidatura.sq_candidato > int(paging.after))
    rows = list((await session.scalars(stmt)).all())
    has_more = len(rows) > paging.limit
    rows = rows[: paging.limit]
    page = Page(
        items=[CandidaturaOut.model_validate(r) for r in rows],
        next_cursor=encode_cursor(rows[-1].sq_candidato) if has_more else None,
    )
    return page_or_csv(request, page, "candidaturas")


@router.get(
    "/resumo",
    response_model=ResumoCandidaturas,
    summary="Totais de candidaturas por ano, cargo, situação e partido",
)
async def resumo_candidaturas(session: Session, filtro: Filtro) -> ResumoCandidaturas:
    c = Candidatura
    qtd = func.count().label("quantidade")
    eleitos = func.count().filter(c.eleito.is_(True)).label("eleitos")

    async def por(coluna, *, ordem=None, limite: int | None = None) -> list[ContagemEleitos]:
        stmt = filtro.aplicar(select(coluna, qtd, eleitos)).group_by(coluna)
        stmt = stmt.order_by(ordem if ordem is not None else desc("quantidade")).limit(limite)
        return [
            ContagemEleitos(chave=None if k is None else str(k), quantidade=q, eleitos=e)
            for k, q, e in await session.execute(stmt)
        ]

    total, total_eleitos = (
        await session.execute(filtro.aplicar(select(qtd, eleitos).select_from(c)))
    ).one()
    situacao = await session.execute(
        filtro.aplicar(select(c.situacao_turno, qtd))
        .group_by(c.situacao_turno)
        .order_by(desc("quantidade"))
    )
    return ResumoCandidaturas(
        total=total,
        eleitos=total_eleitos,
        por_ano=await por(c.ano, ordem=c.ano),
        por_cargo=await por(c.cargo),
        por_situacao=[Contagem(chave=s, quantidade=q) for s, q in situacao],
        por_partido=await por(c.partido_sigla, limite=40),
    )
