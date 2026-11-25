"""Runtime settings read from app settings (environment variables). No secrets live here."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

PROVIDERS = ("openai", "language")


class ConfigError(ValueError):
    """Raised at start-up when a required or invalid setting is found."""


@dataclass(frozen=True)
class Settings:
    data_blob_url: str = ""
    classifier_provider: str = "language"
    openai_endpoint: str = ""
    openai_deployment: str = ""
    openai_api_version: str = "2025-04-01-preview"  # needed for reasoning_effort
    openai_reasoning_effort: str = ""
    language_endpoint: str = ""
    web_origin: str = ""
    max_attempts: int = 5

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        provider = env.get("CLASSIFIER_PROVIDER", "language").strip().lower()
        if provider not in PROVIDERS:
            raise ConfigError(f"CLASSIFIER_PROVIDER must be one of {PROVIDERS}, got {provider!r}")
        return cls(
            data_blob_url=env.get("DATA_BLOB_URL", ""),
            classifier_provider=provider,
            openai_endpoint=env.get("OPENAI_ENDPOINT", ""),
            openai_deployment=env.get("OPENAI_DEPLOYMENT", ""),
            openai_api_version=env.get("OPENAI_API_VERSION", cls.openai_api_version),
            openai_reasoning_effort=env.get("OPENAI_REASONING_EFFORT", "").strip().lower(),
            language_endpoint=env.get("LANGUAGE_ENDPOINT", ""),
            web_origin=env.get("WEB_ORIGIN", ""),
        )

    def require(self, *names: str) -> None:
        missing = [n for n in names if not getattr(self, n)]
        if missing:
            raise ConfigError(f"missing settings: {', '.join(missing)}")
