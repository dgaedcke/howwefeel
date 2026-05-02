"""AsyncElasticsearch singleton factory.

`get_es_client()` returns a process-wide singleton wired with the
production retry/timeout settings from `01-foundation-spec.md` §6.
The singleton survives for the life of the process; FastAPI lifespan
calls `close_es_client()` on shutdown to release the underlying
connection pool.
"""

from __future__ import annotations

from functools import lru_cache

from elasticsearch import AsyncElasticsearch

from .config import ESConfig


@lru_cache(maxsize=1)
def get_es_client() -> AsyncElasticsearch:
    """Return the singleton `AsyncElasticsearch` instance.

    Cached via `lru_cache` so every caller in the process shares one
    connection pool. Configuration is loaded once from the environment.
    """
    config = ESConfig()
    return AsyncElasticsearch(
        hosts=[config.es_url],
        api_key=config.es_api_key,
        retry_on_timeout=True,
        max_retries=3,
        request_timeout=10,
        sniff_on_start=False,
    )


async def close_es_client() -> None:
    """Close the cached client (if any) and reset the cache.

    Used by the FastAPI lifespan shutdown hook and by tests that need
    to swap connection settings between cases.
    """
    if get_es_client.cache_info().currsize:
        existing = get_es_client()
        await existing.close()
    get_es_client.cache_clear()


__all__ = ["get_es_client", "close_es_client"]
