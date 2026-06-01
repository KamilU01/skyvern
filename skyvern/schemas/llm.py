from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict, cast

__all__ = [
    "LiteLLMParams",
    "LLMAllowedFailsPolicy",
    "LLMConfig",
    "LLMConfigBase",
    "LLMRouterConfig",
    "LLMRouterModelConfig",
]

_SETTINGS_DEFAULT = object()
# Sentinel replaced in __post_init__; distinct from callers explicitly passing None.
_DEFAULT_MAX_TOKENS = cast("int | None", _SETTINGS_DEFAULT)
_DEFAULT_TEMPERATURE = cast("float | None", _SETTINGS_DEFAULT)
_DEFAULT_TOP_P = cast("float | None", _SETTINGS_DEFAULT)
_DEFAULT_TOP_K = cast("int | None", _SETTINGS_DEFAULT)
_DEFAULT_MIN_P = cast("float | None", _SETTINGS_DEFAULT)
_DEFAULT_PRESENCE_PENALTY = cast("float | None", _SETTINGS_DEFAULT)
_DEFAULT_REPETITION_PENALTY = cast("float | None", _SETTINGS_DEFAULT)

# Maps each settings-default config field to the Settings attribute it resolves from.
_GENERATION_SETTING_BY_FIELD = {
    "max_tokens": "LLM_CONFIG_MAX_TOKENS",
    "temperature": "LLM_CONFIG_TEMPERATURE",
    "top_p": "LLM_CONFIG_TOP_P",
    "top_k": "LLM_CONFIG_TOP_K",
    "min_p": "LLM_CONFIG_MIN_P",
    "presence_penalty": "LLM_CONFIG_PRESENCE_PENALTY",
    "repetition_penalty": "LLM_CONFIG_REPETITION_PENALTY",
}


def _assert_settings_defaults_resolved(*values: object) -> None:
    if any(value is _SETTINGS_DEFAULT for value in values):
        raise RuntimeError("settings default sentinel was not resolved")


def _resolve_generation_defaults(config: object) -> None:
    """Replace any unresolved settings-default sentinels with their Settings values.

    Fields default to a private sentinel so callers can still pass None explicitly. Only the
    fields a config actually declares are considered; absent fields are skipped. Settings are
    read lazily and only when at least one sentinel needs resolving.
    """
    settings = None
    for field_name, setting_name in _GENERATION_SETTING_BY_FIELD.items():
        if getattr(config, field_name, None) is _SETTINGS_DEFAULT:
            if settings is None:
                settings = _settings()
            object.__setattr__(config, field_name, getattr(settings, setting_name))

    _assert_settings_defaults_resolved(
        *(getattr(config, field_name) for field_name in _GENERATION_SETTING_BY_FIELD if hasattr(config, field_name))
    )


class LiteLLMParams(TypedDict, total=False):
    api_key: str | None
    api_version: str | None
    api_base: str | None
    model_info: dict[str, Any] | None
    vertex_credentials: str | None
    vertex_location: str | None
    thinking: dict[str, Any] | None
    thinking_level: str | None
    service_tier: str | None
    extra_headers: dict[str, str] | None
    timeout: float | None


def _settings() -> Any:
    # Keep settings resolution lazy so importing skyvern.schemas.llm only defines the
    # public dataclasses; config defaults are read when a config is constructed.
    from skyvern.settings_manager import SettingsManager  # noqa: PLC0415

    return SettingsManager.get_settings()


@dataclass(frozen=True)
class LLMConfigBase:
    model_name: str
    required_env_vars: list[str]
    supports_vision: bool
    add_assistant_prefix: bool

    def get_missing_env_vars(self) -> list[str]:
        settings = _settings()
        missing_env_vars = []
        for env_var in self.required_env_vars:
            env_var_value = getattr(settings, env_var, None)
            if not env_var_value:
                missing_env_vars.append(env_var)

        return missing_env_vars


@dataclass(frozen=True)
class LLMConfig(LLMConfigBase):
    """Base-safe LLM config shared by SDK and server import paths.

    Default max-token and temperature fields use a private sentinel so callers can
    still pass None explicitly. __post_init__ must replace the sentinel before the
    frozen dataclass instance is observable.
    """

    litellm_params: LiteLLMParams | None = field(default=None)
    max_tokens: int | None = _DEFAULT_MAX_TOKENS
    max_completion_tokens: int | None = None
    temperature: float | None = _DEFAULT_TEMPERATURE
    top_p: float | None = _DEFAULT_TOP_P
    top_k: int | None = _DEFAULT_TOP_K
    min_p: float | None = _DEFAULT_MIN_P
    presence_penalty: float | None = _DEFAULT_PRESENCE_PENALTY
    repetition_penalty: float | None = _DEFAULT_REPETITION_PENALTY
    reasoning_effort: str | None = None

    def __post_init__(self) -> None:
        _resolve_generation_defaults(self)


@dataclass(frozen=True)
class LLMAllowedFailsPolicy:
    bad_request_error_allowed_fails: int | None = None
    authentication_error_allowed_fails: int | None = None
    timeout_error_allowed_fails: int | None = None
    rate_limit_error_allowed_fails: int | None = None
    content_policy_violation_error_allowed_fails: int | None = None
    internal_server_error_allowed_fails: int | None = None


@dataclass(frozen=True)
class LLMRouterModelConfig:
    model_name: str
    # https://litellm.vercel.app/docs/routing
    litellm_params: dict[str, Any]
    model_info: dict[str, Any] = field(default_factory=dict)
    tpm: int | None = None
    rpm: int | None = None


@dataclass(frozen=True)
class LLMRouterConfig(LLMConfigBase):
    """Base-safe router config with the same settings-default sentinel invariant as LLMConfig."""

    model_list: list[LLMRouterModelConfig]
    # All three redis parameters are required. Even if there isn't a password, it should be an empty string.
    main_model_group: str
    redis_host: str | None = None
    redis_port: int | None = None
    redis_password: str | None = None
    fallback_model_group: str | list[str] | None = None
    routing_strategy: Literal[
        "simple-shuffle",
        "least-busy",
        "usage-based-routing",
        "usage-based-routing-v2",
        "latency-based-routing",
    ] = "usage-based-routing"
    num_retries: int = 1
    retry_delay_seconds: int = 15
    set_verbose: bool = False
    disable_cooldowns: bool | None = None
    allowed_fails: int | None = None
    allowed_fails_policy: LLMAllowedFailsPolicy | None = None
    cooldown_time: float | None = None
    max_tokens: int | None = _DEFAULT_MAX_TOKENS
    max_completion_tokens: int | None = None
    reasoning_effort: str | None = None
    temperature: float | None = _DEFAULT_TEMPERATURE
    top_p: float | None = _DEFAULT_TOP_P
    top_k: int | None = _DEFAULT_TOP_K
    min_p: float | None = _DEFAULT_MIN_P
    presence_penalty: float | None = _DEFAULT_PRESENCE_PENALTY
    repetition_penalty: float | None = _DEFAULT_REPETITION_PENALTY

    def __post_init__(self) -> None:
        _resolve_generation_defaults(self)
