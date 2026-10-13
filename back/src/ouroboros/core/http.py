import asyncio
import time
from types import TracebackType
from typing import Any, Self

import httpx
from loguru import logger
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from ouroboros.core.settings import get_settings

RETRY_STATUS = {429, 500, 502, 503, 504}


class RateLimiter:
    """Limita a N requisições por período, espaçando chamadas uniformemente."""

    def __init__(self, max_calls: int, period: float = 60.0) -> None:
        self._interval = period / max_calls
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._next - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = time.monotonic()
            self._next = max(now, self._next) + self._interval


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRY_STATUS
    return isinstance(exc, httpx.TransportError)


class HttpClient:
    """Cliente base dos conectores: rate limit por fonte + retry com backoff em 429/5xx/rede."""

    def __init__(
        self,
        base_url: str = "",
        *,
        max_calls_per_minute: int | None = None,
        headers: dict[str, str] | None = None,
        attempts: int = 5,
        backoff_initial: float = 1.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=settings.http_timeout,
            headers={"User-Agent": settings.http_user_agent, **(headers or {})},
            follow_redirects=True,
            transport=transport,
        )
        self._limiter = RateLimiter(max_calls_per_minute) if max_calls_per_minute else None
        self._attempts = attempts
        self._backoff_initial = backoff_initial

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception(_is_retryable),
            stop=stop_after_attempt(self._attempts),
            wait=wait_exponential_jitter(
                multiplier=self._backoff_initial, max=60, jitter=self._backoff_initial
            ),
            reraise=True,
        ):
            with attempt:
                if self._limiter:
                    await self._limiter.acquire()
                response = await self._client.request(method, url, **kwargs)
                if response.status_code == 304:  # GET condicional: nada mudou
                    return response
                if response.status_code in RETRY_STATUS:
                    logger.warning(
                        "{} {} -> {}, tentando de novo", method, url, response.status_code
                    )
                response.raise_for_status()
                return response
        raise AssertionError("unreachable")

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()
