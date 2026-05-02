"""Environment-driven configuration for the Tribes persistence layer.

All ES connection settings and index names are derived from a single Pydantic
settings object. Tests override `es_index_prefix` (per session) to isolate
indices on a shared cluster.

Per `01-foundation-spec.md` §6.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ESConfig(BaseSettings):
    """Settings for the Elasticsearch persistence layer.

    Environment variables use the `TRIBES_` prefix (uppercased field names).
    See `01-foundation-spec.md` §6 for the full env-var contract.
    """

    model_config = SettingsConfigDict(
        env_prefix="TRIBES_",
        case_sensitive=False,
        extra="ignore",
    )

    es_url: str
    es_api_key: str | None = None
    es_index_prefix: str = "tribes"

    @property
    def contacts_index(self) -> str:
        return f"{self.es_index_prefix}_contacts"

    @property
    def bins_index(self) -> str:
        return f"{self.es_index_prefix}_bins"

    @property
    def assignments_index(self) -> str:
        return f"{self.es_index_prefix}_assignments"

    @property
    def tribes_index(self) -> str:
        return f"{self.es_index_prefix}_tribes"

    @property
    def pending_jobs_index(self) -> str:
        return f"{self.es_index_prefix}_pending_jobs"


__all__ = ["ESConfig"]
