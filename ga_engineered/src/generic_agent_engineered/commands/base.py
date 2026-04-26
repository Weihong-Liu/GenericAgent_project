"""Command metadata, parsing, and dispatch primitives."""

from __future__ import annotations

import difflib
import shlex
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from generic_agent_engineered.engine import AgentRuntime


@dataclass(frozen=True)
class CommandDef:
    name: str
    description: str
    category: str
    aliases: tuple[str, ...] = ()
    args_hint: str = ""
    subcommands: tuple[str, ...] = ()
    cli_only: bool = False

    @property
    def slash(self) -> str:
        return f"/{self.name}"


@dataclass(frozen=True)
class ParsedCommand:
    name: str
    argv: tuple[str, ...] = ()
    raw: str = ""


@dataclass(frozen=True)
class CommandResult:
    content: str
    is_error: bool = False
    should_exit: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CommandContext:
    runtime: AgentRuntime = field(default_factory=AgentRuntime)
    tool_registry: Any | None = None
    environment: Mapping[str, str] | None = None


CommandHandler = Callable[[CommandContext, ParsedCommand], CommandResult]


def build_lookup(commands: Iterable[CommandDef] | None = None) -> dict[str, CommandDef]:
    from .registry import COMMAND_REGISTRY

    source = COMMAND_REGISTRY if commands is None else commands
    lookup: dict[str, CommandDef] = {}
    for command in source:
        lookup[command.name] = command
        lookup[command.slash] = command
        for alias in command.aliases:
            lookup[alias] = command
            lookup[f"/{alias}"] = command
    return lookup


def resolve_command(raw: str) -> CommandDef | None:
    return build_lookup().get(raw.strip().lower())


def commands_by_category(
    *,
    commands: Iterable[CommandDef] | None = None,
    include_cli_only: bool = True,
) -> dict[str, list[CommandDef]]:
    grouped: dict[str, list[CommandDef]] = {}
    for command in available_commands(
        commands=commands,
        include_cli_only=include_cli_only,
    ):
        grouped.setdefault(command.category, []).append(command)
    return grouped


def available_commands(
    *,
    commands: Iterable[CommandDef] | None = None,
    include_cli_only: bool = True,
    category: str | None = None,
) -> tuple[CommandDef, ...]:
    from .registry import COMMAND_REGISTRY

    source = COMMAND_REGISTRY if commands is None else tuple(commands)
    filtered = [
        command
        for command in source
        if (include_cli_only or not command.cli_only)
        and (category is None or command.category == category)
    ]
    return tuple(filtered)


def parse_command_line(raw: str) -> ParsedCommand:
    stripped = raw.strip()
    if not stripped:
        raise ValueError("command is required")
    parts = shlex.split(stripped)
    name = parts[0].lstrip("/").lower()
    if not name:
        raise ValueError("command name is required")
    return ParsedCommand(name=name, argv=tuple(parts[1:]), raw=raw)


class CommandRouter:
    def __init__(
        self,
        handlers: Mapping[str, CommandHandler] | None = None,
        *,
        commands: Iterable[CommandDef] | None = None,
    ) -> None:
        from .handlers import build_command_handlers
        from .registry import COMMAND_REGISTRY

        self.commands = tuple(COMMAND_REGISTRY if commands is None else commands)
        self.lookup = build_lookup(self.commands)
        self.handlers = dict(build_command_handlers() if handlers is None else handlers)

    def dispatch(self, raw: str, context: CommandContext | None = None) -> CommandResult:
        try:
            parsed = parse_command_line(raw)
        except ValueError as exc:
            return CommandResult(str(exc), is_error=True)

        command = self.lookup.get(parsed.name) or self.lookup.get(f"/{parsed.name}")
        if command is None:
            suggestion = self.suggest(parsed.name)
            suffix = f". Did you mean /{suggestion}?" if suggestion else ""
            return CommandResult(
                f"Unknown command: /{parsed.name}{suffix}",
                is_error=True,
                metadata={"suggestion": suggestion or ""},
            )

        canonical = ParsedCommand(command.name, parsed.argv, raw=parsed.raw)
        handler = self.handlers.get(command.name)
        if handler is None:
            return CommandResult(
                f"Command /{command.name} is registered but has no handler",
                is_error=True,
            )
        return handler(context or CommandContext(), canonical)

    def suggest(self, name: str) -> str | None:
        candidates = sorted({command.name for command in self.commands} | set(self.lookup))
        matches = difflib.get_close_matches(name.lstrip("/"), candidates, n=1, cutoff=0.5)
        if not matches:
            return None
        return matches[0].lstrip("/")
