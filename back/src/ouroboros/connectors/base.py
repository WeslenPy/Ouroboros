from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import ClassVar

from httpx import Response
from pydantic import BaseModel

from ouroboros.core.http import HttpClient
from ouroboros.core.raw_store import RawRecord


class Connector(ABC):
    """Contrato de toda fonte de dados.

    - `extract(particao)` baixa da fonte e devolve registros brutos (sem interpretar).
    - `transform(records)` é pura: todos os brutos da partição -> linhas canônicas.
      Recebe a partição inteira porque várias fontes exigem juntar arquivos
      (ex.: lista de deputados da legislatura + CSV com nome civil e nascimento).

    Novas fontes (ALE de um estado, TCE, câmara municipal) entram implementando esta classe.
    """

    fonte: ClassVar[str]
    recurso: ClassVar[str]

    @abstractmethod
    def extract(self, particao: str) -> AsyncIterator[RawRecord]: ...

    @abstractmethod
    def transform(self, records: Sequence[RawRecord]) -> Sequence[BaseModel]: ...


class HttpConnector(Connector):
    """Conector que fala HTTP. Aceita cliente injetado (testes) ou cria o seu com rate limit."""

    base_url: ClassVar[str] = ""
    max_calls_per_minute: ClassVar[int | None] = None
    headers: ClassVar[dict[str, str]] = {}

    def __init__(self, client: HttpClient | None = None) -> None:
        self._client = client

    @asynccontextmanager
    async def http(self) -> AsyncIterator[HttpClient]:
        if self._client is not None:
            yield self._client
            return
        async with HttpClient(
            self.base_url, max_calls_per_minute=self.max_calls_per_minute, headers=self.headers
        ) as client:
            yield client

    def raw(
        self, recurso: str, particao: str, response: Response, content_type: str | None = None
    ) -> RawRecord:
        """Embrulha a resposta como veio. `content_type` força o tipo quando a fonte manda
        `application/octet-stream` para CSV/ZIP."""
        return RawRecord(
            fonte=self.fonte,
            recurso=recurso,
            particao=particao,
            url=str(response.url),
            payload=response.content,
            content_type=content_type
            or response.headers.get("content-type", "application/octet-stream"),
        )
