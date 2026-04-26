"""Provider abstractions for model backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal

from generic_agent_engineered.runtime.events import StreamEvent
from generic_agent_engineered.runtime.messages import ChatMessage, ChatResponse, ToolCall

TransportKind = Literal["openai_chat", "openai_responses", "anthropic_messages", "codex_oauth"]
AuthKind = Literal["api_key", "oauth_pkce", "oauth_device", "external_process"]


@dataclass(frozen=True)
class ProviderSpec:
    """Static provider metadata used for auth and client construction."""

    id: str
    name: str
    transport: TransportKind
    base_url: str
    auth_kind: AuthKind = "api_key"
    api_key_env_vars: tuple[str, ...] = ()
    base_url_env_var: str | None = None
    aliases: tuple[str, ...] = ()
    supports_tools: bool = True
    supports_streaming: bool = True
    notes: str = ""


class LLMProvider(ABC):
    """Strategy interface implemented by concrete provider clients."""

    def __init__(self, spec: ProviderSpec, model: str) -> None:
        self.spec = spec
        self.model = model

    @abstractmethod
    def stream_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Yield normalized provider stream events."""

    async def complete_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatResponse:
        """Collect a streaming response into one normalized response."""
        content_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        response: ChatResponse | None = None
        async for event in self.stream_chat(messages, tools):
            if event.kind == "content_delta":
                content_parts.append(event.delta)
            elif event.kind == "tool_call" and event.tool_call is not None:
                tool_calls.append(event.tool_call)
            elif event.kind == "message_done" and event.response is not None:
                response = event.response
        return response or ChatResponse(
            content="".join(content_parts),
            tool_calls=tuple(tool_calls),
        )


class ProviderRegistry:
    """Lookup table for provider specs and aliases."""

    def __init__(self, specs: list[ProviderSpec]) -> None:
        self._by_id: dict[str, ProviderSpec] = {}
        self._aliases: dict[str, str] = {}
        for spec in specs:
            self.register(spec)

    def register(self, spec: ProviderSpec) -> None:
        if spec.id in self._by_id:
            raise ValueError(f"duplicate provider id: {spec.id}")
        self._by_id[spec.id] = spec
        self._aliases[spec.id] = spec.id
        for alias in spec.aliases:
            self._aliases[alias] = spec.id

    def resolve(self, name: str) -> ProviderSpec:
        key = name.strip().lower()
        provider_id = self._aliases.get(key)
        if not provider_id:
            raise KeyError(f"unknown provider: {name}")
        return self._by_id[provider_id]

    def list(self) -> list[ProviderSpec]:
        return list(self._by_id.values())
