from __future__ import annotations

import pytest

from skyvern.forge.sdk.api.llm.api_handler_factory import LLMAPIHandlerFactory
from skyvern.schemas.llm import LLMConfig
from skyvern.settings_manager import SettingsManager

_GENERATION_KEYS = ("top_p", "top_k", "min_p", "presence_penalty", "repetition_penalty")


def _make_config(**overrides: object) -> LLMConfig:
    return LLMConfig(
        model_name="gpt-4o",
        required_env_vars=[],
        supports_vision=True,
        add_assistant_prefix=False,
        **overrides,  # type: ignore[arg-type]
    )


def test_generation_params_forwarded_when_set() -> None:
    config = _make_config(top_p=0.9, top_k=40, min_p=0.05, presence_penalty=0.5, repetition_penalty=1.1)
    params = LLMAPIHandlerFactory.get_api_parameters(config)
    assert params["top_p"] == 0.9
    assert params["top_k"] == 40
    assert params["min_p"] == 0.05
    assert params["presence_penalty"] == 0.5
    assert params["repetition_penalty"] == 1.1


def test_generation_params_omitted_when_none(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SettingsManager.get_settings()
    for key in _GENERATION_KEYS:
        monkeypatch.setattr(settings, f"LLM_CONFIG_{key.upper()}", None, raising=False)

    config = _make_config()
    params = LLMAPIHandlerFactory.get_api_parameters(config)
    for key in _GENERATION_KEYS:
        assert key not in params


def test_generation_params_resolve_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SettingsManager.get_settings()
    monkeypatch.setattr(settings, "LLM_CONFIG_TOP_P", 0.7, raising=False)
    monkeypatch.setattr(settings, "LLM_CONFIG_PRESENCE_PENALTY", 0.3, raising=False)

    config = _make_config()
    assert config.top_p == 0.7
    assert config.presence_penalty == 0.3

    params = LLMAPIHandlerFactory.get_api_parameters(config)
    assert params["top_p"] == 0.7
    assert params["presence_penalty"] == 0.3


def test_explicit_none_overrides_settings_default(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SettingsManager.get_settings()
    monkeypatch.setattr(settings, "LLM_CONFIG_TOP_P", 0.7, raising=False)

    # Passing None explicitly must win over the settings default (sentinel is bypassed).
    config = _make_config(top_p=None)
    assert config.top_p is None
    params = LLMAPIHandlerFactory.get_api_parameters(config)
    assert "top_p" not in params
