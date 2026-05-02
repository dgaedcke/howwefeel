"""Test fixtures for the Tribes persistence layer.

* `es_container` (session) — boots a single ephemeral ES 8 Docker container
  for the entire test run.
* `es_url` (session) — the http URL of the running container.
* `es_config` (function) — a fresh `ESConfig` whose `es_index_prefix`
  is unique per test, so concurrent tests do not collide.
* `es_client` (function) — an `AsyncElasticsearch` connected to the
  container; closed at end of test.
* `clean_indices` (function) — calls `ensure_indices` so the V1 indices
  exist at canonical names. Tests that mutate the lifecycle (e.g.
  T-MAP-103) request `es_client` + `es_config` directly and skip this.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from elasticsearch import AsyncElasticsearch


def _ensure_docker_host_env() -> None:
    """Make `docker-py` (and therefore `testcontainers`) find Docker Desktop.

    Docker Desktop on macOS exposes the daemon at
    ``$HOME/.docker/run/docker.sock`` via a CLI context, but the docker SDK
    only reads ``DOCKER_HOST`` / ``/var/run/docker.sock``. We set it here so
    tests don't depend on the user's shell env.
    """
    if os.environ.get("DOCKER_HOST"):
        return
    desktop_sock = Path.home() / ".docker" / "run" / "docker.sock"
    if desktop_sock.exists():
        os.environ["DOCKER_HOST"] = f"unix://{desktop_sock}"


_ensure_docker_host_env()

from testcontainers.elasticsearch import ElasticSearchContainer  # noqa: E402

from app.repositories.es import client as es_client_module  # noqa: E402
from app.repositories.es.config import ESConfig  # noqa: E402
from app.repositories.es.indices.manager import ensure_indices, registered_indices  # noqa: E402

ES_IMAGE = os.environ.get(
    "TRIBES_TEST_ES_IMAGE",
    "docker.elastic.co/elasticsearch/elasticsearch:8.13.0",
)


@pytest.fixture(scope="session")
def es_container() -> Iterator[ElasticSearchContainer]:
    """Boot an ephemeral single-node ES 8 container for the test session."""
    container = (
        ElasticSearchContainer(ES_IMAGE)
        .with_env("discovery.type", "single-node")
        .with_env("ES_JAVA_OPTS", "-Xms512m -Xmx512m")
    )
    container.start()
    try:
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def es_url(es_container: ElasticSearchContainer) -> str:
    host = es_container.get_container_host_ip()
    port = es_container.get_exposed_port(es_container.port)
    return f"http://{host}:{port}"


@pytest.fixture()
def es_config(es_url: str, monkeypatch: pytest.MonkeyPatch) -> ESConfig:
    """Per-test config with a unique index prefix.

    Setting the env vars (rather than constructing `ESConfig` directly)
    proves that the env-driven contract from spec §6 actually works.
    """
    prefix = f"test_{uuid.uuid4().hex[:12]}"
    monkeypatch.setenv("TRIBES_ES_URL", es_url)
    monkeypatch.delenv("TRIBES_ES_API_KEY", raising=False)
    monkeypatch.setenv("TRIBES_ES_INDEX_PREFIX", prefix)
    es_client_module.get_es_client.cache_clear()
    return ESConfig()


@pytest_asyncio.fixture()
async def es_client(es_url: str) -> AsyncIterator[AsyncElasticsearch]:
    client = AsyncElasticsearch(hosts=[es_url], request_timeout=10)
    try:
        yield client
    finally:
        await client.close()


@pytest_asyncio.fixture()
async def clean_indices(
    es_client: AsyncElasticsearch,
    es_config: ESConfig,
) -> AsyncIterator[ESConfig]:
    """Provision the registered indices fresh and tear them down after."""
    await _delete_registered_indices(es_client, es_config)
    await ensure_indices(es_client, es_config)
    try:
        yield es_config
    finally:
        await _delete_registered_indices(es_client, es_config)


async def _delete_registered_indices(
    client: AsyncElasticsearch,
    config: ESConfig,
) -> None:
    for index_name, _ in registered_indices(config):
        await client.indices.delete(index=index_name, ignore_unavailable=True)
