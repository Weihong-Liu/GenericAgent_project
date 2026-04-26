"""Built-in provider registry.

The shape is inspired by Hermes' provider overlay model and free-code's
provider-gated command availability, but kept Python-native and explicit.
"""

from __future__ import annotations

from .base import ProviderRegistry, ProviderSpec

BUILTIN_PROVIDERS = [
    ProviderSpec(
        id="openai",
        name="OpenAI",
        transport="openai_responses",
        base_url="https://api.openai.com/v1",
        api_key_env_vars=("OPENAI_API_KEY",),
        base_url_env_var="OPENAI_BASE_URL",
        aliases=("oai", "gpt"),
    ),
    ProviderSpec(
        id="anthropic",
        name="Anthropic",
        transport="anthropic_messages",
        base_url="https://api.anthropic.com",
        api_key_env_vars=("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"),
        base_url_env_var="ANTHROPIC_BASE_URL",
        aliases=("claude",),
    ),
    ProviderSpec(
        id="openai-codex",
        name="OpenAI Codex OAuth",
        transport="codex_oauth",
        base_url="https://chatgpt.com/backend-api/codex",
        auth_kind="oauth_pkce",
        aliases=("codex", "chatgpt"),
        notes="Planned PKCE OAuth flow inspired by hermes-agent.",
    ),
    ProviderSpec(
        id="kimi",
        name="Kimi / Moonshot",
        transport="openai_chat",
        base_url="https://api.moonshot.ai/v1",
        api_key_env_vars=("KIMI_API_KEY", "MOONSHOT_API_KEY"),
        base_url_env_var="KIMI_BASE_URL",
        aliases=("moonshot", "kimi-coding"),
    ),
    ProviderSpec(
        id="minimax",
        name="MiniMax",
        transport="anthropic_messages",
        base_url="https://api.minimax.io/anthropic",
        api_key_env_vars=("MINIMAX_API_KEY",),
        base_url_env_var="MINIMAX_BASE_URL",
    ),
    ProviderSpec(
        id="dashscope",
        name="Alibaba DashScope",
        transport="openai_chat",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key_env_vars=("DASHSCOPE_API_KEY",),
        base_url_env_var="DASHSCOPE_BASE_URL",
        aliases=("qwen", "alibaba"),
    ),
    ProviderSpec(
        id="custom",
        name="Custom OpenAI-Compatible",
        transport="openai_chat",
        base_url="",
        api_key_env_vars=("GA_CUSTOM_API_KEY", "OPENAI_API_KEY"),
        base_url_env_var="GA_CUSTOM_BASE_URL",
        supports_tools=True,
    ),
]


def build_provider_registry() -> ProviderRegistry:
    return ProviderRegistry(BUILTIN_PROVIDERS)
