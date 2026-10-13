"""Obras e convênios (Transferegov): para onde foi o dinheiro da emenda e em que pé está a obra.

Cada convênio liga as pontas do caminho do dinheiro: emenda (e o político autor) -> convênio
-> município/convenente -> contratos e pagamentos a fornecedores (empreiteiras).
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import Select, and_, desc, exists, func, or_, select

from ouroboros.api.deps import Paging, Session
from ouroboros.api.export import page_or_csv
from ouroboros.api.pagination import Page, encode_cursor
from ouroboros.api.schemas import (
    ObraContratoOut,
    ObraDesembolsoOut,
    ObraDetalhe,
    ObraEmendaOut,
    ObraFornecedorOut,
    ObraMetaOut,
    ObraOut,
    PontoObra,
    ResumoObras,
    TotalObras,
)
from ouroboros.core.privacy import digits
from ouroboros.models import (
    Convenio,
    ConvenioContrato,
    ConvenioDesembolso,
    ConvenioEmenda,
    ConvenioFornecedor,
    ConvenioMeta,
    Politico,
)

router = APIRouter(prefix="/obras", tags=["obras"])

C = Convenio
CE = ConvenioEmenda
ZERO = Decimal("0")
# Obra parada: tem acompanhamento físico (medição, % ou cadastro no Obrasgov), não chegou a 100%
# e está sem medição há 180+ dias ou com a vigência vencida ainda "em execução".
DIAS_PARADA = 180
ACOMPANHADA = or_(
    C.percentual_execucao.is_not(None), C.ultima_medicao.is_not(None), C.obra_id.is_not(None)
)
PARADA = and_(
    ACOMPANHADA,
    func.coalesce(C.percentual_execucao, 0) < 100,
    or_(
        C.dias_sem_medicao >= DIAS_PARADA,
        and_(C.fim_vigencia < func.current_date(), C.situacao.ilike("em execu%")),
    ),
)
LINK_TRANSFEREGOV = (
    "https://discricionarias.transferegov.sistema.gov.br/voluntarias/ConsultarProposta/"
    "ResultadoDaConsultaDePropostaDetalharProposta.do?idProposta={}&Usr=guest&Pwd=guest"
)
# ficha pública da obra na API do Obrasgov (não há página estável por obra na interface)
LINK_OBRASGOV = "https://api.obrasgov.gestao.gov.br/obrasgov/api/projeto-investimento?idUnico={}"


@dataclass
class FiltroObra:
    ano: int | None = Query(None, ge=2000, le=2100, description="Ano da proposta")
    uf: str | None = Query(None, min_length=2, max_length=2)
    municipio: int | None = Query(None, description="Código IBGE do município")
    politico: int | None = Query(None, description="ID do político autor de emenda no convênio")
    emenda: str | None = Query(None, description="Código da emenda (Portal da Transparência)")
    fornecedor: str | None = Query(None, description="CNPJ contratado ou pago pelo convênio")
    proponente: str | None = Query(None, description="CNPJ do convenente (prefeitura, entidade)")
    situacao: str | None = Query(None, description="Trecho da situação: execução, concluída...")
    orgao: str | None = Query(None, description="Trecho do ministério concedente")
    q: str | None = Query(None, description="Trecho do objeto ou nome da obra")
    com_local: bool | None = Query(None, description="Só obras com coordenadas")
    parada: bool | None = Query(None, description="Só obras paradas ou com prazo vencido")
    emendas: bool | None = Query(None, description="Só convênios financiados por emenda")

    def aplicar(self, stmt: Select) -> Select:
        if self.ano:
            stmt = stmt.where(C.ano == self.ano)
        if self.uf:
            stmt = stmt.where(C.uf == self.uf.upper())
        if self.municipio:
            stmt = stmt.where(C.municipio_codigo_ibge == self.municipio)
        if self.politico is not None:
            stmt = stmt.where(
                exists().where(CE.convenio_numero == C.numero, CE.politico_id == self.politico)
            )
        if self.emenda:
            stmt = stmt.where(
                exists().where(CE.convenio_numero == C.numero, CE.emenda_codigo == self.emenda)
            )
        if self.emendas is not None:
            tem = exists().where(CE.convenio_numero == C.numero)
            stmt = stmt.where(tem if self.emendas else ~tem)
        if self.fornecedor:
            doc = digits(self.fornecedor)
            stmt = stmt.where(
                or_(
                    exists().where(
                        ConvenioContrato.convenio_numero == C.numero,
                        ConvenioContrato.fornecedor_documento == doc,
                    ),
                    exists().where(
                        ConvenioFornecedor.convenio_numero == C.numero,
                        ConvenioFornecedor.documento == doc,
                    ),
                )
            )
        if self.proponente:
            stmt = stmt.where(C.proponente_cnpj == digits(self.proponente))
        if self.situacao:
            stmt = stmt.where(C.situacao.icontains(self.situacao, autoescape=True))
        if self.orgao:
            stmt = stmt.where(C.orgao_superior.icontains(self.orgao, autoescape=True))
        if self.q:
            stmt = stmt.where(
                or_(
                    C.objeto.icontains(self.q, autoescape=True),
                    C.obra_nome.icontains(self.q, autoescape=True),
                )
            )
        if self.com_local is not None:
            stmt = stmt.where(C.latitude.is_not(None) if self.com_local else C.latitude.is_(None))
        if self.parada is not None:
            stmt = stmt.where(PARADA if self.parada else ~PARADA)
        return stmt


Filtro = Annotated[FiltroObra, Depends()]


@router.get("", response_model=Page[ObraOut], summary="Obras e convênios (Transferegov)")
async def listar_obras(request: Request, session: Session, paging: Paging, filtro: Filtro):
    """Mais recentes primeiro (número do convênio decrescente)."""
    stmt = filtro.aplicar(select(C)).order_by(C.numero.desc()).limit(paging.limit + 1)
    if paging.after is not None:
        stmt = stmt.where(C.numero < int(paging.after))
    rows = list((await session.scalars(stmt)).all())
    has_more = len(rows) > paging.limit
    rows = rows[: paging.limit]
    page = Page(
        items=[ObraOut.model_validate(r) for r in rows],
        next_cursor=encode_cursor(rows[-1].numero) if has_more else None,
    )
    return page_or_csv(request, page, "obras")


async def _por(session: Session, filtro: FiltroObra, coluna, *, ordem=None, limite=None):
    stmt = filtro.aplicar(
        select(coluna, func.count(), func.sum(C.valor_global), func.sum(C.valor_desembolsado))
    ).group_by(coluna)
    stmt = stmt.order_by(ordem if ordem is not None else desc(func.sum(C.valor_global)))
    return [
        TotalObras(
            chave=None if k is None else str(k), quantidade=q, valor_global=g, valor_desembolsado=d
        )
        for k, q, g, d in await session.execute(stmt.limit(limite))
    ]


@router.get(
    "/resumo",
    response_model=ResumoObras,
    summary="Totais por situação, UF, ano, ministério, autores de emenda e fornecedores",
)
async def resumo_obras(session: Session, filtro: Filtro) -> ResumoObras:
    q, global_, repasse, desemb, local, paradas = (
        await session.execute(
            filtro.aplicar(
                select(
                    func.count(),
                    func.coalesce(func.sum(C.valor_global), 0),
                    func.coalesce(func.sum(C.valor_repasse), 0),
                    func.coalesce(func.sum(C.valor_desembolsado), 0),
                    func.count(C.latitude),
                    func.count().filter(PARADA),
                ).select_from(C)
            )
        )
    ).one()

    filtrados = filtro.aplicar(select(C.numero)).subquery()
    autores = await session.execute(
        select(
            CE.politico_id,
            func.max(CE.parlamentar_nome),
            func.count(func.distinct(CE.convenio_numero)),
            func.sum(CE.valor_repasse),
            func.sum(C.valor_desembolsado),
        )
        .join(C, C.numero == CE.convenio_numero)
        .where(CE.convenio_numero.in_(select(filtrados.c.numero)))
        .group_by(CE.politico_id, CE.parlamentar_nome_normalizado)
        .order_by(desc(func.sum(CE.valor_repasse)))
        .limit(20)
    )
    autores_out = [
        TotalObras(
            chave=str(pid) if pid else None,
            rotulo=nome,
            quantidade=n,
            valor_global=g or ZERO,
            valor_desembolsado=d or ZERO,
        )  # fmt: skip
        for pid, nome, n, g, d in autores
    ]
    nomes = await _nomes(session, {int(a.chave) for a in autores_out if a.chave})
    for a in autores_out:
        if a.chave:
            a.rotulo = nomes.get(int(a.chave), a.rotulo)

    K = ConvenioContrato
    contratados = (
        await session.execute(
            select(
                K.fornecedor_documento,
                func.max(K.fornecedor_nome),
                func.count(func.distinct(K.convenio_numero)),
                func.sum(K.valor),
            )
            .where(
                K.convenio_numero.in_(select(filtrados.c.numero)),
                func.length(K.fornecedor_documento) == 14,
            )
            .group_by(K.fornecedor_documento)
            .order_by(desc(func.sum(K.valor)))
            .limit(20)
        )
    ).all()
    docs = [d for d, *_ in contratados]
    pagos = dict(
        (
            await session.execute(
                select(ConvenioFornecedor.documento, func.sum(ConvenioFornecedor.valor))
                .where(
                    ConvenioFornecedor.documento.in_(docs),
                    ConvenioFornecedor.convenio_numero.in_(select(filtrados.c.numero)),
                )
                .group_by(ConvenioFornecedor.documento)
            )
        ).all()
    )

    return ResumoObras(
        quantidade=q,
        valor_global=global_,
        valor_repasse=repasse,
        valor_desembolsado=desemb,
        com_localizacao=local,
        paradas=paradas,
        por_situacao=await _por(session, filtro, C.situacao),
        por_uf=await _por(session, filtro, C.uf),
        por_ano=await _por(session, filtro, C.ano, ordem=C.ano),
        por_orgao=await _por(session, filtro, C.orgao_superior, limite=15),
        maiores_autores=autores_out,
        maiores_fornecedores=[
            TotalObras(
                chave=d,
                rotulo=nome,
                quantidade=n,
                valor_global=v,
                valor_desembolsado=pagos.get(d, ZERO),
            )  # fmt: skip
            for d, nome, n, v in contratados
        ],
    )


@router.get(
    "/mapa",
    response_model=list[PontoObra],
    summary="Obras com coordenadas, para mapa (maiores primeiro)",
)
async def mapa_obras(
    session: Session, filtro: Filtro, limite: int = Query(2000, ge=1, le=10000)
) -> list[PontoObra]:
    stmt = (
        filtro.aplicar(
            select(
                C.numero,
                C.latitude,
                C.longitude,
                func.coalesce(C.obra_nome, C.objeto),
                C.situacao,
                C.percentual_execucao,
                C.valor_global,
            )
        )
        .where(C.latitude.is_not(None), C.longitude.is_not(None))
        .order_by(C.valor_global.desc())
        .limit(limite)
    )
    return [
        PontoObra(
            numero=n,
            latitude=la,
            longitude=lo,
            rotulo=(r or f"Convênio {n}")[:200],
            situacao=s,
            percentual_execucao=p,
            valor_global=v,
        )  # fmt: skip
        for n, la, lo, r, s, p, v in await session.execute(stmt)
    ]


async def _nomes(session: Session, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    return dict(
        (
            await session.execute(select(Politico.id, Politico.nome).where(Politico.id.in_(ids)))
        ).all()
    )


@router.get("/{numero}", response_model=ObraDetalhe, summary="Obra/convênio com todo o caminho")
async def detalhe_obra(numero: int, session: Session) -> ObraDetalhe:
    c = await session.get(Convenio, numero)
    if c is None:
        raise HTTPException(status_code=404, detail="convênio não encontrado")

    async def todos(model, *ordem):
        return list(
            await session.scalars(
                select(model).where(model.convenio_numero == numero).order_by(*ordem)
            )
        )

    emendas = await todos(CE, CE.valor_repasse.desc())
    nomes = await _nomes(session, {e.politico_id for e in emendas if e.politico_id})
    fornecedores = await todos(ConvenioFornecedor, ConvenioFornecedor.valor.desc())
    base = ObraOut.model_validate(c).model_dump()
    extra = {
        k: getattr(c, k)
        for k in ObraDetalhe.model_fields
        if k not in base and hasattr(c, k) and k != "emendas"
    }
    return ObraDetalhe(
        **base,
        **extra,
        valor_pago_fornecedores=sum((f.valor for f in fornecedores), ZERO),
        emendas=[
            ObraEmendaOut.model_validate(e).model_copy(
                update={"politico_nome": nomes.get(e.politico_id) if e.politico_id else None}
            )
            for e in emendas
        ],
        metas=[
            ObraMetaOut.model_validate(m) for m in await todos(ConvenioMeta, ConvenioMeta.numero)
        ],
        desembolsos=[
            ObraDesembolsoOut.model_validate(d)
            for d in await todos(ConvenioDesembolso, ConvenioDesembolso.data)
        ],
        contratos=[
            ObraContratoOut.model_validate(k)
            for k in await todos(ConvenioContrato, ConvenioContrato.valor.desc())
        ],
        fornecedores=[ObraFornecedorOut.model_validate(f) for f in fornecedores],
        link_transferegov=LINK_TRANSFEREGOV.format(c.proposta_id),
        link_obrasgov=LINK_OBRASGOV.format(c.obra_id) if c.obra_id else None,
    )
