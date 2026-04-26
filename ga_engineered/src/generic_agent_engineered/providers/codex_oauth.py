"""Codex OAuth-backed provider client."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from generic_agent_engineered.auth.openai_oauth import PROVIDER_ID, OpenAICodexOAuthClient
from generic_agent_engineered.auth.store import AuthStore

from .base import ChatMessage, LLMProvider, ProviderSpec, StreamEvent
from .errors import ProviderAuthError
from .openai_responses import OpenAIResponsesHTTPTransport, OpenAIResponsesProvider


class CodexOAuthProvider(LLMProvider):
    """Responses-compatible provider that sources bearer auth from AuthStore."""

    def __init__(
        self,
        spec: ProviderSpec,
        model: str,
        *,
        auth_store: AuthStore | None = None,
        auth_path: Path | None = None,
        oauth_client: OpenAICodexOAuthClient | None = None,
        transport: Any | None = None,
    ) -> None:
        super().__init__(spec, model)
        self.auth_store = auth_store or (AuthStore(auth_path) if auth_path is not None else None)
        self.oauth_client = oauth_client or OpenAICodexOAuthClient()
        self.transport = transport

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        provider = OpenAIResponsesProvider(
            self.spec,
            self.model,
            base_url=self.spec.base_url,
            transport=self.transport or self._transport_from_auth_store(),
        )
        async for event in provider.stream_chat(messages, tools):
            yield event

    def _transport_from_auth_store(self) -> OpenAIResponsesHTTPTransport:
        if self.auth_store is None:
            raise ProviderAuthError("Codex OAuth provider requires an AuthStore")

        record = self.oauth_client.refresh_if_needed(self.auth_store)
        if record is None:
            record = self.auth_store.get(PROVIDER_ID)
        if record is None or not record.access_token:
            raise ProviderAuthError("Run /login openai-codex before using Codex OAuth")

        return OpenAIResponsesHTTPTransport(self.spec.base_url, record.access_token)
