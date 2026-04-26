"""Read-only MCP, plugin, agent, and hook discovery surfaces."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from generic_agent_engineered.config import get_project_config_path
from generic_agent_engineered.engine import AgentRuntime


@dataclass(frozen=True)
class ExtensionSummary:
    name: str
    kind: str
    status: str
    source: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "kind": self.kind,
            "status": self.status,
            "source": self.source,
            "detail": self.detail,
        }


def list_mcp_servers(runtime: AgentRuntime) -> list[ExtensionSummary]:
    items: list[ExtensionSummary] = []
    for path in _settings_paths(runtime):
        data = _load_json(path)
        for key in ("mcp", "mcpServers", "mcp_servers"):
            raw = data.get(key)
            if isinstance(raw, dict):
                servers = raw.get("servers") if key == "mcp" else raw
                if isinstance(servers, dict):
                    for name, value in sorted(servers.items()):
                        items.append(
                            ExtensionSummary(
                                name=str(name),
                                kind="mcp",
                                status="configured",
                                source=str(path),
                                detail=_describe_mapping(value),
                            )
                        )
    return items


def list_plugins(runtime: AgentRuntime) -> list[ExtensionSummary]:
    roots = [
        Path.cwd() / ".agents" / "plugins",
        Path.cwd() / ".codex" / "plugins",
        runtime.settings.home / "plugins",
        Path.home() / ".agents" / "plugins",
        Path.home() / ".codex" / "plugins",
    ]
    return _list_named_paths("plugin", roots)


def list_agents(runtime: AgentRuntime) -> list[ExtensionSummary]:
    roots = [
        Path.cwd() / ".agents" / "agents",
        Path.cwd() / ".codex" / "agents",
        Path.cwd() / "prompts",
        runtime.settings.home / "agents",
        Path.home() / ".codex" / "agents",
    ]
    return _list_named_paths("agent", roots, suffixes={".md", ".toml", ".json"})


def list_hooks(runtime: AgentRuntime) -> list[ExtensionSummary]:
    roots = [
        Path.cwd() / ".codex" / "hooks",
        runtime.settings.home / "hooks",
        Path.home() / ".codex" / "hooks",
        Path.cwd() / ".git" / "hooks",
    ]
    return _list_named_paths("hook", roots, include_samples=True)


def list_extensions(runtime: AgentRuntime, kind: str) -> list[ExtensionSummary]:
    if kind == "mcp":
        return list_mcp_servers(runtime)
    if kind == "plugin":
        return list_plugins(runtime)
    if kind == "agent":
        return list_agents(runtime)
    if kind == "hook":
        return list_hooks(runtime)
    raise ValueError(f"unknown extension kind: {kind}")


def _settings_paths(runtime: AgentRuntime) -> list[Path]:
    paths = [runtime.settings.home / "settings.json", get_project_config_path(Path.cwd())]
    return [path for path in paths if path.exists()]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _describe_mapping(value: Any) -> str:
    if isinstance(value, dict):
        command = value.get("command") or value.get("url") or value.get("type")
        if command:
            return str(command)
        return ", ".join(str(key) for key in sorted(value.keys())) or "configured"
    return str(value) if value is not None else "configured"


def _list_named_paths(
    kind: str,
    roots: list[Path],
    *,
    suffixes: set[str] | None = None,
    include_samples: bool = False,
) -> list[ExtensionSummary]:
    seen: set[tuple[str, str]] = set()
    items: list[ExtensionSummary] = []
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        try:
            children = sorted(root.iterdir(), key=lambda path: path.name.lower())
        except OSError:
            continue
        for child in children:
            if child.name.startswith("."):
                continue
            if suffixes is not None and child.is_file() and child.suffix not in suffixes:
                continue
            if not include_samples and child.name.endswith(".sample"):
                continue
            name = child.stem if child.is_file() else child.name
            key = (name, str(child))
            if key in seen:
                continue
            seen.add(key)
            status = "sample" if child.name.endswith(".sample") else "installed"
            items.append(
                ExtensionSummary(
                    name=name,
                    kind=kind,
                    status=status,
                    source=str(child),
                    detail="directory" if child.is_dir() else child.name,
                )
            )
    return items
