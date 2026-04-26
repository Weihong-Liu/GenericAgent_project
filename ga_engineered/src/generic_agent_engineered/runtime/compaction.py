"""History compaction for provider-neutral runtime messages."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .messages import Message
from .token_budget import (
    BudgetReport,
    TokenBudget,
    estimate_messages_tokens,
    evaluate_token_budget,
)


@dataclass(frozen=True)
class CompactionConfig:
    keep_recent_turns: int = 3
    max_summary_chars: int = 1600
    max_item_chars: int = 240

    def __post_init__(self) -> None:
        if self.keep_recent_turns < 0:
            raise ValueError("keep_recent_turns must be non-negative")
        if self.max_summary_chars < 200:
            raise ValueError("max_summary_chars must be at least 200")
        if self.max_item_chars < 40:
            raise ValueError("max_item_chars must be at least 40")


@dataclass(frozen=True)
class CompactionSummary:
    original_message_count: int
    compacted_message_count: int
    preserved_message_count: int
    original_tokens: int
    compacted_tokens: int
    reason: str
    summary_message: Message


@dataclass(frozen=True)
class CompactionResult:
    messages: tuple[Message, ...]
    changed: bool
    summary: CompactionSummary | None = None
    budget_report: BudgetReport | None = None


def compact_history(
    messages: Sequence[Message],
    *,
    config: CompactionConfig | None = None,
    reason: str = "manual",
    budget_report: BudgetReport | None = None,
) -> CompactionResult:
    config = config or CompactionConfig()
    source = tuple(messages)
    system_preamble, conversation = _split_system_preamble(source)
    turns = _split_turns(conversation)

    if not turns:
        return CompactionResult(source, changed=False, budget_report=budget_report)

    old_turns, recent_turns = _split_old_and_recent_turns(turns, config.keep_recent_turns)
    old_messages = _flatten(old_turns)
    if not old_messages:
        return CompactionResult(source, changed=False, budget_report=budget_report)

    recent_messages = _flatten(recent_turns)
    original_tokens = estimate_messages_tokens(source)
    summary_text = _build_summary_text(
        old_messages,
        config=config,
        reason=reason,
        budget_report=budget_report,
        original_tokens=original_tokens,
    )
    summary_message = Message(
        role="system",
        content=summary_text,
        metadata={
            "compaction": True,
            "reason": reason,
            "compacted_messages": len(old_messages),
            "preserved_messages": len(system_preamble) + len(recent_messages),
            "keep_recent_turns": config.keep_recent_turns,
            "original_tokens": original_tokens,
        },
    )
    compacted_messages = (*system_preamble, summary_message, *recent_messages)
    compacted_tokens = estimate_messages_tokens(compacted_messages)
    summary = CompactionSummary(
        original_message_count=len(source),
        compacted_message_count=len(old_messages),
        preserved_message_count=len(system_preamble) + len(recent_messages),
        original_tokens=original_tokens,
        compacted_tokens=compacted_tokens,
        reason=reason,
        summary_message=summary_message,
    )
    return CompactionResult(
        messages=compacted_messages,
        changed=True,
        summary=summary,
        budget_report=budget_report,
    )


def compact_history_if_needed(
    messages: Sequence[Message],
    *,
    budget: TokenBudget,
    config: CompactionConfig | None = None,
    reason: str = "token_budget",
) -> CompactionResult:
    budget_report = evaluate_token_budget(messages, budget)
    if not budget_report.over_budget:
        return CompactionResult(
            tuple(messages),
            changed=False,
            budget_report=budget_report,
        )
    return compact_history(
        messages,
        config=config,
        reason=reason,
        budget_report=budget_report,
    )


def _split_system_preamble(
    messages: tuple[Message, ...],
) -> tuple[tuple[Message, ...], tuple[Message, ...]]:
    preamble: list[Message] = []
    split_at = 0
    for message in messages:
        if message.role != "system" or message.metadata.get("compaction"):
            break
        preamble.append(message)
        split_at += 1
    return tuple(preamble), messages[split_at:]


def _split_turns(messages: tuple[Message, ...]) -> list[tuple[Message, ...]]:
    turns: list[list[Message]] = []
    current: list[Message] = []
    for message in messages:
        if message.role == "user" and current:
            turns.append(current)
            current = [message]
        else:
            current.append(message)
    if current:
        turns.append(current)
    return [tuple(turn) for turn in turns]


def _split_old_and_recent_turns(
    turns: list[tuple[Message, ...]],
    keep_recent_turns: int,
) -> tuple[list[tuple[Message, ...]], list[tuple[Message, ...]]]:
    if keep_recent_turns == 0:
        return turns, []
    if len(turns) <= keep_recent_turns:
        return [], turns
    return turns[:-keep_recent_turns], turns[-keep_recent_turns:]


def _flatten(turns: list[tuple[Message, ...]]) -> tuple[Message, ...]:
    return tuple(message for turn in turns for message in turn)


def _build_summary_text(
    messages: tuple[Message, ...],
    *,
    config: CompactionConfig,
    reason: str,
    budget_report: BudgetReport | None,
    original_tokens: int,
) -> str:
    lines = [
        "[History compacted]",
        f"Reason: {reason}.",
        f"Original estimate: {original_tokens} tokens.",
        f"Compacted older messages: {len(messages)}.",
    ]
    if budget_report is not None:
        lines.append(
            "Budget trigger: "
            f"{budget_report.estimated_tokens}/{budget_report.trigger_tokens} tokens."
        )

    lines.append("Older context summary:")
    lines.extend(f"- {_summarize_message(message, config.max_item_chars)}" for message in messages)
    return _truncate("\n".join(lines), config.max_summary_chars)


def _summarize_message(message: Message, max_chars: int) -> str:
    if message.role == "assistant" and message.tool_calls:
        calls = ", ".join(f"{tool_call.name}({tool_call.id})" for tool_call in message.tool_calls)
        content = _truncate(message.content, max_chars)
        if content:
            return f"assistant: {content}; requested tools: {calls}"
        return f"assistant requested tools: {calls}"

    if message.role == "tool" and message.tool_result is not None:
        result = message.tool_result
        prefix = f"tool result {result.tool_use_id}"
        if result.is_error:
            prefix += " error"
        return f"{prefix}: {_truncate(result.content, max_chars)}"

    thinking = _metadata_text(message, ("thinking", "reasoning", "thoughts"))
    content = _truncate(message.content, max_chars)
    if thinking:
        thinking = _truncate(thinking, max(40, max_chars // 2))
        if content:
            return f"{message.role}: {content}; thinking compressed: {thinking}"
        return f"{message.role} thinking compressed: {thinking}"
    return f"{message.role}: {content}"


def _metadata_text(message: Message, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = message.metadata.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return "." * max_chars
    return f"{text[: max_chars - 3].rstrip()}..."
