"""Token budget estimation for provider-neutral runtime messages."""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .messages import Message, ToolCall, ToolResult

MESSAGE_OVERHEAD_TOKENS = 4
TOOL_CALL_OVERHEAD_TOKENS = 8
TOOL_RESULT_OVERHEAD_TOKENS = 6


@dataclass(frozen=True)
class TokenBudget:
    max_tokens: int
    trigger_ratio: float = 0.8
    reserve_tokens: int = 0

    def __post_init__(self) -> None:
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be at least 1")
        if not 0 < self.trigger_ratio <= 1:
            raise ValueError("trigger_ratio must be between 0 and 1")
        if self.reserve_tokens < 0:
            raise ValueError("reserve_tokens must be non-negative")
        if self.reserve_tokens >= self.max_tokens:
            raise ValueError("reserve_tokens must be lower than max_tokens")

    @property
    def available_tokens(self) -> int:
        return self.max_tokens - self.reserve_tokens

    @property
    def trigger_tokens(self) -> int:
        return max(1, math.floor(self.available_tokens * self.trigger_ratio))


@dataclass(frozen=True)
class BudgetReport:
    estimated_tokens: int
    max_tokens: int
    trigger_tokens: int
    remaining_tokens: int
    over_budget: bool


def estimate_text_tokens(text: str) -> int:
    """Return a deterministic, dependency-free token estimate.

    This intentionally avoids provider-specific tokenizers. The heuristic is
    conservative enough for pre-flight compaction decisions and can be swapped
    for an exact tokenizer at the provider boundary later.
    """

    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def estimate_json_tokens(value: Any) -> int:
    return estimate_text_tokens(
        json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    )


def estimate_tool_call_tokens(tool_call: ToolCall) -> int:
    return (
        TOOL_CALL_OVERHEAD_TOKENS
        + estimate_text_tokens(tool_call.id)
        + estimate_text_tokens(tool_call.name)
        + estimate_json_tokens(tool_call.arguments)
    )


def estimate_tool_result_tokens(tool_result: ToolResult) -> int:
    total = (
        TOOL_RESULT_OVERHEAD_TOKENS
        + estimate_text_tokens(tool_result.tool_use_id)
        + estimate_text_tokens(tool_result.content)
    )
    if tool_result.metadata:
        total += estimate_json_tokens(tool_result.metadata)
    return total


def estimate_message_tokens(message: Message) -> int:
    total = MESSAGE_OVERHEAD_TOKENS + estimate_text_tokens(message.role)
    if message.role == "tool" and message.tool_result is not None:
        total += estimate_tool_result_tokens(message.tool_result)
    else:
        total += estimate_text_tokens(message.content)

    for tool_call in message.tool_calls:
        total += estimate_tool_call_tokens(tool_call)

    if message.metadata:
        total += estimate_json_tokens(message.metadata)
    return total


def estimate_messages_tokens(messages: Sequence[Message]) -> int:
    return sum(estimate_message_tokens(message) for message in messages)


def evaluate_token_budget(messages: Sequence[Message], budget: TokenBudget) -> BudgetReport:
    estimated = estimate_messages_tokens(messages)
    remaining = max(0, budget.available_tokens - estimated)
    return BudgetReport(
        estimated_tokens=estimated,
        max_tokens=budget.max_tokens,
        trigger_tokens=budget.trigger_tokens,
        remaining_tokens=remaining,
        over_budget=estimated >= budget.trigger_tokens,
    )


def should_compact(messages: Sequence[Message], budget: TokenBudget) -> bool:
    return evaluate_token_budget(messages, budget).over_budget
