"""External integration command surfaces."""

from __future__ import annotations

from generic_agent_engineered.state import integration_status, list_integration_statuses

from .base import CommandContext, CommandHandler, CommandResult, ParsedCommand

INTEGRATION_COMMANDS = {
    "ide": "IDE",
    "desktop": "Desktop app",
    "chrome": "Chrome bridge",
    "voice": "Voice input",
    "remote": "Remote session",
    "mobile": "Mobile handoff",
    "teleport": "Teleport",
}


def _list_integrations(context: CommandContext) -> CommandResult:
    items = list_integration_statuses(context.runtime)
    lines = ["External integrations"]
    for item in items:
        marker = "available" if item.available else "unavailable"
        lines.append(f"  {item.name} [{item.status}/{marker}] {item.detail}")
        lines.append(f"    {item.action}")
    return CommandResult(
        "\n".join(lines),
        metadata={"integrations": [item.to_dict() for item in items]},
    )


def _integration_result(context: CommandContext, name: str) -> CommandResult:
    item = integration_status(context.runtime, name)
    marker = "available" if item.available else "unavailable"
    content = "\n".join(
        [
            f"{item.label}: {item.status} ({marker})",
            item.detail,
            item.action,
        ]
    )
    return CommandResult(content, metadata={"integration": item.to_dict()})


def _handler(name: str) -> CommandHandler:
    def handle(context: CommandContext, parsed: ParsedCommand) -> CommandResult:
        subcommand = parsed.argv[0] if parsed.argv else "status"
        if subcommand in {"list", "ls", "show", "status"}:
            return _integration_result(context, name)
        item = integration_status(context.runtime, name)
        return CommandResult(
            f"/{name} {subcommand} unavailable: {item.action}",
            is_error=True,
            metadata={
                "unavailable": True,
                "integration": item.to_dict(),
                "command": name,
                "subcommand": subcommand,
            },
        )

    return handle


def _integrations_handler(context: CommandContext, parsed: ParsedCommand) -> CommandResult:
    if not parsed.argv or parsed.argv[0] in {"list", "ls", "show", "status"}:
        return _list_integrations(context)
    name = parsed.argv[0].lower()
    if name not in INTEGRATION_COMMANDS:
        return CommandResult(
            f"Unknown integration: {name}",
            is_error=True,
            metadata={"unknown_integration": name},
        )
    return _integration_result(context, name)


INTEGRATION_HANDLERS: dict[str, CommandHandler] = {
    "integrations": _integrations_handler,
    **{name: _handler(name) for name in INTEGRATION_COMMANDS},
}
