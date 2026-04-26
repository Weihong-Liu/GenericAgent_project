"""Tool and diagnostic slash command handlers."""

from __future__ import annotations

from collections.abc import Iterable

from generic_agent_engineered.tools import (
    CODE_RUN_SPEC,
    FILE_PATCH_SPEC,
    FILE_READ_SPEC,
    FILE_WRITE_SPEC,
    SHELL_SPEC,
    WEB_EXECUTE_JS_SPEC,
    WEB_OPEN_SPEC,
    WEB_SCAN_SPEC,
    ToolSpec,
)

from .base import CommandContext, CommandHandler, CommandResult, ParsedCommand


def handle_tools(context: CommandContext, parsed: ParsedCommand) -> CommandResult:
    action = parsed.argv[0] if parsed.argv else "list"
    if action in {"enable", "disable"}:
        return _toggle_tool(context, parsed, action=action)
    if action != "list":
        return CommandResult(f"unknown /tools action: {action}", is_error=True)

    if context.tool_registry is not None and hasattr(context.tool_registry, "list_tools"):
        registrations = context.tool_registry.list_tools(include_disabled=True)
        lines = ["Tools"]
        for registration in registrations:
            state = "enabled" if registration.enabled else "disabled"
            lines.append(f"  {registration.name:<18} {state}")
        return CommandResult("\n".join(lines))

    lines = ["Tools"]
    for spec in _core_tool_specs():
        permissions = ", ".join(permission.name for permission in spec.permissions) or "none"
        lines.append(f"  {spec.name:<18} permissions={permissions}")
    return CommandResult("\n".join(lines))


def handle_doctor(context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    from generic_agent_engineered.cli.doctor import (
        build_diagnostic_report,
        render_diagnostic_report,
    )

    report = build_diagnostic_report(context.runtime)
    return CommandResult(render_diagnostic_report(report), is_error=not report.ok)


def _toggle_tool(
    context: CommandContext,
    parsed: ParsedCommand,
    *,
    action: str,
) -> CommandResult:
    if len(parsed.argv) < 2:
        return CommandResult(f"/tools {action} requires a tool name", is_error=True)
    if context.tool_registry is None:
        return CommandResult(
            "No live tool registry is attached to this command context",
            is_error=True,
        )

    name = parsed.argv[1]
    try:
        if action == "enable":
            context.tool_registry.enable(name)
        else:
            context.tool_registry.disable(name)
    except Exception as exc:
        return CommandResult(str(exc), is_error=True)
    return CommandResult(f"Tool {action}d: {name}", metadata={"tool": name, "action": action})


def _core_tool_specs() -> Iterable[ToolSpec]:
    return (
        FILE_READ_SPEC,
        FILE_WRITE_SPEC,
        FILE_PATCH_SPEC,
        SHELL_SPEC,
        CODE_RUN_SPEC,
        WEB_OPEN_SPEC,
        WEB_SCAN_SPEC,
        WEB_EXECUTE_JS_SPEC,
    )


TOOL_HANDLERS: dict[str, CommandHandler] = {
    "tools": handle_tools,
    "doctor": handle_doctor,
}
