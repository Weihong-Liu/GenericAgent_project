"""Provider-neutral agent loop."""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from .compaction import CompactionConfig, compact_history_if_needed
from .events import RuntimeEvent
from .messages import ChatResponse, Message, ToolCall, ToolResult
from .token_budget import TokenBudget

AgentLoopStatus = Literal["completed", "stopped", "max_turns_exceeded"]
StopSignal = Callable[[], bool]
ToolHandler = Callable[[ToolCall], str | dict[str, Any] | ToolResult | Awaitable[Any]]
EventSink = Callable[[RuntimeEvent], Awaitable[None] | None]


class ToolExecutor(Protocol):
    async def run(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call and return a provider-neutral result."""


class ChatProvider(Protocol):
    def stream_chat(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[RuntimeEvent]:
        """Yield provider-neutral runtime events."""


class AgentLoopError(RuntimeError):
    """Base AgentLoop error."""


class MissingToolExecutorError(AgentLoopError):
    """Raised when the model asks for tools but no executor is available."""


@dataclass(frozen=True)
class AgentLoopConfig:
    max_turns: int = 8
    token_budget: TokenBudget | None = None
    compaction: CompactionConfig = field(default_factory=CompactionConfig)

    def __post_init__(self) -> None:
        if self.max_turns < 1:
            raise ValueError("max_turns must be at least 1")


@dataclass(frozen=True)
class AgentLoopResult:
    status: AgentLoopStatus
    messages: tuple[Message, ...]
    events: tuple[RuntimeEvent, ...]
    final_message: Message | None = None
    retry_reason: str | None = None
    turns: int = 0

    @property
    def completed(self) -> bool:
        return self.status == "completed"


@dataclass
class FunctionToolExecutor:
    handlers: dict[str, ToolHandler] = field(default_factory=dict)

    async def run(self, tool_call: ToolCall) -> ToolResult:
        handler = self.handlers.get(tool_call.name)
        if handler is None:
            return ToolResult(
                tool_use_id=tool_call.id,
                content=f"unknown tool: {tool_call.name}",
                is_error=True,
            )

        raw_result = handler(tool_call)
        if inspect.isawaitable(raw_result):
            raw_result = await raw_result
        return _coerce_tool_result(tool_call, raw_result)


class AgentLoop:
    def __init__(
        self,
        provider: ChatProvider,
        *,
        tool_executor: ToolExecutor | None = None,
        tools: list[dict[str, Any]] | None = None,
        config: AgentLoopConfig | None = None,
        stop_signal: StopSignal | None = None,
        event_sink: EventSink | None = None,
    ) -> None:
        self.provider = provider
        self.tool_executor = tool_executor
        self.tools = tools or []
        self.config = config or AgentLoopConfig()
        self.stop_signal = stop_signal or (lambda: False)
        self.event_sink = event_sink

    async def _emit(self, event: RuntimeEvent, events: list[RuntimeEvent]) -> None:
        events.append(event)
        if self.event_sink is None:
            return
        result = self.event_sink(event)
        if inspect.isawaitable(result):
            await result

    async def run(self, messages: list[Message] | tuple[Message, ...]) -> AgentLoopResult:
        history = list(messages)
        events: list[RuntimeEvent] = []

        for turn in range(1, self.config.max_turns + 1):
            if self.stop_signal():
                return await self._stopped(history, events, turn=turn)

            self._compact_history(history, turn=turn)
            await self._emit(RuntimeEvent.turn_started(turn), events)
            try:
                response = await self._collect_provider_response(history, events, turn=turn)
            except _StopLoop:
                return await self._stopped(history, events, turn=turn)
            assistant_message = response.to_message()
            history.append(assistant_message)

            if not response.tool_calls:
                await self._emit(
                    RuntimeEvent.turn_finished(turn, reason="final_response"),
                    events,
                )
                return AgentLoopResult(
                    status="completed",
                    messages=tuple(history),
                    events=tuple(events),
                    final_message=assistant_message,
                    turns=turn,
                )

            try:
                await self._execute_tool_calls(response.tool_calls, history, events, turn=turn)
            except _StopLoop:
                return await self._stopped(history, events, turn=turn)
            await self._emit(RuntimeEvent.turn_finished(turn, reason="tool_calls"), events)

        await self._emit(
            RuntimeEvent.loop_stopped(
                reason="max_turns_exceeded",
                turn=self.config.max_turns,
            ),
            events,
        )
        return AgentLoopResult(
            status="max_turns_exceeded",
            messages=tuple(history),
            events=tuple(events),
            retry_reason="max_turns_exceeded",
            turns=self.config.max_turns,
        )

    async def _collect_provider_response(
        self,
        history: list[Message],
        events: list[RuntimeEvent],
        *,
        turn: int,
    ) -> ChatResponse:
        content_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        response: ChatResponse | None = None

        async for event in self.provider.stream_chat(history, self.tools):
            await self._emit(event, events)
            if event.kind == "content_delta":
                content_parts.append(event.delta)
            elif event.kind == "tool_call" and event.tool_call is not None:
                tool_calls.append(event.tool_call)
            elif event.kind == "message_done" and event.response is not None:
                response = event.response

            if self.stop_signal():
                await self._emit(
                    RuntimeEvent.turn_finished(turn, reason="stop_signal"),
                    events,
                )
                raise _StopLoop

        return response or ChatResponse(
            content="".join(content_parts),
            tool_calls=tuple(tool_calls),
        )

    async def _execute_tool_calls(
        self,
        tool_calls: tuple[ToolCall, ...],
        history: list[Message],
        events: list[RuntimeEvent],
        *,
        turn: int,
    ) -> None:
        if self.tool_executor is None:
            raise MissingToolExecutorError("tool calls require a ToolExecutor")

        for tool_call in tool_calls:
            if self.stop_signal():
                await self._emit(
                    RuntimeEvent.turn_finished(turn, reason="stop_signal"),
                    events,
                )
                raise _StopLoop
            tool_result = await self.tool_executor.run(tool_call)
            history.append(Message.tool(tool_result))
            await self._emit(RuntimeEvent.from_tool_result(tool_result), events)

    def _compact_history(self, history: list[Message], *, turn: int) -> None:
        if self.config.token_budget is None:
            return

        result = compact_history_if_needed(
            history,
            budget=self.config.token_budget,
            config=self.config.compaction,
            reason=f"before_turn_{turn}",
        )
        if result.changed:
            history[:] = list(result.messages)

    async def _stopped(
        self,
        history: list[Message],
        events: list[RuntimeEvent],
        *,
        turn: int,
    ) -> AgentLoopResult:
        await self._emit(RuntimeEvent.loop_stopped(reason="stop_signal", turn=turn), events)
        return AgentLoopResult(
            status="stopped",
            messages=tuple(history),
            events=tuple(events),
            retry_reason="stop_signal",
            turns=turn - 1,
        )


class _StopLoop(Exception):
    pass


def _coerce_tool_result(tool_call: ToolCall, raw_result: Any) -> ToolResult:
    if isinstance(raw_result, ToolResult):
        return raw_result
    if isinstance(raw_result, dict):
        content = raw_result.get("content")
        if content is None:
            content = raw_result
        return ToolResult(tool_use_id=tool_call.id, content=str(content))
    return ToolResult(tool_use_id=tool_call.id, content=str(raw_result))
