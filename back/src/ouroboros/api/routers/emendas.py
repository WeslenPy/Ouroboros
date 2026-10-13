from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import Integer, Select, String, cast, desc, func, select

from ouroboros.api.deps import Paging, Session
from ouroboros.api.export import page_or_csv
from ouroboros.api.pagination import Page, encode_cursor
from ouroboros.api.schemas import (
    EmendaDetalhe,
    EmendaOut,
    FavorecidoOut,
    ObraOut,
    ResumoEmendas,
    TotalChave,
    TransferenciaEspecialExecutorOut,
    TransferenciaEspecialOut,
)
from ouroboros.core.privacy import digits
from ouroboros.core.text import normalize
from ouroboros.models import (
    Convenio,
    ConvenioEmenda,
    Emenda,
    EmendaConvenio,
    EmendaFavorecido,
    Politico,
    TransferenciaEspecial,
    TransferenciaEspecialExecutor,
    TransferenciaEspecialPagamento,
)

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


T = TransferenciaEspecial


async def _transferencias(session: Session, stmt: Select) -> list[TransferenciaEspecialOut]:
    """Planos de transferência especial com executores (objeto) e total pago."""
    planos = list((await session.scalars(stmt)).all())
    if not planos:
        return []
    ids = [p.id for p in planos]
    pagos = dict(
        (
            await session.execute(
                select(
                    TransferenciaEspecialPagamento.plano_id,
                    func.sum(TransferenciaEspecialPagamento.valor),
                )
                .where(TransferenciaEspecialPagamento.plano_id.in_(ids))
                .group_by(TransferenciaEspecialPagamento.plano_id)
            )
        ).all()
    )
    executores: dict[int, list[TransferenciaEspecialExecutorOut]] = {}
    for e in await session.scalars(
        select(TransferenciaEspecialExecutor).where(TransferenciaEspecialExecutor.plano_id.in_(ids))
    ):
        executores.setdefault(e.plano_id, []).append(
            TransferenciaEspecialExecutorOut.model_validate(e)
        )
    return [
        TransferenciaEspecialOut.model_validate(p).model_copy(
            update={
                "valor_pago": pagos.get(p.id) or Decimal("0"),
                "executores": executores.get(p.id, []),
            }
        )
        for p in planos
    ]


@router.get(
    "/transferencias-especiais",
    response_model=Page[TransferenciaEspecialOut],
    summary="Transferências especiais (emendas Pix): plano, executor e objeto",
)
async def listar_transferencias(
    session: Session,
    paging: Paging,
    ano: int | None = Query(None, ge=2000, le=2100),
    politico: int | None = Query(None, description="ID do político autor"),
    emenda: str | None = Query(None, description="Código da emenda"),
    uf: str | None = Query(None, min_length=2, max_length=2),
    municipio: int | None = Query(None, description="Código IBGE do município beneficiário"),
    beneficiario: str | None = Query(None, description="CNPJ do beneficiário"),
):
    stmt = select(T).order_by(T.id.desc()).limit(paging.limit + 1)
    if ano:
        stmt = stmt.where(T.ano == ano)
    if politico is not None:
        stmt = stmt.where(T.politico_id == politico)
    if emenda:
        stmt = stmt.where(T.emenda_codigo == emenda)
    if uf:
        stmt = stmt.where(T.uf == uf.upper())
    if municipio:
        stmt = stmt.where(T.municipio_codigo_ibge == municipio)
    if beneficiario:
        stmt = stmt.where(T.beneficiario_cnpj == digits(beneficiario))
    if paging.after is not None:
        stmt = stmt.where(T.id < int(paging.after))
    items = await _transferencias(session, stmt)
    has_more = len(items) > paging.limit
    items = items[: paging.limit]
    return Page(items=items, next_cursor=encode_cursor(items[-1].id) if has_more else None)


@router.get(
    "/{codigo}",
    response_model=EmendaDetalhe,
    summary="Uma emenda de ponta a ponta: destinos, favorecidos, obras e transferências",
)
async def detalhe_emenda(codigo: str, session: Session) -> EmendaDetalhe:
    destinos = list(
        await session.scalars(select(E).where(E.codigo == codigo).order_by(PAGO.desc()))
    )
    if not destinos:
        raise HTTPException(status_code=404, detail="emenda não encontrada")
    primeira = destinos[0]
    politico_id = next((d.politico_id for d in destinos if d.politico_id), None)
    politico_nome = (
        await session.scalar(select(Politico.nome).where(Politico.id == politico_id))
        if politico_id
        else None
    )

    f = EmendaFavorecido
    favorecidos = [
        TotalChave(chave=doc, rotulo=nome, empenhado=total, pago=total, quantidade=q)
        for doc, nome, total, q in await session.execute(
            select(
                f.favorecido_documento, func.max(f.favorecido_nome), func.sum(f.valor), func.count()
            )
            .where(f.emenda_codigo == codigo)
            .group_by(f.favorecido_documento)
            .order_by(desc(func.sum(f.valor)))
            .limit(50)
        )
    ]
    # convênio pela emenda no Transferegov ou pelo número que a Transparência informa
    numeros = select(ConvenioEmenda.convenio_numero).where(ConvenioEmenda.emenda_codigo == codigo)
    numeros_cgu = select(cast(EmendaConvenio.numero, Integer)).where(
        EmendaConvenio.emenda_codigo == codigo, EmendaConvenio.numero.op("~")("^[0-9]{1,9}$")
    )
    obras = [
        ObraOut.model_validate(c)
        for c in await session.scalars(
            select(Convenio)
            .where(Convenio.numero.in_(numeros) | Convenio.numero.in_(numeros_cgu))
            .order_by(Convenio.valor_global.desc())
        )
    ]
    return EmendaDetalhe(
        codigo=codigo,
        ano=primeira.ano,
        tipo=primeira.tipo,
        autor_nome=primeira.autor_nome,
        politico_id=politico_id,
        politico_nome=politico_nome,
        empenhado=sum((d.valor_empenhado for d in destinos), Decimal("0")),
        pago=sum((d.valor_pago + d.valor_rp_pago for d in destinos), Decimal("0")),
        destinos=[EmendaOut.model_validate(d) for d in destinos],
        favorecidos=favorecidos,
        obras=obras,
        transferencias_especiais=await _transferencias(
            session, select(T).where(T.emenda_codigo == codigo).order_by(T.id)
        ),
    )
