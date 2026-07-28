"""Strict application configuration and lazy client factories."""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from pydantic import SecretStr

_REQUIRED_ENV_NAMES = (
    "DEEPINFRA_API_TOKEN",
    "DEEPINFRA_MODEL",
    "DEEPINFRA_BASE_URL",
    "LANGSMITH_API_KEY",
    "LANGSMITH_PROJECT",
)


class ConfigurationError(RuntimeError):
    """Raised when startup configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class DeepInfraSettings:
    api_token: str
    model: str
    base_url: str


@dataclass(frozen=True, slots=True)
class LangSmithSettings:
    api_key: str
    project: str


@dataclass(frozen=True, slots=True)
class AppSettings:
    deepinfra: DeepInfraSettings
    langsmith: LangSmithSettings


def _validate_deepinfra_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.netloc != "api.deepinfra.com":
        raise ConfigurationError(
            "DEEPINFRA_BASE_URL must be an HTTPS URL hosted at api.deepinfra.com."
        )
    return value.rstrip("/")


def load_settings() -> AppSettings:
    """Load and validate the five required environment variables.

    There is no tracing toggle. DeepInfra and LangSmith configuration is always
    required, and no required value has a hidden fallback.
    """
    load_dotenv(override=False)
    values = {name: os.getenv(name, "").strip() for name in _REQUIRED_ENV_NAMES}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ConfigurationError(
            "Missing required environment variables: " + ", ".join(missing)
        )

    return AppSettings(
        deepinfra=DeepInfraSettings(
            api_token=values["DEEPINFRA_API_TOKEN"],
            model=values["DEEPINFRA_MODEL"],
            base_url=_validate_deepinfra_url(values["DEEPINFRA_BASE_URL"]),
        ),
        langsmith=LangSmithSettings(
            api_key=values["LANGSMITH_API_KEY"],
            project=values["LANGSMITH_PROJECT"],
        ),
    )


@contextmanager
def automatic_tracing_disabled():
    """Prevent framework auto-capture so only privacy-safe traces are emitted."""
    try:
        from langsmith import tracing_context
    except ModuleNotFoundError:
        yield
        return
    with tracing_context(enabled=False):
        yield


def build_chat_model(settings: AppSettings) -> Any:
    """Create the sole DeepInfra-backed LangChain chat model."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.deepinfra.model,
        api_key=SecretStr(settings.deepinfra.api_token),
        base_url=settings.deepinfra.base_url,
        temperature=0.0,
        timeout=60,
        max_retries=1,
    )


def build_langsmith_client(settings: AppSettings) -> Any:
    """Create the LangSmith client from required configuration."""
    from langsmith import Client

    return Client(api_key=settings.langsmith.api_key)
