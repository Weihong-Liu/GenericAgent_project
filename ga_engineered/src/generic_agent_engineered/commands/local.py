"""Local/free-code-style utility command handlers."""

from __future__ import annotations

import json
from collections.abc import Callable

from generic_agent_engineered import __version__
from generic_agent_engineered.runtime.token_budget import estimate_messages_tokens
from generic_agent_engineered.state import (
    list_background_tasks,
    list_session_summaries,
    worktree_status,
)

from .base import CommandContext, CommandHandler, CommandResult, ParsedCommand


def handle_version(_context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    return CommandResult(f"GenericAgent Engineered {__version__}", metadata={"version": __version__})


def handle_stats(context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    messages = context.runtime.state.messages
    by_role: dict[str, int] = {}
    for message in messages:
        by_role[message.role] = by_role.get(message.role, 0) + 1
    payload = {
        "session_id": context.runtime.state.session_id,
        "turns": context.runtime.state.turn_count,
        "messages": len(messages),
        "messages_by_role": by_role,
        "tokens_estimate": estimate_messages_tokens(messages),
        "provider": context.runtime.state.provider_id,
        "model": context.runtime.state.model,
    }
    return CommandResult(json.dumps(payload, indent=2, sort_keys=True), metadata=payload)


def handle_summary(context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    messages = context.runtime.state.messages
    if not messages:
        return CommandResult("No conversation messages yet", metadata={"messages": 0})
    last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
    last_assistant = next((m.content for m in reversed(messages) if m.role == "assistant"), "")
    lines = [
        "Conversation summary",
        f"  session   {context.runtime.state.session_id}",
        f"  turns     {context.runtime.state.turn_count}",
        f"  messages  {len(messages)}",
        f"  last user {one_line(last_user)}",
    ]
    if last_assistant:
        lines.append(f"  last bot  {one_line(last_assistant)}")
    return CommandResult("\n".join(lines), metadata={"messages": len(messages)})


def handle_export(context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    payload = [
        {"role": message.role, "content": message.content}
        for message in context.runtime.state.messages
    ]
    return CommandResult(
        json.dumps(payload, ensure_ascii=False, indent=2),
        metadata={"format": "json", "messages": len(payload)},
    )


def handle_diff(context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    messages = context.runtime.state.messages
    if len(messages) < 2:
        return CommandResult("Not enough conversation history to diff", is_error=True)
    before = messages[-2].content.splitlines(keepends=True)
    after = messages[-1].content.splitlines(keepends=True)
    import difflib

    diff = "".join(
        difflib.unified_diff(
            before,
            after,
            fromfile=f"{messages[-2].role}:previous",
            tofile=f"{messages[-1].role}:latest",
        )
    )
    return CommandResult(diff or "Last two messages are identical", metadata={"messages": 2})


def handle_keybindings(_context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    return CommandResult(
        "\n".join(
            [
                "Keybindings",
                "  Ctrl-P quick open",
                "  Ctrl-F transcript search",
                "  Ctrl-M model picker",
                "  Ctrl-T theme picker",
                "  Ctrl-X thinking marker",
                "  Ctrl-S session browser",
                "  Ctrl-B background tasks",
                "  Ctrl-J worktree status",
                "  Ctrl-R history search",
                "  Shift-Up message navigator",
                "  Ctrl-O expand recent tool output",
                "  Ctrl-G cancel turn",
                "  Ctrl-Y restore stashed prompt",
            ]
        )
    )


def handle_statusline(_context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    return CommandResult(
        "Statusline is managed by the TypeScript TUI and shows model, turn count, tokens, busy state, and Vim mode."
    )


def handle_copy(_context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    return _feature_gated("copy", "Clipboard integration is not wired in this TUI runtime yet.")


def handle_theme(_context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    return _feature_gated("theme", "Use Ctrl-T for the current UI picker; persistent theme backend is not wired yet.")


def handle_vim(_context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    return CommandResult("Vim mode is controlled by GA_VIM_MODE at TUI startup.")


def handle_output_style(_context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    return _feature_gated("output-style", "Output-style persistence is not implemented yet.")


def handle_effort(_context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    return _feature_gated("effort", "Backend reasoning-effort control is not implemented yet.")


def handle_rate_limit_options(context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    messages = context.runtime.state.messages
    tokens = estimate_messages_tokens(messages)
    lines = [
        "Rate limit options",
        f"  provider  {context.runtime.state.provider_id}",
        f"  model     {context.runtime.state.model}",
        f"  tokens    {tokens} estimated",
        "  action    /compact to shrink context before retrying",
        "  action    /new or /clear to start clean",
        "  action    /model or /providers to switch configured backends",
    ]
    return CommandResult(
        "\n".join(lines),
        metadata={
            "provider": context.runtime.state.provider_id,
            "model": context.runtime.state.model,
            "tokens_estimate": tokens,
        },
    )


def handle_bridge(_context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    return CommandResult(
        "\n".join(
            [
                "Browser bridge",
                "  command  uv run gae bridge",
                "  purpose  serves web_scan/web_execute_js through the legacy TMWebDriver bridge",
                "  note     the TUI gateway best-effort auto-spawns it when bridge extras are installed",
            ]
        ),
        metadata={"command": "uv run gae bridge"},
    )


def handle_rename(context: CommandContext, parsed: ParsedCommand) -> CommandResult:
    name = " ".join(parsed.argv).strip()
    if not name:
        return CommandResult("Usage: /rename <session-name>", is_error=True)
    context.runtime.state.session_id = name
    return CommandResult(f"Renamed current session: {name}", metadata={"session_id": name})


def handle_sessions(context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    summaries = list_session_summaries(context.runtime)
    lines = ["Sessions"]
    for summary in summaries:
        marker = "*" if summary.current else " "
        label = summary.title or summary.id
        suffix = "" if summary.persisted else " (memory)"
        lines.append(
            f"{marker} {summary.id}  {label}  messages={summary.message_count}{suffix}"
        )
    return CommandResult(
        "\n".join(lines),
        metadata={"sessions": [summary.to_dict() for summary in summaries]},
    )


def handle_tasks(_context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    tasks = list_background_tasks(busy=False, request_id=None)
    if not tasks:
        return CommandResult(
            "No background tasks are running",
            metadata={"tasks": [], "busy": False},
        )
    return CommandResult(
        "\n".join(f"{task.status} {task.label}: {task.detail}" for task in tasks),
        metadata={"tasks": [task.to_dict() for task in tasks], "busy": True},
    )


def handle_worktree(_context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    status = worktree_status()
    if not status["is_git"]:
        return CommandResult("Current workspace is not a git worktree", metadata=status)
    lines = [
        "Worktree",
        f"  path     {status['path']}",
        f"  branch   {status['branch']}",
        f"  dirty    {status['dirty']} ({status['changes']} changes)",
        f"  remote   +{status['ahead']} / -{status['behind']}",
    ]
    return CommandResult("\n".join(lines), metadata=status)


def _unsupported(command: str) -> CommandHandler:
    def handler(_context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
        return _feature_gated(command, f"/{command} is registered for parity but not implemented yet.")

    return handler


def _feature_gated(command: str, detail: str) -> CommandResult:
    return CommandResult(
        f"/{command} unavailable: {detail}",
        is_error=True,
        metadata={"unavailable": True, "command": command},
    )


def one_line(text: str, limit: int = 120) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else f"{flat[: limit - 3].rstrip()}..."


LOCAL_HANDLERS: dict[str, CommandHandler] = {
    "version": handle_version,
    "stats": handle_stats,
    "summary": handle_summary,
    "export": handle_export,
    "diff": handle_diff,
    "copy": handle_copy,
    "theme": handle_theme,
    "vim": handle_vim,
    "keybindings": handle_keybindings,
    "statusline": handle_statusline,
    "output-style": handle_output_style,
    "effort": handle_effort,
    "rate-limit-options": handle_rate_limit_options,
    "rename": handle_rename,
    "sessions": handle_sessions,
    "tasks": handle_tasks,
    "worktree": handle_worktree,
    "bridge": handle_bridge,
    "add-dir": _unsupported("add-dir"),
    "advisor": _unsupported("advisor"),
    "assistant": _unsupported("assistant"),
    "branch": _unsupported("branch"),
    "btw": _unsupported("btw"),
    "color": _unsupported("color"),
    "context": _unsupported("context"),
    "cost": _unsupported("cost"),
    "extra-usage": _unsupported("extra-usage"),
    "fast": _unsupported("fast"),
    "feedback": _unsupported("feedback"),
    "files": _unsupported("files"),
    "heapdump": _unsupported("heapdump"),
    "insights": _unsupported("insights"),
    "init": _unsupported("init"),
    "install-github-app": _unsupported("install-github-app"),
    "install-slack-app": _unsupported("install-slack-app"),
    "onboarding": _unsupported("onboarding"),
    "passes": _unsupported("passes"),
    "plan": _unsupported("plan"),
    "pr_comments": _unsupported("pr_comments"),
    "privacy-settings": _unsupported("privacy-settings"),
    "release-notes": _unsupported("release-notes"),
    "reload-plugins": _unsupported("reload-plugins"),
    "remote-env": _unsupported("remote-env"),
    "remote-setup": _unsupported("remote-setup"),
    "reset-limits": _unsupported("reset-limits"),
    "review": _unsupported("review"),
    "rewind": _unsupported("rewind"),
    "security-review": _unsupported("security-review"),
    "session": _unsupported("session"),
    "share": _unsupported("share"),
    "stickers": _unsupported("stickers"),
    "tag": _unsupported("tag"),
    "terminal-setup": _unsupported("terminal-setup"),
    "thinkback": _unsupported("thinkback"),
    "thinkback-play": _unsupported("thinkback-play"),
    "ultrareview": _unsupported("ultrareview"),
    "upgrade": _unsupported("upgrade"),
}
