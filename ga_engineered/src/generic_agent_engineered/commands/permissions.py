"""Permission and sandbox slash command handlers."""

from __future__ import annotations

from dataclasses import replace

from generic_agent_engineered.runtime.approvals import ApprovalStore, HIGH_RISK_TOOLS

from .base import CommandContext, CommandHandler, CommandResult, ParsedCommand


def handle_permissions(context: CommandContext, parsed: ParsedCommand) -> CommandResult:
    action = parsed.argv[0] if parsed.argv else "list"
    store = _approval_store(context)
    if action in {"list", "show"}:
        allowed = sorted(store.always_allow)
        lines = ["Permissions", f"  approvals file  {store.path}"]
        lines.append("  always allow    " + (", ".join(allowed) if allowed else "<none>"))
        lines.append("  gated tools     " + ", ".join(sorted(HIGH_RISK_TOOLS)))
        return CommandResult("\n".join(lines), metadata={"always_allow": allowed})

    if action == "allow":
        tool = _tool_arg(parsed)
        if tool is None:
            return CommandResult("Usage: /permissions allow <tool>", is_error=True)
        store.add_always_allow(tool)
        return CommandResult(f"Always allow: {tool}", metadata={"tool": tool})

    if action in {"deny", "revoke"}:
        tool = _tool_arg(parsed)
        if tool is None:
            return CommandResult("Usage: /permissions revoke <tool>", is_error=True)
        removed = store.remove_always_allow(tool)
        return CommandResult(
            f"Revoked always-allow: {tool}" if removed else f"No always-allow rule for: {tool}",
            metadata={"tool": tool, "removed": removed},
        )

    if action == "clear":
        count = len(store.always_allow)
        store.clear()
        return CommandResult(f"Cleared {count} always-allow rule(s)", metadata={"removed": count})

    return CommandResult(
        "Usage: /permissions [list|allow <tool>|revoke <tool>|clear]",
        is_error=True,
    )


def handle_sandbox_toggle(context: CommandContext, parsed: ParsedCommand) -> CommandResult:
    action = parsed.argv[0] if parsed.argv else "status"
    if action == "status":
        return _sandbox_status(context)
    if action in {"on", "enable", "enabled"}:
        context.runtime.settings = replace(context.runtime.settings, yolo=False)
        return _sandbox_status(context, prefix="Sandbox approvals enabled")
    if action in {"off", "disable", "disabled", "yolo"}:
        context.runtime.settings = replace(context.runtime.settings, yolo=True)
        return _sandbox_status(context, prefix="Sandbox approvals bypassed")
    return CommandResult("Usage: /sandbox-toggle [status|on|off]", is_error=True)


def _sandbox_status(context: CommandContext, *, prefix: str = "Sandbox status") -> CommandResult:
    yolo = context.runtime.settings.yolo
    mode = "bypass/yolo" if yolo else "approval-required"
    return CommandResult(
        f"{prefix}: {mode}",
        metadata={"yolo": yolo, "mode": mode},
    )


def _approval_store(context: CommandContext) -> ApprovalStore:
    return ApprovalStore.load(context.runtime.settings.home / "approvals.json")


def _tool_arg(parsed: ParsedCommand) -> str | None:
    if len(parsed.argv) < 2 or not parsed.argv[1].strip():
        return None
    return parsed.argv[1].strip()


PERMISSION_HANDLERS: dict[str, CommandHandler] = {
    "permissions": handle_permissions,
    "sandbox-toggle": handle_sandbox_toggle,
}
