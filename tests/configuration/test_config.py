from __future__ import annotations

import sys
import types

import pytest

from orchestrator.config import (
    ConfigurationError,
    build_chat_model,
    build_langsmith_client,
    load_settings,
)

ENV_NAMES = (
    "DEEPINFRA_API_TOKEN",
    "DEEPINFRA_MODEL",
    "DEEPINFRA_BASE_URL",
    "LANGSMITH_API_KEY",
    "LANGSMITH_PROJECT",
)


def clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Keep a developer's untracked .env file from influencing isolated tests.
    monkeypatch.setattr("orchestrator.config.load_dotenv", lambda **_: False)
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def set_complete_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPINFRA_API_TOKEN", "test-token")
    monkeypatch.setenv("DEEPINFRA_MODEL", "test/model")
    monkeypatch.setenv(
        "DEEPINFRA_BASE_URL", "https://api.deepinfra.com/v1/openai"
    )
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-langsmith-key")
    monkeypatch.setenv("LANGSMITH_PROJECT", "test-project")


def test_missing_required_variables_are_listed(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_env(monkeypatch)
    with pytest.raises(ConfigurationError) as exc_info:
        load_settings()
    message = str(exc_info.value)
    for name in ENV_NAMES:
        assert name in message


@pytest.mark.parametrize("missing_name", ENV_NAMES)
def test_every_environment_variable_is_required(
    monkeypatch: pytest.MonkeyPatch,
    missing_name: str,
) -> None:
    clear_env(monkeypatch)
    set_complete_env(monkeypatch)
    monkeypatch.delenv(missing_name)
    with pytest.raises(ConfigurationError, match=missing_name):
        load_settings()


def test_settings_contain_all_five_values(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_env(monkeypatch)
    set_complete_env(monkeypatch)
    settings = load_settings()
    assert settings.deepinfra.api_token == "test-token"
    assert settings.deepinfra.model == "test/model"
    assert settings.deepinfra.base_url == "https://api.deepinfra.com/v1/openai"
    assert settings.langsmith.api_key == "test-langsmith-key"
    assert settings.langsmith.project == "test-project"
    assert not hasattr(settings.langsmith, "tracing")


def test_model_factory_uses_env_values(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_env(monkeypatch)
    set_complete_env(monkeypatch)
    settings = load_settings()
    captured: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    fake_module = types.ModuleType("langchain_openai")
    fake_module.ChatOpenAI = FakeChatOpenAI
    monkeypatch.setitem(sys.modules, "langchain_openai", fake_module)
    build_chat_model(settings)

    assert captured["model"] == "test/model"
    assert captured["base_url"] == "https://api.deepinfra.com/v1/openai"
    assert captured["api_key"].get_secret_value() == "test-token"


def test_langsmith_factory_uses_required_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_env(monkeypatch)
    set_complete_env(monkeypatch)
    settings = load_settings()
    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    fake_module = types.ModuleType("langsmith")
    fake_module.Client = FakeClient
    monkeypatch.setitem(sys.modules, "langsmith", fake_module)
    build_langsmith_client(settings)
    assert captured == {"api_key": "test-langsmith-key"}
