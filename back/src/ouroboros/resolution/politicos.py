"""Resolução de identidade: liga pessoas vindas de qualquer fonte a uma linha de `politico`.

Ordem de decisão para cada (origem, id_externo):
1. já ligado antes (politico_identificador) -> mesmo político;
2. mesmo CPF (HMAC) -> mesmo político;
3. mesmo nome civil normalizado + data de nascimento, com um único candidato e sem CPF
   conflitante -> mesmo político;
4. mesma data de nascimento + nome aproximado (ver `nomes.py`), único candidato -> mesmo político;
5. senão cria político novo. Empate em (3) ou (4) vira `match_pendente` para revisão manual.

CPF igual em dois políticos prova que são a mesma pessoa: as linhas são fundidas (`fusao.py`).

Trabalha em lote (uma consulta por critério), porque o TSE traz dezenas/centenas de milhares
de pessoas por eleição.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

from loguru import logger
from sqlalchemy import BigInteger, Date, String, any_, bindparam, func, select, update
from sqlalchemy.dialects.postgresql import ARRAY, insert
from sqlalchemy.ext.asyncio import AsyncSession

from ouroboros.canonical import CpfPessoaRow, PessoaRow
from ouroboros.core.text import normalize
from ouroboros.models.politico import MatchPendente, Politico, PoliticoIdentificador
from ouroboros.resolution.fusao import fundir_politicos
from ouroboros.resolution.nomes import mesma_pessoa

# Nome exibido: nome parlamentar (Câmara/Senado) vence nome de urna (TSE).
PRIORIDADE_NOME = {"tse": 1}
PRIORIDADE_PADRAO = 3
_CHUNK = 2000

NomeKey = tuple[str, date]


def _any(values: Sequence[object], item_type=String):
    return any_(bindparam(None, list(values), type_=ARRAY(item_type)))


def _nome_key(p: PessoaRow) -> NomeKey | None:
    if p.nome_civil and p.data_nascimento:
        return normalize(p.nome_civil), p.data_nascimento
    return None


_CAMPOS_ATUALIZAVEIS = (
    Politico.id,
    Politico.nome,
    Politico.nome_normalizado,
    Politico.nome_origem,
    Politico.nome_civil,
    Politico.nome_civil_normalizado,
    Politico.data_nascimento,
    Politico.genero,
    Politico.cpf_hmac,
    Politico.foto_url,
)


def _prioridade(origem: str) -> int:
    return PRIORIDADE_NOME.get(origem, PRIORIDADE_PADRAO)


def _completar(
    atual: dict, p: PessoaRow, origem: str, prioridade: int, *, pode_renomear: bool = True
) -> dict:
    """Estado do político depois de incorporar `p`: preenche vazios, nunca apaga.

    Nome exibido troca só para fonte de prioridade maior, ou quando a mesma fonte mudou o nome.
    Foto: a mais recente vence.
    """
    novo = dict(atual)
    prio_atual = _prioridade(atual["nome_origem"])
    mesma_fonte_renomeou = origem == atual["nome_origem"] and p.nome != atual["nome"]
    if pode_renomear and (prioridade > prio_atual or mesma_fonte_renomeou):
        novo.update(nome=p.nome, nome_normalizado=normalize(p.nome), nome_origem=origem)
    if novo["nome_civil"] is None and p.nome_civil:
        novo.update(nome_civil=p.nome_civil, nome_civil_normalizado=normalize(p.nome_civil))
    for campo in ("data_nascimento", "genero", "cpf_hmac"):
        if novo[campo] is None and getattr(p, campo):
            novo[campo] = getattr(p, campo)
    if p.foto_url:
        novo["foto_url"] = p.foto_url
    return novo


@dataclass
class Resolucao:
    politico_por_id_externo: dict[str, int] = field(default_factory=dict)
    criados: int = 0
    metodos: Counter[str] = field(default_factory=Counter)
    pendentes: int = 0
    fusoes: int = 0


@dataclass
class _Pendente:
    origem: str
    id_externo: str
    motivo: str
    politico_ids: list[int]


def _merge(rows: list[PessoaRow]) -> PessoaRow:
    """Junta linhas da mesma pessoa no lote: primeiro valor não nulo de cada campo."""
    base = rows[0]
    if len(rows) == 1:
        return base
    updates = {}
    for campo in ("nome_civil", "data_nascimento", "genero", "cpf_hmac", "foto_url"):
        if getattr(base, campo) is None:
            updates[campo] = next((getattr(r, campo) for r in rows if getattr(r, campo)), None)
    return base.model_copy(update=updates)


async def resolver_pessoas(session: AsyncSession, pessoas: Sequence[PessoaRow]) -> Resolucao:
    res = Resolucao()
    if not pessoas:
        return res
    origens = {p.origem for p in pessoas}
    if len(origens) != 1:
        raise ValueError(f"lote com mais de uma origem: {origens}")
    origem = origens.pop()

    unicas = list({p.id_externo: p for p in pessoas}.values())
    ids = [p.id_externo for p in unicas]

    # --- consultas em lote -------------------------------------------------------------
    ligados: dict[str, int] = {}
    nome_ligado: dict[str, str] = {}
    for i in range(0, len(ids), 10 * _CHUNK):
        rows = await session.execute(
            select(
                PoliticoIdentificador.id_externo,
                PoliticoIdentificador.politico_id,
                PoliticoIdentificador.nome_na_fonte,
            ).where(
                PoliticoIdentificador.origem == origem,
                PoliticoIdentificador.id_externo == _any(ids[i : i + 10 * _CHUNK]),
            )
        )
        for id_externo, pid, nome in rows:
            ligados[id_externo] = pid
            nome_ligado[id_externo] = nome

    cpfs = sorted({p.cpf_hmac for p in unicas if p.cpf_hmac})
    dono_cpf: dict[str, int] = {}
    if cpfs:
        rows = await session.execute(
            select(Politico.cpf_hmac, Politico.id).where(Politico.cpf_hmac == _any(cpfs))
        )
        dono_cpf = dict(rows.all())

    nome_keys = {k for p in unicas if (k := _nome_key(p))}
    por_nome: dict[NomeKey, list[tuple[int, str | None]]] = {}
    if nome_keys:
        rows = await session.execute(
            select(
                Politico.nome_civil_normalizado,
                Politico.data_nascimento,
                Politico.id,
                Politico.cpf_hmac,
            ).where(
                Politico.nome_civil_normalizado == _any(sorted({k[0] for k in nome_keys})),
                Politico.data_nascimento.is_not(None),
            )
        )
        for nome, nasc, pid, cpf in rows.all():
            if (nome, nasc) in nome_keys:
                por_nome.setdefault((nome, nasc), []).append((pid, cpf))

    # candidatos a nome aproximado: mesma data de nascimento, sem match exato.
    # Quem tem CPF só compara com políticos sem CPF (com CPF, o passo 2 já teria achado).
    sem_exato = [
        p
        for p in unicas
        if p.id_externo not in ligados
        and not (p.cpf_hmac and p.cpf_hmac in dono_cpf)
        and (k := _nome_key(p))
        and k not in por_nome
    ]
    por_data: dict[date, list[tuple[int, str, str | None]]] = {}
    datas_todos = sorted({p.data_nascimento for p in sem_exato if not p.cpf_hmac})
    datas_sem_cpf = sorted({p.data_nascimento for p in sem_exato} - set(datas_todos))
    for datas, so_sem_cpf in ((datas_todos, False), (datas_sem_cpf, True)):
        if not datas:
            continue
        stmt = select(
            Politico.data_nascimento, Politico.id, Politico.nome_civil, Politico.cpf_hmac
        ).where(Politico.data_nascimento == _any(datas, Date), Politico.nome_civil.is_not(None))
        if so_sem_cpf:
            stmt = stmt.where(Politico.cpf_hmac.is_(None))
        for nasc, pid, nome_civil, cpf in await session.execute(stmt):
            por_data.setdefault(nasc, []).append((pid, nome_civil, cpf))

    # --- decisão por pessoa ------------------------------------------------------------
    existentes: dict[str, tuple[int, PessoaRow]] = {}  # id_externo -> (politico_id, pessoa)
    metodo_por_id: dict[str, str] = {}
    grupos_novos: list[list[PessoaRow]] = []
    novo_por_cpf: dict[str, int] = {}
    novo_por_nome: dict[NomeKey, int] = {}
    pendentes: list[_Pendente] = []

    for p in unicas:
        key = _nome_key(p)
        if p.id_externo in ligados:
            existentes[p.id_externo] = (ligados[p.id_externo], p)
            continue
        if p.cpf_hmac and p.cpf_hmac in dono_cpf:
            existentes[p.id_externo] = (dono_cpf[p.cpf_hmac], p)
            metodo_por_id[p.id_externo] = "cpf"
            continue
        candidatos = por_nome.get(key, []) if key else []
        compativeis = sorted(
            {pid for pid, cpf in candidatos if not (cpf and p.cpf_hmac and cpf != p.cpf_hmac)}
        )
        if len(compativeis) == 1:
            existentes[p.id_externo] = (compativeis[0], p)
            metodo_por_id[p.id_externo] = "nome_nascimento"
            continue
        if len(compativeis) > 1:
            pendentes.append(
                _Pendente(origem, p.id_externo, "nome_nascimento_ambiguo", compativeis)
            )
        elif key and p.nome_civil:
            aproximados = sorted(
                {
                    pid
                    for pid, nome_civil, cpf in por_data.get(p.data_nascimento, [])
                    if not (cpf and p.cpf_hmac and cpf != p.cpf_hmac)
                    and mesma_pessoa(p.nome_civil, nome_civil)
                }
            )
            if len(aproximados) == 1:
                existentes[p.id_externo] = (aproximados[0], p)
                metodo_por_id[p.id_externo] = "nome_aproximado"
                continue
            if len(aproximados) > 1:
                pendentes.append(
                    _Pendente(origem, p.id_externo, "nome_aproximado_ambiguo", aproximados)
                )

        # pessoa nova: agrupa com outra nova do mesmo lote (mesmo CPF ou nome+nascimento)
        idx = None
        if p.cpf_hmac:
            idx = novo_por_cpf.get(p.cpf_hmac)
        if idx is None and key and not p.cpf_hmac:
            idx = novo_por_nome.get(key)
        if idx is None:
            idx = len(grupos_novos)
            grupos_novos.append([])
        grupos_novos[idx].append(p)
        if p.cpf_hmac:
            novo_por_cpf.setdefault(p.cpf_hmac, idx)
        if key:
            novo_por_nome.setdefault(key, idx)

    # --- cria políticos novos ----------------------------------------------------------
    prioridade = _prioridade(origem)
    for start in range(0, len(grupos_novos), _CHUNK):
        chunk = grupos_novos[start : start + _CHUNK]
        merged = [_merge(g) for g in chunk]
        values = [
            {
                "nome": m.nome,
                "nome_normalizado": normalize(m.nome),
                "nome_origem": origem,
                "nome_civil": m.nome_civil,
                "nome_civil_normalizado": normalize(m.nome_civil) if m.nome_civil else None,
                "data_nascimento": m.data_nascimento,
                "genero": m.genero,
                "cpf_hmac": m.cpf_hmac,
                "foto_url": m.foto_url,
            }
            for m in merged
        ]
        novos_ids = (
            await session.scalars(
                insert(Politico).returning(Politico.id, sort_by_parameter_order=True), values
            )
        ).all()
        for grupo, pid in zip(chunk, novos_ids, strict=True):
            for i, p in enumerate(grupo):
                res.politico_por_id_externo[p.id_externo] = pid
                # primeiro do grupo criou o político; demais foram agrupados no mesmo lote
                metodo_por_id[p.id_externo] = "origem" if i == 0 else "lote"
        res.criados += len(chunk)

    # --- completa dados de políticos que já existiam (só grava o que muda) -------------
    for id_externo, (pid, _) in existentes.items():
        res.politico_por_id_externo[id_externo] = pid
    atuais: dict[int, dict] = {}
    pids = sorted({pid for pid, _ in existentes.values()})
    for i in range(0, len(pids), 10 * _CHUNK):
        rows = await session.execute(
            select(*_CAMPOS_ATUALIZAVEIS).where(
                Politico.id == _any(pids[i : i + 10 * _CHUNK], BigInteger)
            )
        )
        atuais.update({r["id"]: dict(r) for r in rows.mappings()})

    cpf_atribuido: dict[str, int] = dict(dono_cpf)
    alterados: dict[int, dict] = {}
    vistos: set[int] = set()
    fusoes: list[tuple[int, int]] = []
    for pid, p in existentes.values():
        atual = alterados.get(pid) or atuais[pid]
        # mesma pessoa repetida no lote (ex.: dois SQ no TSE): só a primeira define o nome,
        # senão o nome alterna a cada recarga
        novo = _completar(atual, p, origem, prioridade, pode_renomear=pid not in vistos)
        vistos.add(pid)
        if novo.get("cpf_hmac") and novo["cpf_hmac"] != atual["cpf_hmac"]:
            dono = cpf_atribuido.get(novo["cpf_hmac"])
            if dono is not None and dono != pid:
                fusoes.append((pid, dono))
                novo["cpf_hmac"] = atual["cpf_hmac"]
            else:
                cpf_atribuido[novo["cpf_hmac"]] = pid
        if novo != atual:
            alterados[pid] = novo
    if alterados:
        logger.debug("resolução {}: {} políticos atualizados", origem, len(alterados))
        t = Politico.__table__.c
        cols = [c.key for c in _CAMPOS_ATUALIZAVEIS if c.key != "id"]
        stmt = (
            update(Politico.__table__)
            .where(t.id == bindparam("v_id"))
            .values({**{c: bindparam(f"v_{c}") for c in cols}, "atualizado_em": func.now()})
        )
        params = [{f"v_{k}": v for k, v in row.items()} for row in alterados.values()]
        for start in range(0, len(params), _CHUNK):
            await session.execute(stmt, params[start : start + _CHUNK])

    # --- grava identificadores novos ou com nome mudado --------------------------------
    ident_values = [
        {
            "origem": origem,
            "id_externo": p.id_externo,
            "politico_id": res.politico_por_id_externo[p.id_externo],
            "metodo": metodo_por_id.get(p.id_externo, "origem"),
            "nome_na_fonte": p.nome,
            "nome_na_fonte_normalizado": normalize(p.nome),
        }
        for p in unicas
        if p.id_externo not in ligados or nome_ligado[p.id_externo] != p.nome
    ]
    for start in range(0, len(ident_values), _CHUNK):
        stmt = insert(PoliticoIdentificador).values(ident_values[start : start + _CHUNK])
        stmt = stmt.on_conflict_do_update(
            index_elements=[PoliticoIdentificador.origem, PoliticoIdentificador.id_externo],
            set_={
                "nome_na_fonte": stmt.excluded.nome_na_fonte,
                "nome_na_fonte_normalizado": stmt.excluded.nome_na_fonte_normalizado,
                "atualizado_em": func.now(),
            },
        )
        await session.execute(stmt)

    await _gravar_pendentes(session, pendentes)

    if fusoes:
        mantido = await _fundir_todos(session, fusoes)
        res.politico_por_id_externo = {
            k: mantido.get(v, v) for k, v in res.politico_por_id_externo.items()
        }
        res.fusoes = len(fusoes)

    res.metodos = Counter(metodo_por_id.get(i, "existente") for i in ids if i not in ligados)
    res.metodos["ja_ligado"] = len(ligados)
    res.pendentes = len(pendentes)
    logger.info(
        "resolução {}: {} pessoas, {} políticos novos, métodos={}, pendentes={}, fusões={}",
        origem,
        len(unicas),
        res.criados,
        dict(res.metodos),
        res.pendentes,
        res.fusoes,
    )
    return res


async def _fundir_todos(session: AsyncSession, pares: Sequence[tuple[int, int]]) -> dict[int, int]:
    """Funde cada par (seguindo fusões anteriores do mesmo lote). Retorna removido -> mantido."""
    destino: dict[int, int] = {}

    def raiz(x: int) -> int:
        while x in destino:
            x = destino[x]
        return x

    for a, b in pares:
        ra, rb = raiz(a), raiz(b)
        if ra == rb:
            continue
        mantido = await fundir_politicos(session, ra, rb)
        destino[rb if mantido == ra else ra] = mantido
    return {x: raiz(x) for x in destino}


async def _gravar_pendentes(session: AsyncSession, pendentes: Sequence[_Pendente]) -> None:
    if not pendentes:
        return
    values = [
        {
            "origem": p.origem,
            "id_externo": p.id_externo,
            "motivo": p.motivo,
            "politico_ids": p.politico_ids,
        }
        for p in pendentes
    ]
    for start in range(0, len(values), _CHUNK):
        await session.execute(
            insert(MatchPendente)
            .values(values[start : start + _CHUNK])
            .on_conflict_do_nothing(constraint="uq_match_pendente")
        )


async def aplicar_cpfs(session: AsyncSession, cpfs: Sequence[CpfPessoaRow]) -> int:
    """Preenche cpf_hmac de políticos já ligados, a partir de CPF visto em fonte secundária.

    Se o CPF já pertence a outro político, as duas linhas são a mesma pessoa: são fundidas.
    """
    if not cpfs:
        return 0
    unicos = {(c.origem, c.id_externo): c for c in cpfs}
    origens = {o for o, _ in unicos}
    ligados: dict[tuple[str, str], int] = {}
    for origem in origens:
        rows = await session.execute(
            select(PoliticoIdentificador.id_externo, PoliticoIdentificador.politico_id).where(
                PoliticoIdentificador.origem == origem,
                PoliticoIdentificador.id_externo == _any([i for o, i in unicos if o == origem]),
            )
        )
        ligados.update({(origem, i): pid for i, pid in rows.all()})

    hashes = sorted({c.cpf_hmac for c in unicos.values()})
    dono = dict(
        (
            await session.execute(
                select(Politico.cpf_hmac, Politico.id).where(Politico.cpf_hmac == _any(hashes))
            )
        ).all()
    )
    pids = sorted(set(ligados.values()))
    atual = dict(
        (
            await session.execute(
                select(Politico.id, Politico.cpf_hmac).where(Politico.id == _any(pids, BigInteger))
            )
        ).all()
    )

    params, fusoes = [], []
    for (origem, id_externo), c in unicos.items():
        pid = ligados.get((origem, id_externo))
        if pid is None or atual.get(pid):
            continue
        outro = dono.get(c.cpf_hmac)
        if outro is not None and outro != pid:
            fusoes.append((pid, outro))
            continue
        dono[c.cpf_hmac] = pid
        atual[pid] = c.cpf_hmac
        params.append({"pid": pid, "p_cpf": c.cpf_hmac})

    if params:
        t = Politico.__table__.c
        await session.execute(
            update(Politico.__table__)
            .where(t.id == bindparam("pid"))
            .values(cpf_hmac=bindparam("p_cpf"), atualizado_em=func.now()),
            params,
        )
    if fusoes:
        await _fundir_todos(session, fusoes)
    return len(params) + len(fusoes)
