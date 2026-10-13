"""Coleta de fotos de políticos e escolha da foto principal.

Fontes:
- Câmara: https://www.camara.leg.br/internet/deputado/bandep/{id}.jpg
- Senado: https://www.senado.leg.br/senadores/img/fotos-oficiais/senador{codigo}.jpg
- TSE: um ZIP por UF e eleição com a foto de todo candidato, arquivo `[F]{UF}{SQ}_div.jpg`

Câmara e Senado servem a imagem por URL estável: guardamos só a URL (um HEAD confirma que
existe) e o front carrega direto da fonte. O TSE não tem link individual utilizável (o
DivulgaCandContas responde 403 fora do navegador), então as fotos de candidatos são extraídas
do ZIP oficial e servidas por esta API. ZIP sem mudança (ETag) não é baixado de novo.

As fotos são ligadas pelos identificadores que a resolução de identidade já gravou
(id Câmara, código Senado, SQ_CANDIDATO), então estes jobs rodam depois das cargas de pessoas.
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
from sqlalchemy import String, and_, cast, delete, func, select
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
# CDN do TSE: arquivos grandes, poucas requisições; espaçamento educado
TSE_CHAMADAS_POR_MINUTO = 30


@dataclass(frozen=True)
class FotoColetada:
    origem: str
    id_externo: str
    politico_id: int
    ano: int | None
    url_origem: str
    imagem: Imagem | None = None  # None: só URL, arquivo não baixado


async def _gravar(session: AsyncSession, fotos: Sequence[FotoColetada]) -> None:
    if not fotos:
        return
    arquivo = ("sha256", "extensao", "content_type", "tamanho_bytes", "largura", "altura")
    values = [
        {
            "origem": f.origem,
            "id_externo": f.id_externo,
            "politico_id": f.politico_id,
            "ano": f.ano,
            "url_origem": f.url_origem,
            **{c: getattr(f.imagem, c) if f.imagem else None for c in arquivo},
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
    """URL da foto oficial de quem tem identificador na casa (`camara` ou `senado`).

    Não baixa a imagem: um HEAD confirma que a URL responde com uma imagem.
    """
    url_tpl = FOTO_CASA_URL[origem]
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

        ano_atual = date.today().year
        validas: list[FotoColetada] = []
        sem_foto: list[str] = []
        sem = asyncio.Semaphore(_CONCORRENCIA)

        async def checar(client: HttpClient, id_externo: str, pid: int, fim: date | None) -> None:
            url = url_tpl.format(id=id_externo)
            async with sem:
                try:
                    r = await client.request("HEAD", url)
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code in (403, 404):
                        sem_foto.append(id_externo)
                        return
                    raise
            if not r.headers.get("content-type", "").startswith("image/"):
                sem_foto.append(id_externo)
                return
            validas.append(
                FotoColetada(
                    origem=origem,
                    id_externo=id_externo,
                    politico_id=pid,
                    ano=min(fim.year, ano_atual) if fim else None,
                    url_origem=str(r.url),  # já depois de redirects (http -> https)
                )
            )

        async with HttpClient(max_calls_per_minute=600) as client:
            await asyncio.gather(*(checar(client, *a) for a in alvos))

        async with sm() as s:
            for start in range(0, len(validas), _LOTE):
                await _gravar(s, validas[start : start + _LOTE])
            if sem_foto:  # foto que sumiu da fonte deixa de ser oferecida
                await s.execute(
                    delete(PoliticoFoto).where(
                        PoliticoFoto.origem == origem, PoliticoFoto.id_externo.in_(sem_foto)
                    )
                )
            await atualizar_fotos_principais(s)
            await s.commit()
        contador.registros = len(validas)
        logger.info(
            "fotos {}: {} alvos, {} com foto, {} sem foto",
            origem,
            len(alvos),
            len(validas),
            len(sem_foto),
        )
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

        async with HttpClient(max_calls_per_minute=TSE_CHAMADAS_POR_MINUTO) as client:
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
