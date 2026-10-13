"""Coleta de fotos de políticos e escolha da foto principal.

Fontes:
- Câmara: https://www.camara.leg.br/internet/deputado/bandep/{id}.jpg
- Senado: https://www.senado.leg.br/senadores/img/fotos-oficiais/senador{codigo}.jpg
- TSE: um ZIP por UF e eleição com a foto de todo candidato, arquivo `[F]{UF}{SQ}_div.jpg`

As fotos são ligadas pelos identificadores que a resolução de identidade já gravou
(id Câmara, código Senado, SQ_CANDIDATO), então este job roda depois das cargas de pessoas.
Tudo é incremental por GET condicional (ETag): rodar de novo só baixa o que mudou.
"""

import asyncio
import io
import re
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import httpx
from loguru import logger
from sqlalchemy import String, and_, cast, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ouroboros.core.db import get_sessionmaker
from ouroboros.core.http import HttpClient
from ouroboros.core.media_store import Imagem, ImagemInvalida, MediaStore
from ouroboros.core.settings import get_settings
from ouroboros.models.foto import PoliticoFoto, RecursoRemoto
from ouroboros.models.mandato import Candidatura, Mandato
from ouroboros.models.politico import PoliticoIdentificador
from ouroboros.pipelines.runner import registrar_execucao
from ouroboros.resolution.fotos import atualizar_fotos_principais

FOTO_CASA_URL = {
    "camara": "https://www.camara.leg.br/internet/deputado/bandep/{id}.jpg",
    "senado": "https://www.senado.leg.br/senadores/img/fotos-oficiais/senador{id}.jpg",
}
TSE_FOTOS_URL = (
    "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes{ano}/fotos/"
    "foto_cand{ano}_{uf}_div.zip"
)
_ARQUIVO_TSE = re.compile(r"^F?[A-Z]{2}(\d+)_div\.(?:jpe?g|png)$", re.IGNORECASE)
_LOTE = 500
_CONCORRENCIA = 8


@dataclass(frozen=True)
class FotoColetada:
    origem: str
    id_externo: str
    politico_id: int
    ano: int | None
    url_origem: str
    imagem: Imagem
    etag: str | None


async def _gravar(session: AsyncSession, fotos: Sequence[FotoColetada]) -> None:
    if not fotos:
        return
    values = [
        {
            "origem": f.origem,
            "id_externo": f.id_externo,
            "politico_id": f.politico_id,
            "ano": f.ano,
            "url_origem": f.url_origem,
            "sha256": f.imagem.sha256,
            "extensao": f.imagem.extensao,
            "content_type": f.imagem.content_type,
            "tamanho_bytes": f.imagem.tamanho_bytes,
            "largura": f.imagem.largura,
            "altura": f.imagem.altura,
            "etag": f.etag,
        }
        for f in fotos
    ]
    stmt = insert(PoliticoFoto).values(values)
    await session.execute(
        stmt.on_conflict_do_update(
            constraint="uq_politico_foto_origem_id",
            set_={
                **{c: stmt.excluded[c] for c in values[0] if c not in ("origem", "id_externo")},
                "obtida_em": func.now(),
            },
        )
    )


async def coletar_fotos_casa(origem: str) -> int:
    """Fotos oficiais de quem tem identificador na casa (`camara` ou `senado`)."""
    url_tpl = FOTO_CASA_URL[origem]
    store = MediaStore()
    sm = get_sessionmaker()
    async with registrar_execucao(origem, "fotos", "atual") as contador:
        async with sm() as s:
            alvos = (
                await s.execute(
                    select(
                        PoliticoIdentificador.id_externo,
                        PoliticoIdentificador.politico_id,
                        func.max(Mandato.fim),
                    )
                    .join(
                        Mandato,
                        and_(
                            Mandato.politico_id == PoliticoIdentificador.politico_id,
                            Mandato.origem == origem,
                        ),
                    )
                    .where(PoliticoIdentificador.origem == origem)
                    .group_by(PoliticoIdentificador.id_externo, PoliticoIdentificador.politico_id)
                )
            ).all()
            etags = dict(
                (
                    await s.execute(
                        select(PoliticoFoto.id_externo, PoliticoFoto.etag).where(
                            PoliticoFoto.origem == origem
                        )
                    )
                ).all()
            )

        ano_atual = date.today().year
        stats = {"nova": 0, "sem_mudanca": 0, "sem_foto": 0, "invalida": 0}
        coletadas: list[FotoColetada] = []
        sem = asyncio.Semaphore(_CONCORRENCIA)

        async def baixar(client: HttpClient, id_externo: str, pid: int, fim: date | None) -> None:
            url = url_tpl.format(id=id_externo)
            headers = {"If-None-Match": etags[id_externo]} if etags.get(id_externo) else {}
            async with sem:
                try:
                    r = await client.get(url, headers=headers)
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code in (403, 404):
                        stats["sem_foto"] += 1
                        return
                    raise
            if r.status_code == 304:
                stats["sem_mudanca"] += 1
                return
            try:
                imagem = store.save(r.content)
            except ImagemInvalida:
                stats["invalida"] += 1
                return
            stats["nova"] += 1
            coletadas.append(
                FotoColetada(
                    origem=origem,
                    id_externo=id_externo,
                    politico_id=pid,
                    ano=min(fim.year, ano_atual) if fim else None,
                    url_origem=url,
                    imagem=imagem,
                    etag=r.headers.get("etag"),
                )
            )

        async with HttpClient(max_calls_per_minute=300) as client:
            for start in range(0, len(alvos), _LOTE):
                await asyncio.gather(*(baixar(client, *a) for a in alvos[start : start + _LOTE]))
                async with sm() as s:
                    await _gravar(s, coletadas)
                    await s.commit()
                contador.registros += len(coletadas)
                coletadas.clear()

        async with sm() as s:
            await atualizar_fotos_principais(s)
            await s.commit()
        logger.info("fotos {}: {} alvos, {}", origem, len(alvos), stats)
    return contador.registros


async def coletar_fotos_tse(ano: str) -> int:
    """Fotos de todos os candidatos da eleição, UF por UF. ZIP sem mudança (ETag) é pulado."""
    store = MediaStore()
    sm = get_sessionmaker()
    async with registrar_execucao("tse", "fotos", ano) as contador:
        async with sm() as s:
            politico_por_sq = dict(
                (
                    await s.execute(
                        select(
                            PoliticoIdentificador.id_externo, PoliticoIdentificador.politico_id
                        ).where(
                            PoliticoIdentificador.origem == "tse",
                            PoliticoIdentificador.id_externo.in_(
                                select(cast(Candidatura.sq_candidato, String)).where(
                                    Candidatura.ano == int(ano)
                                )
                            ),
                        )
                    )
                ).all()
            )
            validadores = {r.url: r for r in (await s.scalars(select(RecursoRemoto))).all()}
        if not politico_por_sq:
            logger.warning("fotos tse {}: nenhuma candidatura carregada; rode tse_candidatos", ano)
            return 0

        async with HttpClient(max_calls_per_minute=30) as client:
            for uf in get_settings().tse_fotos_ufs:
                url = TSE_FOTOS_URL.format(ano=ano, uf=uf)
                v = validadores.get(url)
                headers = {}
                if v and v.etag:
                    headers["If-None-Match"] = v.etag
                if v and v.last_modified:
                    headers["If-Modified-Since"] = v.last_modified
                try:
                    r = await client.get(url, headers=headers)
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code in (403, 404):
                        logger.info("fotos tse {} {}: arquivo não existe", ano, uf)
                        continue
                    raise
                if r.status_code == 304:
                    logger.info("fotos tse {} {}: sem mudança", ano, uf)
                    continue

                coletadas, sem_cadastro, invalidas = [], 0, 0
                with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                    for nome in zf.namelist():
                        m = _ARQUIVO_TSE.match(nome.rsplit("/", 1)[-1])
                        if not m:
                            continue
                        sq = str(int(m.group(1)))
                        pid = politico_por_sq.get(sq)
                        if pid is None:
                            sem_cadastro += 1
                            continue
                        try:
                            imagem = store.save(zf.read(nome))
                        except ImagemInvalida:
                            invalidas += 1
                            continue
                        coletadas.append(
                            FotoColetada(
                                origem="tse",
                                id_externo=sq,
                                politico_id=pid,
                                ano=int(ano),
                                url_origem=f"{url}#{nome}",
                                imagem=imagem,
                                etag=None,
                            )
                        )
                async with sm() as s:
                    for start in range(0, len(coletadas), _LOTE):
                        await _gravar(s, coletadas[start : start + _LOTE])
                    await s.execute(
                        insert(RecursoRemoto)
                        .values(
                            url=url,
                            etag=r.headers.get("etag"),
                            last_modified=r.headers.get("last-modified"),
                        )
                        .on_conflict_do_update(
                            index_elements=[RecursoRemoto.url],
                            set_={
                                "etag": r.headers.get("etag"),
                                "last_modified": r.headers.get("last-modified"),
                                "processado_em": func.now(),
                            },
                        )
                    )
                    await s.commit()
                contador.registros += len(coletadas)
                logger.info(
                    "fotos tse {} {}: {} fotos, {} sem candidatura carregada, {} inválidas",
                    ano,
                    uf,
                    len(coletadas),
                    sem_cadastro,
                    invalidas,
                )

        async with sm() as s:
            await atualizar_fotos_principais(s)
            await s.commit()
    return contador.registros
