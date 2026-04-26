"""Anthropic Messages API provider client."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol

from .base import ChatMessage, ChatResponse, LLMProvider, ProviderSpec, StreamEvent, ToolCall
from .errors import ProviderAuthError, ProviderError, ProviderProtocolError, map_provider_exception
from .http import SSEJSONTransport
from .tools import parse_tool_arguments, to_anthropic_tools


class AnthropicMessagesTransport(Protocol):
    def stream_messages(self, payload: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        """Stream raw Anthropic Messages events."""
        ...


@dataclass(frozen=True)
class AnthropicMessagesHTTPTransport:
    base_url: str
    api_key: str
    anthropic_version: str = "2023-06-01"

    async def stream_messages(self, payload: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        if not self.api_key:
            raise ProviderAuthError("Anthropic Messages transport requires an API key")
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.anthropic_version,
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
        }
        async for event in SSEJSONTransport(self.base_url, "/v1/messages", headers).stream(payload):
            yield event


class AnthropicMessagesProvider(LLMProvider):
    def __init__(
        self,
        spec: ProviderSpec,
        model: str,
        *,
        api_key: str = "",
        base_url: str | None = None,
        max_tokens: int = 4096,
        transport: AnthropicMessagesTransport | None = None,
    ) -> None:
        super().__init__(spec, model)
        self.api_key = api_key
        self.base_url = base_url or spec.base_url
        self.max_tokens = max_tokens
        self.transport = transport or AnthropicMessagesHTTPTransport(self.base_url, api_key)

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        payload = _messages_payload(messages, self.model, self.max_tokens)
        if tools:
            payload["tools"] = to_anthropic_tools(tools)

        content_parts: list[str] = []
        tool_buffers: dict[int, _ContentBlockBuffer] = {}
        tool_calls: list[ToolCall] = []
        try:
            async for event in self.transport.stream_messages(payload):
                async for normalized in self._normalize_event(
                    event,
                    content_parts,
                    tool_buffers,
                    tool_calls,
                ):
                    yield normalized
        except ProviderError:
            raise
        except Exception as exc:
            raise map_provider_exception(exc, provider_id=self.spec.id) from exc

        response = ChatResponse(
            content="".join(content_parts),
            tool_calls=tuple(tool_calls),
        )
        yield StreamEvent(kind="message_done", response=response)

    async def _normalize_event(
        self,
        event: dict[str, Any],
        content_parts: list[str],
        tool_buffers: dict[int, _ContentBlockBuffer],
        tool_calls: list[ToolCall],
    ) -> AsyncIterator[StreamEvent]:
        event_type = event.get("type")
        index = _index(event)

        if event_type == "content_block_start":
            block = event.get("content_block", {})
            if not isinstance(block, dict):
                return
            if block.get("type") == "text":
                text = _string(block.get("text"))
                if text:
                    content_parts.append(text)
                    yield StreamEvent(kind="content_delta", delta=text)
                return
            if block.get("type") == "tool_use":
                tool_buffers[index] = _ContentBlockBuffer(
                    id=_string(block.get("id")),
                    name=_string(block.get("name")),
                    arguments=block.get("input") if isinstance(block.get("input"), dict) else None,
                )
                return

        if event_type == "content_block_delta":
            delta = event.get("delta", {})
            if not isinstance(delta, dict):
                return
            if delta.get("type") == "text_delta":
                text = _string(delta.get("text"))
                if text:
                    content_parts.append(text)
                    yield StreamEvent(kind="content_delta", delta=text)
                return
            if delta.get("type") == "input_json_delta":
                buffer = tool_buffers.setdefault(index, _ContentBlockBuffer())
                buffer.arguments_json += _string(delta.get("partial_json"))
                return

        if event_type == "content_block_stop" and index in tool_buffers:
            tool_call = _buffer_to_tool_call(tool_buffers.pop(index))
            tool_calls.append(tool_call)
            yield StreamEvent(kind="tool_call", tool_call=tool_call)


@dataclass
class _ContentBlockBuffer:
    id: str = ""
    name: str = ""
    arguments_json: str = ""
    arguments: dict[str, Any] | None = None


def _messages_payload(
    messages: list[ChatMessage],
    model: str,
    max_tokens: int,
) -> dict[str, Any]:
    system_parts: list[str] = []
    message_items: list[dict[str, str]] = []
    for message in messages:
        if message.role == "system":
            system_parts.append(message.content)
            continue
        role = message.role if message.role in {"user", "assistant"} else "user"
        message_items.append({"role": role, "content": message.content})

    payload: dict[str, Any] = {
        "model": model,
        "messages": message_items,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if system_parts:
        payload["system"] = "\n\n".join(system_parts)
    return payload


def _buffer_to_tool_call(buffer: _ContentBlockBuffer) -> ToolCall:
    if not buffer.name:
        raise ProviderProtocolError("Anthropic tool_use block did not include a name")
    raw_arguments: Any = buffer.arguments_json or buffer.arguments
    return ToolCall(
        id=buffer.id or buffer.name,
        name=buffer.name,
        arguments=parse_tool_arguments(raw_arguments),
    )


def _index(event: dict[str, Any]) -> int:
    value = event.get("index", 0)
    return value if isinstance(value, int) else 0


def _string(value: Any) -> str:
    return value if isinstance(value, str) else ""
