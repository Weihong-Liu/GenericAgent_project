"""Configuration and environment resolution for the engineered GenericAgent."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config_loader import extract_runtime_config, load_config_file

DEFAULT_PROVIDER = "openai"
DEFAULT_MODEL = "gpt-5.4"
DEFAULT_LANGUAGE = "zh"
CONFIG_DIR_ENV_NAMES = (
    "GENERIC_AGENT_CONFIG_DIR",
    "GA_CONFIG_DIR",
    "GENERIC_AGENT_HOME",
    "CLAUDE_CONFIG_DIR",
)
PROJECT_CONFIG_PATHS = (
    Path(".generic-agent") / "settings.json",
    Path(".generic-agent.json"),
    Path(".generic-agent.yaml"),
    Path(".generic-agent.yml"),
)
USER_CONFIG_NAMES = ("settings.json", "config.json", "config.yaml", "config.yml")
PROJECT_CONFIG_PATH = PROJECT_CONFIG_PATHS[0]
USER_CONFIG_NAME = USER_CONFIG_NAMES[0]
ENV_CONFIG_JSON_NAMES = ("GA_CONFIG_JSON", "GENERIC_AGENT_CONFIG_JSON")
AGENT_HOME_DIR_NAMES = (
    "agents",
    "backups",
    "cache",
    "debug",
    "downloads",
    "file-history",
    "ide",
    "paste-cache",
    "plans",
    "plugins",
    "projects",
    "session-env",
    "sessions",
    "shell-snapshots",
    "skills",
    "state",
    "statsig",
    "tasks",
    "teams",
    "telemetry",
    "todos",
    "transcripts",
)
AGENT_HOME_FILE_DEFAULTS = {
    "config.json": "{}\n",
    "history.jsonl": "",
    "settings.json": "{}\n",
    "stats-cache.json": "{}\n",
}
AGENT_HOME_RESERVED_FILE_NAMES = (
    "settings.json.bak",
    "settings.json.orig",
)
PROXY_ENV_NAMES = (
    "HTTPS_PROXY",
    "https_proxy",
    "HTTP_PROXY",
    "http_proxy",
    "ALL_PROXY",
    "all_proxy",
)
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off", ""}
_MISSING = object()


def _default_agent_home() -> Path:
    return Path.home() / ".generic-agent"


def get_agent_home(env: Mapping[str, str] | None = None) -> Path:
    """Return the writable home directory for engineered GenericAgent state."""
    env_map = os.environ if env is None else env
    override = _config_dir_from_env(env_map)
    if override:
        return override

    json_home = _json_env_overrides(env_map).home
    return json_home if json_home is not None else _default_agent_home()


def get_agent_home_env_name(env: Mapping[str, str] | None = None) -> str | None:
    """Return the env var currently selecting the config home, if any."""
    env_map = os.environ if env is None else env
    for name in CONFIG_DIR_ENV_NAMES:
        if _optional_str(env_map.get(name)) is not None:
            return name
    return None


def get_user_config_path(env: Mapping[str, str] | None = None) -> Path:
    """Return the user-level config file path."""
    return get_agent_home(env) / USER_CONFIG_NAME


def get_agent_home_layout(home: Path | None = None) -> AgentHomeLayout:
    """Return the free-code-style home layout for a GenericAgent config dir."""
    return AgentHomeLayout.from_home(_default_agent_home() if home is None else home)


def get_project_config_path(cwd: Path | None = None) -> Path:
    """Return the nearest project config path candidate for the current workspace."""
    found = find_project_config_path(cwd)
    if found is not None:
        return found
    return _search_base(cwd) / PROJECT_CONFIG_PATH


def find_project_config_path(cwd: Path | None = None) -> Path | None:
    """Find the nearest project-local config by walking from cwd to filesystem root."""
    base = _search_base(cwd)
    for directory in (base, *base.parents):
        for config_path in PROJECT_CONFIG_PATHS:
            candidate = directory / config_path
            if candidate.exists():
                return candidate
    return None


def parse_bool(value: Any, *, name: str = "value") -> bool:
    """Parse a config or environment boolean with explicit failure on ambiguity."""
    if isinstance(value, bool):
        return value
    if value is None:
        raise ValueError(f"{name} cannot be parsed as a boolean")
    normalized = str(value).strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"{name} must be one of true/false/1/0/yes/no/on/off")


def _env_bool(name: str, default: bool = False, env: Mapping[str, str] | None = None) -> bool:
    env_map = os.environ if env is None else env
    value = env_map.get(name)
    if value is None:
        return default
    return parse_bool(value, name=name)


@dataclass(frozen=True)
class ConfigOverrides:
    """Optional settings from one configuration layer."""

    home: Path | None = None
    default_provider: str | None = None
    default_model: str | None = None
    language: str | None = None
    verbose: bool | None = None
    yolo: bool | None = None
    proxy: str | None = None
    environment: dict[str, str] | None = None

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> ConfigOverrides:
        return cls(
            home=_optional_path(
                _pick(
                    values,
                    "home",
                    "agent_home",
                    "generic_agent_home",
                    "config_dir",
                    "generic_agent_config_dir",
                )
            ),
            default_provider=_optional_str(_pick(values, "default_provider", "provider")),
            default_model=_optional_str(_pick(values, "default_model", "model")),
            language=_optional_str(_pick(values, "language", "lang")),
            verbose=_optional_bool(_pick(values, "verbose"), "verbose"),
            yolo=_optional_bool(_pick(values, "yolo", "auto_approve"), "yolo"),
            proxy=_optional_str(_pick(values, "proxy", "https_proxy", "http_proxy", "all_proxy")),
            environment=_optional_environment(_pick(values, "environment", "env")),
        )

    @classmethod
    def coerce(
        cls,
        value: ConfigOverrides | Mapping[str, Any] | object | None,
    ) -> ConfigOverrides:
        if value is None:
            return cls()
        if isinstance(value, ConfigOverrides):
            return value
        if isinstance(value, Mapping):
            return cls.from_mapping(value)

        extracted: dict[str, Any] = {}
        for key in (
            "home",
            "agent_home",
            "generic_agent_home",
            "config_dir",
            "generic_agent_config_dir",
            "default_provider",
            "provider",
            "default_model",
            "model",
            "language",
            "lang",
            "verbose",
            "yolo",
            "auto_approve",
            "proxy",
            "environment",
            "env",
        ):
            if hasattr(value, key):
                extracted[key] = getattr(value, key)
        return cls.from_mapping(extracted)


@dataclass(frozen=True)
class RuntimeSettings:
    """Runtime settings resolved from defaults, config files, env, and CLI overrides."""

    home: Path = field(default_factory=_default_agent_home)
    default_provider: str = DEFAULT_PROVIDER
    default_model: str = DEFAULT_MODEL
    language: str = DEFAULT_LANGUAGE
    verbose: bool = False
    yolo: bool = False
    proxy: str | None = None
    environment: dict[str, str] = field(default_factory=dict)

    @property
    def layout(self) -> AgentHomeLayout:
        return get_agent_home_layout(self.home)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> RuntimeSettings:
        """Resolve settings from defaults plus environment only."""
        return _apply_overrides(cls(), _env_overrides(os.environ if env is None else env))

    @property
    def state_dir(self) -> Path:
        return self.home / "state"

    @property
    def auth_path(self) -> Path:
        return self.home / "auth.json"

    @property
    def approvals_path(self) -> Path:
        return self.home / "approvals.json"

    @property
    def settings_path(self) -> Path:
        return self.home / "settings.json"

    @property
    def config_path(self) -> Path:
        return self.home / "config.json"

    @property
    def history_path(self) -> Path:
        return self.home / "history.jsonl"

    @property
    def stats_cache_path(self) -> Path:
        return self.home / "stats-cache.json"

    def home_dir(self, name: str) -> Path:
        """Return a named directory in the standard GenericAgent home layout."""
        return self.layout.directory(name)

    def home_file(self, name: str) -> Path:
        """Return a named file in the standard GenericAgent home layout."""
        return self.layout.file(name)

    def ensure_home_layout(self, *, create_files: bool = True) -> AgentHomeLayout:
        """Create the standard GenericAgent home directories and baseline files."""
        return self.layout.ensure(create_files=create_files)


@dataclass(frozen=True)
class AgentHomeLayout:
    """Standard ``~/.generic-agent`` layout modelled after free-code ``~/.claude``."""

    home: Path
    directories: dict[str, Path]
    files: dict[str, Path]
    reserved_files: dict[str, Path]

    @classmethod
    def from_home(cls, home: Path) -> AgentHomeLayout:
        resolved_home = Path(home).expanduser()
        return cls(
            home=resolved_home,
            directories={name: resolved_home / name for name in AGENT_HOME_DIR_NAMES},
            files={name: resolved_home / name for name in AGENT_HOME_FILE_DEFAULTS},
            reserved_files={
                name: resolved_home / name for name in AGENT_HOME_RESERVED_FILE_NAMES
            },
        )

    def directory(self, name: str) -> Path:
        try:
            return self.directories[name]
        except KeyError as exc:
            raise KeyError(f"unknown GenericAgent home directory: {name}") from exc

    def file(self, name: str) -> Path:
        if name in self.files:
            return self.files[name]
        if name in self.reserved_files:
            return self.reserved_files[name]
        raise KeyError(f"unknown GenericAgent home file: {name}")

    def ensure(self, *, create_files: bool = True) -> AgentHomeLayout:
        self.home.mkdir(parents=True, exist_ok=True)
        for directory in self.directories.values():
            directory.mkdir(parents=True, exist_ok=True)
        if create_files:
            for filename, default_content in AGENT_HOME_FILE_DEFAULTS.items():
                path = self.home / filename
                if not path.exists():
                    path.write_text(default_content, encoding="utf-8")
        return self


def resolve_runtime_settings(
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    cli_overrides: ConfigOverrides | Mapping[str, Any] | object | None = None,
) -> RuntimeSettings:
    """Resolve settings by precedence: CLI > env > project config > user config > defaults."""
    env_map = os.environ if env is None else env
    settings = RuntimeSettings()

    user_config = find_user_config_path(env_map)
    if user_config is not None:
        settings = _apply_overrides(settings, _file_overrides(user_config))

    project_config = find_project_config_path(cwd)
    if project_config is not None:
        settings = _apply_overrides(settings, _file_overrides(project_config))

    settings = _apply_overrides(settings, _env_overrides(env_map))
    return _apply_overrides(settings, ConfigOverrides.coerce(cli_overrides))


def _apply_overrides(settings: RuntimeSettings, overrides: ConfigOverrides) -> RuntimeSettings:
    environment = dict(settings.environment)
    if overrides.environment is not None:
        environment.update(overrides.environment)
    return RuntimeSettings(
        home=overrides.home if overrides.home is not None else settings.home,
        default_provider=overrides.default_provider or settings.default_provider,
        default_model=overrides.default_model or settings.default_model,
        language=overrides.language or settings.language,
        verbose=overrides.verbose if overrides.verbose is not None else settings.verbose,
        yolo=overrides.yolo if overrides.yolo is not None else settings.yolo,
        proxy=overrides.proxy if overrides.proxy is not None else settings.proxy,
        environment=environment,
    )


def _env_overrides(env: Mapping[str, str]) -> ConfigOverrides:
    return _merge_overrides(_json_env_overrides(env), _env_name_overrides(env))


def _env_name_overrides(env: Mapping[str, str]) -> ConfigOverrides:
    return ConfigOverrides(
        home=_config_dir_from_env(env),
        default_provider=_optional_str(env.get("GA_PROVIDER")),
        default_model=_optional_str(env.get("GA_MODEL")),
        language=_optional_str(env.get("GA_LANG")),
        verbose=_env_bool("GA_VERBOSE", env=env) if "GA_VERBOSE" in env else None,
        yolo=_env_bool("GA_YOLO", env=env) if "GA_YOLO" in env else None,
        proxy=_resolve_proxy_from_env(env),
    )


def _json_env_overrides(env: Mapping[str, str]) -> ConfigOverrides:
    for name in ENV_CONFIG_JSON_NAMES:
        raw = _optional_str(env.get(name))
        if raw is None:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{name} must contain a JSON object") from exc
        if not isinstance(parsed, Mapping):
            raise ValueError(f"{name} must contain a JSON object")
        return _overrides_from_config_mapping(parsed)
    return ConfigOverrides()


def _config_dir_from_env(env: Mapping[str, str]) -> Path | None:
    for name in CONFIG_DIR_ENV_NAMES:
        value = _optional_path(env.get(name))
        if value is not None:
            return value
    return None


def _file_overrides(path: Path) -> ConfigOverrides:
    return _overrides_from_config_mapping(load_config_file(path))


def _overrides_from_config_mapping(raw: Mapping[str, Any]) -> ConfigOverrides:
    env_values = _optional_environment(raw.get("env"))
    env_overrides = _env_name_overrides(env_values or {})
    runtime_overrides = ConfigOverrides.from_mapping(extract_runtime_config(raw))
    env_block = (
        ConfigOverrides(environment=env_values) if env_values is not None else ConfigOverrides()
    )
    return _merge_overrides(env_block, env_overrides, runtime_overrides)


def _merge_overrides(*layers: ConfigOverrides) -> ConfigOverrides:
    merged = ConfigOverrides()
    for layer in layers:
        merged = ConfigOverrides(
            home=layer.home if layer.home is not None else merged.home,
            default_provider=(
                layer.default_provider
                if layer.default_provider is not None
                else merged.default_provider
            ),
            default_model=(
                layer.default_model if layer.default_model is not None else merged.default_model
            ),
            language=layer.language if layer.language is not None else merged.language,
            verbose=layer.verbose if layer.verbose is not None else merged.verbose,
            yolo=layer.yolo if layer.yolo is not None else merged.yolo,
            proxy=layer.proxy if layer.proxy is not None else merged.proxy,
            environment=_merge_environment(merged.environment, layer.environment),
        )
    return merged


def _merge_environment(
    lower: dict[str, str] | None,
    higher: dict[str, str] | None,
) -> dict[str, str] | None:
    if lower is None and higher is None:
        return None
    merged = dict(lower or {})
    if higher is not None:
        merged.update(higher)
    return merged


def _resolve_proxy_from_env(env: Mapping[str, str]) -> str | None:
    for name in PROXY_ENV_NAMES:
        value = _optional_str(env.get(name))
        if value is not None:
            return value
    return None


def _search_base(cwd: Path | None) -> Path:
    base = (cwd or Path.cwd()).expanduser().resolve()
    if base.exists() and base.is_file():
        return base.parent
    return base


def find_user_config_path(env: Mapping[str, str] | None = None) -> Path | None:
    """Find the user-level config file, preferring JSON settings like free-code."""
    home = get_agent_home(env)
    for config_name in USER_CONFIG_NAMES:
        candidate = home / config_name
        if candidate.exists():
            return candidate
    return None


def _pick(values: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key not in values:
            continue
        value = values[key]
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return _MISSING


def _optional_str(value: Any) -> str | None:
    if value is _MISSING or value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _optional_path(value: Any) -> Path | None:
    cleaned = _optional_str(value)
    return Path(cleaned).expanduser() if cleaned else None


def _optional_bool(value: Any, name: str) -> bool | None:
    if value is _MISSING or value is None:
        return None
    return parse_bool(value, name=name)


def _optional_environment(value: Any) -> dict[str, str] | None:
    if value is _MISSING or value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("env must be a JSON object with string-like keys and values")

    environment: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        if raw_value is None:
            continue
        key = str(raw_key).strip()
        if not key:
            raise ValueError("env keys cannot be empty")
        environment[key] = _environment_value(raw_value)
    return environment


def _environment_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
