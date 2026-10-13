"""Coleta de logos de partidos e escolha da logo principal.

Fontes:
- Wikidata: item com o número TSE do partido (P4251) e sua logo (P154), um arquivo do
  Wikimedia Commons. Baixada pelo thumbnail do Commons, que já rasteriza SVG em PNG (o
  MediaStore só aceita JPEG/PNG/WEBP). `url_origem` aponta para a página do arquivo no Commons,
  onde estão autoria e licença.
- Manual (CLI `ouroboros logo`): URL ou arquivo local. Tem prioridade sobre a do Wikidata.
  URL pode ser só guardada (servida direto da origem) em vez de baixada.

O TSE não serve logos fora do navegador (403), por isso o Wikidata. Número TSE é reaproveitado
quando um partido é extinto (25 era DEM, hoje é PRD), então o item só vale se a sigla ou o
nome do partido carregado batem com a sigla, o rótulo ou um alias do item; os aliases cobrem
partidos renomeados no mesmo item (PMN -> Mobiliza). Roda depois de `tse_candidatos`, que
carrega os partidos.
"""

import asyncio
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote

import httpx
from loguru import logger
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ouroboros.core.db import get_sessionmaker
from ouroboros.core.http import HttpClient
from ouroboros.core.media_store import Imagem, MediaStore, inspecionar
from ouroboros.core.text import normalize
from ouroboros.models.foto import PartidoLogo
from ouroboros.models.partido import Partido
from ouroboros.pipelines.runner import registrar_execucao

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
COMMONS_THUMB = "https://commons.wikimedia.org/wiki/Special:FilePath/{arquivo}?width={largura}"
COMMONS_PAGINA = "https://commons.wikimedia.org/wiki/File:{arquivo}"
LARGURA = 512
# Commons pede espaçamento educado; são poucas dezenas de arquivos
COMMONS_CHAMADAS_POR_MINUTO = 60

CONSULTA_WIKIDATA = """
SELECT ?item ?numero ?logo ?rank ?extinto
       (GROUP_CONCAT(DISTINCT ?sigla; separator="|") AS ?siglas)
       (GROUP_CONCAT(DISTINCT ?rotulo; separator="|") AS ?rotulos)
WHERE {
  ?item wdt:P4251 ?numero ; p:P154 ?st .
  ?st ps:P154 ?logo ; wikibase:rank ?rank .
  FILTER(?rank != wikibase:DeprecatedRank)
  OPTIONAL { ?item wdt:P576 ?extinto }
  OPTIONAL { ?item wdt:P1813 ?sigla }
  OPTIONAL {
    { ?item rdfs:label ?rotulo } UNION { ?item skos:altLabel ?rotulo }
    FILTER(LANG(?rotulo) IN ("pt", "pt-br"))
  }
}
GROUP BY ?item ?numero ?logo ?rank ?extinto
"""
_PREFERIDA = "http://wikiba.se/ontology#PreferredRank"
_NAO_ALFANUM = re.compile(r"[^a-z0-9]")


class PartidoNaoEncontrado(LookupError):
    pass


def _chave(texto: str) -> str:
    """'PC do B' e 'PCdoB', 'União Brasil' e 'UNIÃO BRASIL' viram a mesma chave."""
    return _NAO_ALFANUM.sub("", normalize(texto))


@dataclass(frozen=True)
class LogoWikidata:
    item: str  # Q...
    numero: int
    arquivo: str  # nome do arquivo no Commons
    preferida: bool
    extinto: bool
    nomes: frozenset[str]  # siglas, rótulo e aliases do item, já em `_chave`


@dataclass(frozen=True)
class PartidoAlvo:
    id: int
    numero_tse: int
    sigla: str
    nome: str


def ler_sparql(payload: dict) -> list[LogoWikidata]:
    logos = []
    for b in payload["results"]["bindings"]:
        numero = b["numero"]["value"].strip()
        if not numero.isdigit():
            continue
        nomes = "|".join(b[k]["value"] for k in ("siglas", "rotulos") if k in b)
        logos.append(
            LogoWikidata(
                item=b["item"]["value"].rsplit("/", 1)[-1],
                numero=int(numero),
                arquivo=unquote(b["logo"]["value"].rsplit("/", 1)[-1]),
                preferida=b["rank"]["value"] == _PREFERIDA,
                extinto="extinto" in b,
                nomes=frozenset(_chave(n) for n in nomes.split("|") if n),
            )
        )
    return logos


def escolher_logos(
    logos: Sequence[LogoWikidata], partidos: Sequence[PartidoAlvo]
) -> dict[int, LogoWikidata]:
    """Logo do Wikidata para cada partido (id -> logo). Partido sem item confiável fica de fora."""
    por_numero: dict[int, list[LogoWikidata]] = {}
    for logo in logos:
        por_numero.setdefault(logo.numero, []).append(logo)

    escolhidas = {}
    for p in partidos:
        candidatas = por_numero.get(p.numero_tse, [])
        nomes = {_chave(p.sigla), _chave(p.nome)}
        batem = [c for c in candidatas if c.nomes & nomes]
        if not batem:
            continue
        # item ativo antes de extinto; logo de rank preferido antes de normal; nome desempata
        escolhidas[p.id] = min(batem, key=lambda c: (c.extinto, not c.preferida, c.arquivo))
    return escolhidas


async def _gravar(
    session: AsyncSession,
    partido_id: int,
    origem: str,
    url_origem: str,
    imagem: Imagem | None,
    id_externo: str | None = None,
) -> None:
    arquivo = ("sha256", "extensao", "content_type", "tamanho_bytes", "largura", "altura")
    values = {
        "partido_id": partido_id,
        "origem": origem,
        "id_externo": id_externo,
        "url_origem": url_origem,
        **{c: getattr(imagem, c) if imagem else None for c in arquivo},
    }
    stmt = insert(PartidoLogo).values(values)
    await session.execute(
        stmt.on_conflict_do_update(
            constraint="uq_partido_logo_origem",
            set_={
                **{c: stmt.excluded[c] for c in values if c not in ("partido_id", "origem")},
                "obtida_em": func.now(),
            },
        )
    )


async def atualizar_logos_principais(session: AsyncSession) -> None:
    """Logo principal = manual, se houver; senão a coletada."""
    await session.execute(
        text(
            """
            UPDATE partido p SET logo_id = l.id
            FROM (
                SELECT DISTINCT ON (partido_id) partido_id, id
                FROM partido_logo
                ORDER BY partido_id, (origem = 'manual') DESC, id DESC
            ) l
            WHERE p.id = l.partido_id AND p.logo_id IS DISTINCT FROM l.id
            """
        )
    )


async def coletar_logos_wikidata(particao: str = "atual") -> int:
    """Logo (P154) do item Wikidata com o número TSE de cada partido carregado."""
    store = MediaStore()
    sm = get_sessionmaker()
    async with registrar_execucao("wikidata", "logos", particao) as contador:
        async with sm() as s:
            partidos = [
                PartidoAlvo(id=i, numero_tse=n, sigla=sg, nome=nm)
                for i, n, sg, nm in await s.execute(
                    select(Partido.id, Partido.numero_tse, Partido.sigla, Partido.nome).where(
                        Partido.numero_tse.is_not(None)
                    )
                )
            ]
            atuais = {
                lg.partido_id: lg
                for lg in await s.scalars(
                    select(PartidoLogo).where(PartidoLogo.origem == "wikidata")
                )
            }
        if not partidos:
            logger.warning("logos: nenhum partido carregado; rode tse_candidatos")
            return 0

        async with HttpClient(max_calls_per_minute=COMMONS_CHAMADAS_POR_MINUTO) as client:
            r = await client.get(
                WIKIDATA_SPARQL,
                params={"query": CONSULTA_WIKIDATA},
                headers={"Accept": "application/sparql-results+json"},
            )
            escolhidas = escolher_logos(ler_sparql(r.json()), partidos)

            baixadas: dict[int, tuple[LogoWikidata, str, Imagem]] = {}
            falhas = 0
            for partido_id, logo in escolhidas.items():
                pagina = COMMONS_PAGINA.format(arquivo=quote(logo.arquivo.replace(" ", "_")))
                atual = atuais.get(partido_id)
                if (
                    atual is not None
                    and atual.url_origem == pagina
                    and atual.armazenada
                    and store.path_for(atual.sha256, atual.extensao).exists()
                ):
                    continue  # mesmo arquivo do Commons já baixado
                url = COMMONS_THUMB.format(arquivo=quote(logo.arquivo), largura=LARGURA)
                try:
                    resp = await client.get(url)
                    imagem = store.save(resp.content)
                except (httpx.HTTPError, ValueError) as exc:
                    # falha pontual mantém a logo anterior; não apaga nada
                    logger.warning("logo {} ({}): {}", logo.item, logo.arquivo, exc)
                    falhas += 1
                    continue
                baixadas[partido_id] = (logo, pagina, imagem)

        async with sm() as s:
            for partido_id, (logo, pagina, imagem) in baixadas.items():
                await _gravar(s, partido_id, "wikidata", pagina, imagem, logo.item)
            sem_logo = [pid for pid in atuais if pid not in escolhidas]
            if sem_logo:  # item perdeu a logo ou deixou de bater com o partido
                await s.execute(
                    delete(PartidoLogo).where(
                        PartidoLogo.origem == "wikidata", PartidoLogo.partido_id.in_(sem_logo)
                    )
                )
            await atualizar_logos_principais(s)
            await s.commit()
        contador.registros = len(baixadas)
        logger.info(
            "logos: {} partidos, {} com logo no Wikidata, {} baixadas, {} falhas",
            len(partidos),
            len(escolhidas),
            len(baixadas),
            falhas,
        )
    return contador.registros


async def _partido(session: AsyncSession, chave: str) -> Partido:
    """Partido pelo número TSE ou pela sigla."""
    chave = chave.strip()
    if chave.isdigit():
        stmt = select(Partido).where(Partido.numero_tse == int(chave))
    else:
        stmt = select(Partido).where(func.upper(Partido.sigla) == chave.upper())
    partido = await session.scalar(stmt.order_by(Partido.ativo.desc(), Partido.id).limit(1))
    if partido is None:
        raise PartidoNaoEncontrado(f"partido não encontrado: {chave}")
    return partido


async def registrar_logo_manual(
    partido: str,
    *,
    url: str | None = None,
    arquivo: Path | None = None,
    baixar: bool = True,
) -> Imagem:
    """Logo manual de um partido (sigla ou número TSE), de uma URL ou de um arquivo local.

    Com `baixar=False` (só URL) a imagem é validada mas não guardada: a API redireciona para
    a URL. Arquivo local é sempre guardado. Substitui a logo manual anterior e passa a ser a
    principal.
    """
    if (url is None) == (arquivo is None):
        raise ValueError("informe url ou arquivo")
    if url is not None and not url.startswith(("https://", "http://")):
        raise ValueError("url precisa ser http(s)")
    if arquivo is not None:
        # só o nome: caminho local do servidor não sai na API
        dados = await asyncio.to_thread(arquivo.read_bytes)
        origem_url, baixar = f"arquivo:{arquivo.name}", True
    else:
        async with HttpClient() as client:
            dados, origem_url = (await client.get(url)).content, url
    imagem = MediaStore().save(dados) if baixar else inspecionar(dados)

    async with get_sessionmaker()() as s:
        p = await _partido(s, partido)
        await _gravar(s, p.id, "manual", origem_url, imagem if baixar else None)
        await atualizar_logos_principais(s)
        await s.commit()
    logger.info("logo manual de {} ({}x{})", p.sigla, imagem.largura, imagem.altura)
    return imagem


async def remover_logo_manual(partido: str) -> bool:
    """Apaga a logo manual; a coletada (se houver) volta a ser a principal."""
    async with get_sessionmaker()() as s:
        p = await _partido(s, partido)
        r = await s.execute(
            delete(PartidoLogo).where(
                PartidoLogo.partido_id == p.id, PartidoLogo.origem == "manual"
            )
        )
        await atualizar_logos_principais(s)
        await s.commit()
    return r.rowcount > 0
