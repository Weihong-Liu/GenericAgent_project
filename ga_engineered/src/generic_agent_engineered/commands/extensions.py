"""MCP, plugin, custom-agent, and hook command surfaces."""

from __future__ import annotations

from generic_agent_engineered.state import list_extensions

from .base import CommandContext, CommandHandler, CommandResult, ParsedCommand

KINDS = {
    "mcp": "MCP servers",
    "plugin": "Plugins",
    "agents": "Custom agents",
    "hooks": "Hooks",
}


def _list_kind(context: CommandContext, kind: str) -> CommandResult:
    lookup_kind = {"agents": "agent", "hooks": "hook"}.get(kind, kind)
    items = list_extensions(context.runtime, lookup_kind)
    title = KINDS[kind]
    notes = _parity_notes(kind)
    if not items:
        return CommandResult(
            f"{title}: none discovered{notes}",
            metadata={"kind": lookup_kind, "items": [], "parity_note": notes.strip()},
        )
    lines = [title]
    for item in items:
        lines.append(f"  {item.name} [{item.status}] {item.source}")
        if item.detail:
            lines.append(f"    {item.detail}")
    if notes:
        lines.append(notes.strip())
    return CommandResult(
        "\n".join(lines),
        metadata={
            "kind": lookup_kind,
            "items": [item.to_dict() for item in items],
            "parity_note": notes.strip(),
        },
    )


def _parity_notes(kind: str) -> str:
    if kind == "hooks":
        return (
            "\n  parity  read-only discovery only; free-code's hook editor and "
            "execution lifecycle are not wired into the GenericAgent runtime."
        )
    return ""


def _handler(kind: str) -> CommandHandler:
    def handle(context: CommandContext, parsed: ParsedCommand) -> CommandResult:
        subcommand = parsed.argv[0] if parsed.argv else "list"
        if subcommand in {"list", "ls", "show", "status"}:
            return _list_kind(context, kind)
        return CommandResult(
            f"/{kind} {subcommand} unavailable: write/edit flows are not wired yet.",
            is_error=True,
            metadata={"unavailable": True, "command": kind, "subcommand": subcommand},
        )

    return handle


EXTENSION_HANDLERS: dict[str, CommandHandler] = {
    "mcp": _handler("mcp"),
    "plugin": _handler("plugin"),
    "agents": _handler("agents"),
    "hooks": _handler("hooks"),
}
