"""Session and informational slash command handlers."""

from __future__ import annotations

import uuid

from generic_agent_engineered.runtime.compaction import compact_history
from generic_agent_engineered.runtime.messages import Message
from generic_agent_engineered.runtime.token_budget import estimate_messages_tokens

from .base import CommandContext, CommandHandler, CommandResult, ParsedCommand, commands_by_category


def handle_help(context: CommandContext, parsed: ParsedCommand) -> CommandResult:
    return handle_commands(context, parsed)


def handle_commands(_context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    lines: list[str] = []
    for category, commands in commands_by_category().items():
        lines.append(category)
        for command in commands:
            hint = f" {command.args_hint}" if command.args_hint else ""
            aliases = (
                f" aliases={', '.join('/' + alias for alias in command.aliases)}"
                if command.aliases
                else ""
            )
            lines.append(f"  /{command.name}{hint} - {command.description}{aliases}")
    return CommandResult("\n".join(lines))


def handle_status(context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    from generic_agent_engineered.cli.status import build_status, render_status

    return CommandResult(render_status(build_status(context.runtime)))


def handle_new(context: CommandContext, parsed: ParsedCommand) -> CommandResult:
    session_id = parsed.argv[0] if parsed.argv else f"session-{uuid.uuid4().hex[:8]}"
    _reset_runtime_session(context, session_id=session_id)
    return CommandResult(f"Started new session: {session_id}", metadata={"session_id": session_id})


def handle_clear(context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    _reset_runtime_session(context, session_id=context.runtime.state.session_id)
    return CommandResult("Session cleared")


def handle_history(context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    messages = context.runtime.state.messages
    if not messages:
        return CommandResult("History is empty")
    return CommandResult(_format_history(messages))


def handle_retry(context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    index = _last_user_index(context.runtime.state.messages)
    if index is None:
        return CommandResult("No user message to retry", is_error=True)
    message = context.runtime.state.messages[index]
    return CommandResult(
        f"Retrying last user message: {message.content}",
        metadata={"retry_content": message.content, "message_index": index},
    )


def handle_undo(context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    messages = context.runtime.state.messages
    index = _last_user_index(messages)
    if index is None:
        return CommandResult("No user turn to undo", is_error=True)

    removed = len(messages) - index
    del messages[index:]
    context.runtime.state.turn_count = max(0, context.runtime.state.turn_count - 1)
    return CommandResult(f"Removed {removed} message(s) from the last turn")


def handle_compact(context: CommandContext, parsed: ParsedCommand) -> CommandResult:
    reason = " ".join(parsed.argv).strip() or "manual"
    result = compact_history(context.runtime.state.messages, reason=reason)
    if not result.changed:
        return CommandResult("Nothing to compact", metadata={"changed": False})

    context.runtime.state.messages = list(result.messages)
    summary = result.summary
    return CommandResult(
        (
            "Compacted history: "
            f"{summary.original_message_count if summary else 0} -> {len(result.messages)} "
            f"messages, tokens={summary.compacted_tokens if summary else 0}"
        ),
        metadata={
            "changed": True,
            "messages": len(result.messages),
            "reason": reason,
        },
    )


def handle_resume(context: CommandContext, parsed: ParsedCommand) -> CommandResult:
    session_id = parsed.argv[0] if parsed.argv else "latest"
    context.runtime.state.session_id = session_id
    return CommandResult(f"Resumed session: {session_id}", metadata={"session_id": session_id})


def handle_usage(context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    messages = context.runtime.state.messages
    tokens = estimate_messages_tokens(messages)
    return CommandResult(
        "\n".join(
            [
                "Usage estimate",
                f"  messages  {len(messages)}",
                f"  turns     {context.runtime.state.turn_count}",
                f"  tokens    {tokens}",
            ]
        ),
        metadata={"messages": len(messages), "turns": context.runtime.state.turn_count},
    )


def handle_exit(_context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    return CommandResult("Exiting.", should_exit=True)


def _reset_runtime_session(context: CommandContext, *, session_id: str) -> None:
    context.runtime.state.session_id = session_id
    context.runtime.state.turn_count = 0
    context.runtime.state.messages = []


def _last_user_index(messages: list[Message]) -> int | None:
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].role == "user":
            return index
    return None


def _format_history(messages: list[Message]) -> str:
    lines = ["History"]
    for index, message in enumerate(messages, start=1):
        preview = message.content.replace("\n", " ")
        if len(preview) > 120:
            preview = f"{preview[:117].rstrip()}..."
        lines.append(f"{index}. {message.role}: {preview}")
    return "\n".join(lines)


SESSION_HANDLERS: dict[str, CommandHandler] = {
    "help": handle_help,
    "commands": handle_commands,
    "status": handle_status,
    "new": handle_new,
    "clear": handle_clear,
    "history": handle_history,
    "retry": handle_retry,
    "undo": handle_undo,
    "compact": handle_compact,
    "resume": handle_resume,
    "usage": handle_usage,
    "exit": handle_exit,
}
