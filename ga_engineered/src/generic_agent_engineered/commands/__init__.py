"""Central slash command registry and command router."""

from .base import (
    CommandContext,
    CommandDef,
    CommandHandler,
    CommandResult,
    CommandRouter,
    ParsedCommand,
    available_commands,
    build_lookup,
    commands_by_category,
    parse_command_line,
    resolve_command,
)
from .registry import COMMAND_REGISTRY

__all__ = [
    "COMMAND_REGISTRY",
    "CommandContext",
    "CommandDef",
    "CommandHandler",
    "CommandResult",
    "CommandRouter",
    "ParsedCommand",
    "available_commands",
    "build_lookup",
    "commands_by_category",
    "parse_command_line",
    "resolve_command",
]
