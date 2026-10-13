"""Consultas compartilhadas entre routers."""

from dataclasses import dataclass
from datetime import date

from fastapi import Query
from sqlalchemy import Select, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ouroboros.api.schemas import (
    ResumoDespesas,
    TotalAno,
    TotalCategoria,
    TotalFornecedor,
    TotalMes,
)
from ouroboros.models.despesa import DespesaGabinete


@dataclass
class FiltroDespesa:
    ano: int | None = Query(None, ge=2000, le=2100)
    mes: int | None = Query(None, ge=1, le=12)
    verba: str | None = Query(None, description="CEAP (Câmara), CEAPS (Senado)")
    uf: str | None = Query(None, min_length=2, max_length=2)
    categoria: str | None = Query(None, description="Trecho da categoria, sem diferenciar caixa")
    fornecedor: str | None = Query(
        None, description="CNPJ (só dígitos) ou trecho do nome do fornecedor"
    )
    politico_id: int | None = Query(None, description="Só despesas ligadas a este político")
    data_inicio: date | None = Query(None, description="Data de emissão a partir de (inclusive)")
    data_fim: date | None = Query(None, description="Data de emissão até (inclusive)")

    def aplicar(self, stmt: Select, politico_id: int | None = None) -> Select:
        d = DespesaGabinete
        if politico_id is not None:
            stmt = stmt.where(d.politico_id == politico_id)
        if self.politico_id is not None:
            stmt = stmt.where(d.politico_id == self.politico_id)
        if self.data_inicio:
            stmt = stmt.where(d.data_emissao >= self.data_inicio)
        if self.data_fim:
            stmt = stmt.where(d.data_emissao <= self.data_fim)
        if self.ano:
            stmt = stmt.where(d.ano == self.ano)
        if self.mes:
            stmt = stmt.where(d.mes == self.mes)
        if self.verba:
            stmt = stmt.where(d.verba == self.verba.upper())
        if self.uf:
            stmt = stmt.where(d.uf == self.uf.upper())
        if self.categoria:
            stmt = stmt.where(d.categoria.icontains(self.categoria, autoescape=True))
        if self.fornecedor:
            f = self.fornecedor.strip()
            digitos = "".join(c for c in f if c.isdigit())
            if len(digitos) == 14:
                stmt = stmt.where(d.fornecedor_documento == digitos)
            else:
                stmt = stmt.where(d.fornecedor_nome.icontains(f, autoescape=True))
        return stmt


async def resumo_despesas(
    session: AsyncSession, filtro: FiltroDespesa, politico_id: int | None = None
) -> ResumoDespesas:
    d = DespesaGabinete
    total, quantidade = (
        await session.execute(
            filtro.aplicar(
                select(func.coalesce(func.sum(d.valor_liquido), 0), func.count()), politico_id
            )
        )
    ).one()

    soma = func.sum(d.valor_liquido).label("total")
    qtd = func.count().label("quantidade")
    por_ano = await session.execute(
        filtro.aplicar(select(d.ano, soma, qtd), politico_id).group_by(d.ano).order_by(d.ano)
    )
    por_mes = await session.execute(
        filtro.aplicar(select(d.ano, d.mes, soma, qtd), politico_id)
        .group_by(d.ano, d.mes)
        .order_by(d.ano, d.mes)
    )
    por_categoria = await session.execute(
        filtro.aplicar(select(d.categoria, soma, qtd), politico_id)
        .group_by(d.categoria)
        .order_by(desc("total"))
    )
    fornecedores = await session.execute(
        filtro.aplicar(
            select(d.fornecedor_documento, func.max(d.fornecedor_nome).label("nome"), soma, qtd),
            politico_id,
        )
        .group_by(d.fornecedor_documento)
        .order_by(desc("total"))
        .limit(20)
    )
    return ResumoDespesas(
        total=total,
        quantidade=quantidade,
        por_ano=[TotalAno(ano=a, total=t, quantidade=q) for a, t, q in por_ano],
        por_mes=[TotalMes(ano=a, mes=m, total=t, quantidade=q) for a, m, t, q in por_mes],
        por_categoria=[
            TotalCategoria(categoria=c, total=t, quantidade=q) for c, t, q in por_categoria
        ],
        maiores_fornecedores=[
            TotalFornecedor(fornecedor_documento=doc, fornecedor_nome=n, total=t, quantidade=q)
            for doc, n, t, q in fornecedores
        ],
    )
