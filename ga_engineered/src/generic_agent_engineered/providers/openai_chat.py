"""OpenAI-compatible Chat Completions provider client."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol

from .base import ChatMessage, ChatResponse, LLMProvider, ProviderSpec, StreamEvent, ToolCall
from .errors import ProviderAuthError, ProviderError, ProviderProtocolError, map_provider_exception
from .http import SSEJSONTransport
from .tools import parse_tool_arguments, to_openai_tools


class OpenAIChatTransport(Protocol):
    def stream_chat_completions(
        self,
        payload: dict[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream raw Chat Completions chunks."""
        ...


@dataclass(frozen=True)
class OpenAIChatHTTPTransport:
    base_url: str
    api_key: str

    async def stream_chat_completions(
        self,
        payload: dict[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        if not self.api_key:
            raise ProviderAuthError("OpenAI-compatible chat transport requires an API key")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
        }
        async for event in SSEJSONTransport(self.base_url, "/chat/completions", headers).stream(
            payload
        ):
            yield event


class OpenAIChatProvider(LLMProvider):
    def __init__(
        self,
        spec: ProviderSpec,
        model: str,
        *,
        api_key: str = "",
        base_url: str | None = None,
        transport: OpenAIChatTransport | None = None,
    ) -> None:
        super().__init__(spec, model)
        self.api_key = api_key
        self.base_url = base_url or spec.base_url
        self.transport = transport or OpenAIChatHTTPTransport(self.base_url, api_key)

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": _messages_to_openai(messages),
            "stream": True,
        }
        if tools:
            payload["tools"] = to_openai_tools(tools)

        content_parts: list[str] = []
        tool_buffers: dict[int, _ToolBuffer] = {}
        try:
            async for chunk in self.transport.stream_chat_completions(payload):
                choice = _first_choice(chunk)
                delta = choice.get("delta", {}) if isinstance(choice, dict) else {}
                if not isinstance(delta, dict):
                    continue

                content_delta = _string(delta.get("content"))
                if content_delta:
                    content_parts.append(content_delta)
                    yield StreamEvent(kind="content_delta", delta=content_delta)

                for raw_tool_delta in delta.get("tool_calls", []) or []:
                    _merge_tool_delta(tool_buffers, raw_tool_delta)
        except ProviderError:
            raise
        except Exception as exc:
            raise map_provider_exception(exc, provider_id=self.spec.id) from exc

        tool_calls = [_buffer_to_tool_call(buffer) for _, buffer in sorted(tool_buffers.items())]
        response = ChatResponse(
            content="".join(content_parts),
            tool_calls=tuple(tool_calls),
        )
        for tool_call in tool_calls:
            yield StreamEvent(kind="tool_call", tool_call=tool_call)
        yield StreamEvent(kind="message_done", response=response)


@dataclass
class _ToolBuffer:
    id: str = ""
    name: str = ""
    arguments: str = ""


def _messages_to_openai(messages: list[ChatMessage]) -> list[dict[str, str]]:
    return [{"role": message.role, "content": message.content} for message in messages]


def _first_choice(chunk: dict[str, Any]) -> dict[str, Any]:
    choices = chunk.get("choices")
    if not isinstance(choices, list) or not choices:
        return {}
    choice = choices[0]
    return choice if isinstance(choice, dict) else {}


def _merge_tool_delta(tool_buffers: dict[int, _ToolBuffer], raw_tool_delta: Any) -> None:
    if not isinstance(raw_tool_delta, dict):
        return
    index = raw_tool_delta.get("index", 0)
    if not isinstance(index, int):
        index = 0
    buffer = tool_buffers.setdefault(index, _ToolBuffer())
    buffer.id = _string(raw_tool_delta.get("id")) or buffer.id

    function_delta = raw_tool_delta.get("function", {})
    if not isinstance(function_delta, dict):
        return
    buffer.name = _string(function_delta.get("name")) or buffer.name
    buffer.arguments += _string(function_delta.get("arguments"))


def _buffer_to_tool_call(buffer: _ToolBuffer) -> ToolCall:
    if not buffer.name:
        raise ProviderProtocolError("OpenAI chat tool call did not include a name")
    return ToolCall(
        id=buffer.id or buffer.name,
        name=buffer.name,
        arguments=parse_tool_arguments(buffer.arguments),
    )


def _string(value: Any) -> str:
    return value if isinstance(value, str) else ""
