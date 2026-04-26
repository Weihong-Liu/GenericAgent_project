"""OpenAI Responses API provider client."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol

from .base import ChatMessage, ChatResponse, LLMProvider, ProviderSpec, StreamEvent, ToolCall
from .errors import ProviderAuthError, ProviderError, ProviderProtocolError, map_provider_exception
from .http import SSEJSONTransport
from .tools import parse_tool_arguments, to_openai_tools


class OpenAIResponsesTransport(Protocol):
    def stream_responses(self, payload: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        """Stream raw Responses API events."""
        ...


@dataclass(frozen=True)
class OpenAIResponsesHTTPTransport:
    base_url: str
    api_key: str

    async def stream_responses(self, payload: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        if not self.api_key:
            raise ProviderAuthError("OpenAI Responses transport requires an API key")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
        }
        async for event in SSEJSONTransport(self.base_url, "/responses", headers).stream(payload):
            yield event


class OpenAIResponsesProvider(LLMProvider):
    def __init__(
        self,
        spec: ProviderSpec,
        model: str,
        *,
        api_key: str = "",
        base_url: str | None = None,
        transport: OpenAIResponsesTransport | None = None,
    ) -> None:
        super().__init__(spec, model)
        self.api_key = api_key
        self.base_url = base_url or spec.base_url
        self.transport = transport or OpenAIResponsesHTTPTransport(self.base_url, api_key)

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        payload: dict[str, Any] = {
            "model": self.model,
            "input": _messages_to_input(messages),
            "stream": True,
        }
        if tools:
            payload["tools"] = to_openai_tools(tools)

        content_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        try:
            async for event in self.transport.stream_responses(payload):
                async for normalized in self._normalize_event(event, content_parts, tool_calls):
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
        tool_calls: list[ToolCall],
    ) -> AsyncIterator[StreamEvent]:
        event_type = event.get("type")
        if event_type == "response.output_text.delta":
            delta = _string(event.get("delta"))
            if delta:
                content_parts.append(delta)
                yield StreamEvent(kind="content_delta", delta=delta)
            return

        if event_type == "response.output_item.done":
            tool_call = _tool_call_from_output_item(event.get("item", {}))
            if tool_call is not None and _new_tool_call(tool_call, tool_calls):
                tool_calls.append(tool_call)
                yield StreamEvent(kind="tool_call", tool_call=tool_call)
            return

        if event_type == "response.completed":
            _merge_completed_response(event.get("response", {}), content_parts, tool_calls)
            return

        if event_type == "response.failed":
            error = event.get("error") or {}
            message = error.get("message") if isinstance(error, dict) else ""
            raise ProviderError(_string(message) or "OpenAI Responses request failed")


def _messages_to_input(messages: list[ChatMessage]) -> list[dict[str, str]]:
    return [{"role": message.role, "content": message.content} for message in messages]


def _tool_call_from_output_item(raw_item: Any) -> ToolCall | None:
    if not isinstance(raw_item, dict):
        return None
    if raw_item.get("type") not in {"function_call", "tool_call"}:
        return None

    name = _string(raw_item.get("name"))
    if not name:
        raise ProviderProtocolError("OpenAI tool call item did not include a name")
    tool_id = _string(raw_item.get("call_id")) or _string(raw_item.get("id")) or name
    arguments = parse_tool_arguments(raw_item.get("arguments"))
    return ToolCall(id=tool_id, name=name, arguments=arguments)


def _merge_completed_response(
    raw_response: Any,
    content_parts: list[str],
    tool_calls: list[ToolCall],
) -> None:
    if not isinstance(raw_response, dict):
        return
    output_text = _string(raw_response.get("output_text"))
    if output_text and not content_parts:
        content_parts.append(output_text)

    for item in raw_response.get("output", []) or []:
        tool_call = _tool_call_from_output_item(item)
        if tool_call is not None and _new_tool_call(tool_call, tool_calls):
            tool_calls.append(tool_call)
            continue
        _merge_message_item(item, content_parts)


def _merge_message_item(raw_item: Any, content_parts: list[str]) -> None:
    if not isinstance(raw_item, dict) or raw_item.get("type") != "message":
        return
    if content_parts:
        return
    for content in raw_item.get("content", []) or []:
        if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
            text = _string(content.get("text"))
            if text:
                content_parts.append(text)


def _new_tool_call(tool_call: ToolCall, tool_calls: list[ToolCall]) -> bool:
    signature = _tool_call_signature(tool_call)
    return all(
        existing.id != tool_call.id and _tool_call_signature(existing) != signature
        for existing in tool_calls
    )


def _tool_call_signature(tool_call: ToolCall) -> str:
    arguments = json.dumps(
        tool_call.arguments,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return f"{tool_call.name}:{arguments}"


def _string(value: Any) -> str:
    return value if isinstance(value, str) else ""
