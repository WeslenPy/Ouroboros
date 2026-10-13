from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import Select, String, cast, desc, func, select

from ouroboros.api.deps import Paging, Session
from ouroboros.api.export import page_or_csv
from ouroboros.api.pagination import Page, encode_cursor
from ouroboros.api.schemas import EmendaOut, FavorecidoOut, ResumoEmendas, TotalChave
from ouroboros.core.privacy import digits
from ouroboros.core.text import normalize
from ouroboros.models import Emenda, EmendaFavorecido, Politico

router = APIRouter(prefix="/emendas", tags=["emendas"])

E = Emenda
PAGO = (E.valor_pago + E.valor_rp_pago).label("pago")


@dataclass
class FiltroEmenda:
    ano: int | None = Query(None, ge=2000, le=2100)
    tipo: str | None = Query(None, description="Trecho do tipo: individual, especiais, bancada...")
    uf: str | None = Query(None, min_length=2, max_length=2, description="UF de destino")
    municipio: int | None = Query(None, description="Código IBGE do município de destino")
    funcao: str | None = Query(None, description="Área (função orçamentária): Saúde, Educação...")
    autor: str | None = Query(None, description="Trecho do nome do autor")
    politico: int | None = Query(None, description="ID do político autor")

    def aplicar(self, stmt: Select) -> Select:
        if self.ano:
            stmt = stmt.where(E.ano == self.ano)
        if self.tipo:
            stmt = stmt.where(E.tipo.icontains(self.tipo, autoescape=True))
        if self.uf:
            stmt = stmt.where(E.uf == self.uf.upper())
        if self.municipio:
            stmt = stmt.where(E.municipio_codigo_ibge == self.municipio)
        if self.funcao:
            stmt = stmt.where(E.funcao.icontains(self.funcao, autoescape=True))
        if self.autor:
            stmt = stmt.where(E.autor_nome_normalizado.contains(normalize(self.autor)))
        if self.politico is not None:
            stmt = stmt.where(E.politico_id == self.politico)
        return stmt


Filtro = Annotated[FiltroEmenda, Depends()]


@router.get("", response_model=Page[EmendaOut], summary="Emendas parlamentares (orçamento federal)")
async def listar_emendas(request: Request, session: Session, paging: Paging, filtro: Filtro):
    stmt = filtro.aplicar(select(E)).order_by(E.id).limit(paging.limit + 1)
    if paging.after is not None:
        stmt = stmt.where(E.id > int(paging.after))
    rows = list((await session.scalars(stmt)).all())
    has_more = len(rows) > paging.limit
    rows = rows[: paging.limit]
    page = Page(
        items=[EmendaOut.model_validate(r) for r in rows],
        next_cursor=encode_cursor(rows[-1].id) if has_more else None,
    )
    return page_or_csv(request, page, "emendas")


async def _por(session: Session, filtro: FiltroEmenda, coluna, *, ordem=None, limite=None):
    stmt = filtro.aplicar(
        select(coluna, func.sum(E.valor_empenhado), func.sum(PAGO), func.count())
    ).group_by(coluna)
    stmt = stmt.order_by(ordem if ordem is not None else desc(func.sum(PAGO))).limit(limite)
    return [
        TotalChave(chave=None if k is None else str(k), empenhado=e, pago=p, quantidade=q)
        for k, e, p, q in await session.execute(stmt)
    ]


@router.get(
    "/resumo",
    response_model=ResumoEmendas,
    summary="Totais por ano, tipo, área, UF, autor, destino e favorecido",
)
async def resumo_emendas(session: Session, filtro: Filtro) -> ResumoEmendas:
    quantidade, empenhado, pago = (
        await session.execute(
            filtro.aplicar(
                select(
                    func.count(),
                    func.coalesce(func.sum(E.valor_empenhado), 0),
                    func.coalesce(func.sum(PAGO), 0),
                ).select_from(E)
            )
        )
    ).one()

    autores = await session.execute(
        filtro.aplicar(
            select(
                E.politico_id,
                func.max(E.autor_nome),
                func.sum(E.valor_empenhado),
                func.sum(PAGO),
                func.count(),
            )
        )
        .group_by(E.politico_id, E.autor_nome_normalizado)
        .order_by(desc(func.sum(PAGO)))
        .limit(20)
    )
    autores_out = [
        TotalChave(chave=str(pid) if pid else None, rotulo=nome, empenhado=e, pago=p, quantidade=q)
        for pid, nome, e, p, q in autores
    ]
    # nome do cadastro (ex.: "Jandira Feghali") no lugar do nome da fonte em maiúsculas
    pids = [int(a.chave) for a in autores_out if a.chave]
    if pids:
        cadastro = dict(
            (
                await session.execute(
                    select(Politico.id, Politico.nome).where(Politico.id.in_(pids))
                )
            ).all()
        )
        for a in autores_out:
            if a.chave:
                a.rotulo = cadastro.get(int(a.chave), a.rotulo)

    destino = func.coalesce(cast(E.municipio_codigo_ibge, String), E.localidade)
    destinos = await session.execute(
        filtro.aplicar(
            select(
                destino.label("destino"),
                func.max(func.coalesce(E.municipio_nome + " - " + E.uf, E.localidade)).label(
                    "rotulo"
                ),
                func.sum(E.valor_empenhado),
                func.sum(PAGO),
                func.count(),
            )
        )
        .group_by(destino)
        .order_by(desc(func.sum(PAGO)))
        .limit(20)
    )

    return ResumoEmendas(
        quantidade=quantidade,
        empenhado=empenhado,
        pago=pago,
        por_ano=await _por(session, filtro, E.ano, ordem=E.ano),
        por_tipo=await _por(session, filtro, E.tipo),
        por_funcao=await _por(session, filtro, E.funcao),
        por_uf=await _por(session, filtro, E.uf),
        maiores_autores=autores_out,
        maiores_destinos=[
            TotalChave(chave=d, rotulo=r, empenhado=e, pago=p, quantidade=q)
            for d, r, e, p, q in destinos
        ],
        maiores_favorecidos=await _maiores_favorecidos(session, filtro),
    )


async def _maiores_favorecidos(session: Session, filtro: FiltroEmenda) -> list[TotalChave]:
    f = EmendaFavorecido
    stmt = (
        select(
            f.favorecido_documento,
            func.max(f.favorecido_nome),
            func.sum(f.valor),
            func.count(),
        )
        .where(f.favorecido_documento.is_not(None), ~f.favorecido_documento.contains("*"))
        .group_by(f.favorecido_documento)
        .order_by(desc(func.sum(f.valor)))
        .limit(20)
    )
    if filtro.ano:
        stmt = stmt.where(f.ano == filtro.ano)
    if filtro.politico is not None:
        stmt = stmt.where(f.politico_id == filtro.politico)
    if filtro.uf:
        stmt = stmt.where(f.uf == filtro.uf.upper())
    if filtro.tipo:
        stmt = stmt.where(f.tipo.icontains(filtro.tipo, autoescape=True))
    if filtro.autor:
        stmt = stmt.where(f.autor_nome_normalizado.contains(normalize(filtro.autor)))
    return [
        TotalChave(chave=doc, rotulo=nome, empenhado=total, pago=total, quantidade=q)
        for doc, nome, total, q in await session.execute(stmt)
    ]


@router.get(
    "/favorecidos",
    response_model=Page[FavorecidoOut],
    summary="Pagamentos de emendas por favorecido (quem recebeu o dinheiro)",
)
async def listar_favorecidos(
    request: Request,
    session: Session,
    paging: Paging,
    ano: int | None = Query(None, ge=2000, le=2100),
    politico: int | None = Query(None, description="ID do político autor"),
    favorecido: str | None = Query(None, description="CNPJ (só dígitos) ou trecho do nome"),
    emenda: str | None = Query(None, description="Código da emenda"),
    uf: str | None = Query(None, min_length=2, max_length=2),
):
    f = EmendaFavorecido
    stmt = select(f).order_by(f.id).limit(paging.limit + 1)
    if ano:
        stmt = stmt.where(f.ano == ano)
    if politico is not None:
        stmt = stmt.where(f.politico_id == politico)
    if favorecido:
        d = digits(favorecido)
        if len(d) == 14:
            stmt = stmt.where(f.favorecido_documento == d)
        else:
            stmt = stmt.where(f.favorecido_nome.icontains(favorecido.strip(), autoescape=True))
    if emenda:
        stmt = stmt.where(f.emenda_codigo == emenda)
    if uf:
        stmt = stmt.where(f.uf == uf.upper())
    if paging.after is not None:
        stmt = stmt.where(f.id > int(paging.after))
    rows = list((await session.scalars(stmt)).all())
    has_more = len(rows) > paging.limit
    rows = rows[: paging.limit]
    page = Page(
        items=[FavorecidoOut.model_validate(r) for r in rows],
        next_cursor=encode_cursor(rows[-1].id) if has_more else None,
    )
    return page_or_csv(request, page, "emendas_favorecidos")
