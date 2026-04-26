"""Config file loading helpers for GenericAgent Engineered."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

RUNTIME_SECTION_KEYS = ("runtime", "generic_agent", "generic-agent", "settings")


def load_config_file(path: Path) -> dict[str, Any]:
    """Load a YAML/JSON config file, returning an empty mapping when absent."""
    config_path = Path(path).expanduser()
    if not config_path.exists():
        return {}

    text = config_path.read_text(encoding="utf-8")
    if not text.strip():
        return {}

    loaded = _load_with_pyyaml(text)
    if loaded is None:
        loaded = _load_simple_yaml(text)

    if loaded is None:
        return {}
    if not isinstance(loaded, Mapping):
        raise ValueError(f"Config file must contain a mapping: {config_path}")
    return dict(loaded)


def load_runtime_config(path: Path) -> dict[str, Any]:
    """Load config and return only runtime-relevant keys."""
    return extract_runtime_config(load_config_file(path))


def extract_runtime_config(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten supported runtime sections while allowing top-level runtime keys."""
    if not raw:
        return {}

    extracted: dict[str, Any] = {}
    for section_key in RUNTIME_SECTION_KEYS:
        section = raw.get(section_key)
        if isinstance(section, Mapping):
            extracted.update(section)

    for key, value in raw.items():
        if key not in RUNTIME_SECTION_KEYS:
            extracted.setdefault(key, value)
    return extracted


def _load_with_pyyaml(text: str) -> Any | None:
    try:
        import yaml  # type: ignore[import-untyped]
    except Exception:
        return None
    return yaml.safe_load(text)


def _load_simple_yaml(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "---":
            continue

        if ":" not in stripped:
            raise ValueError(f"Unsupported config syntax on line {line_number}")

        indent = len(line) - len(line.lstrip(" "))
        key, value = stripped.split(":", 1)
        key = key.strip().strip("\"'")
        if not key:
            raise ValueError(f"Empty config key on line {line_number}")

        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise ValueError(f"Invalid indentation on line {line_number}")

        current = stack[-1][1]
        value = value.strip()
        if value == "":
            nested: dict[str, Any] = {}
            current[key] = nested
            stack.append((indent, nested))
        else:
            current[key] = _parse_scalar(value)

    return root


def _parse_scalar(value: str) -> Any:
    value = _strip_inline_comment(value).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]

    lowered = value.lower()
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False
    if lowered in {"null", "none", "~"}:
        return None

    try:
        return int(value)
    except ValueError:
        return value


def _strip_inline_comment(value: str) -> str:
    in_single = False
    in_double = False
    for index, char in enumerate(value):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            return value[:index]
    return value
