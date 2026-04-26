"""Provider client construction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from generic_agent_engineered.auth.store import AuthStore

from .anthropic_messages import AnthropicMessagesProvider
from .base import LLMProvider, ProviderSpec
from .codex_oauth import CodexOAuthProvider
from .openai_chat import OpenAIChatProvider
from .openai_responses import OpenAIResponsesProvider


def create_provider_client(
    spec: ProviderSpec,
    model: str,
    *,
    api_key: str = "",
    base_url: str | None = None,
    auth_store: AuthStore | None = None,
    auth_path: Path | None = None,
    transport: Any | None = None,
) -> LLMProvider:
    if spec.transport == "openai_responses":
        return OpenAIResponsesProvider(
            spec,
            model,
            api_key=api_key,
            base_url=base_url,
            transport=transport,
        )
    if spec.transport == "openai_chat":
        return OpenAIChatProvider(
            spec,
            model,
            api_key=api_key,
            base_url=base_url,
            transport=transport,
        )
    if spec.transport == "anthropic_messages":
        return AnthropicMessagesProvider(
            spec,
            model,
            api_key=api_key,
            base_url=base_url,
            transport=transport,
        )
    if spec.transport == "codex_oauth":
        return CodexOAuthProvider(
            spec,
            model,
            auth_store=auth_store,
            auth_path=auth_path,
            transport=transport,
        )
    raise ValueError(f"Unsupported provider transport: {spec.transport}")
