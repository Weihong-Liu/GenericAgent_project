"""Runtime skeleton for the engineered agent."""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import RuntimeSettings, resolve_runtime_settings
from .providers.base import ProviderSpec
from .providers.registry import build_provider_registry
from .runtime.messages import Message


@dataclass
class RuntimeState:
    session_id: str = "default"
    turn_count: int = 0
    model: str = ""
    provider_id: str = ""
    messages: list[Message] = field(default_factory=list)


class AgentRuntime:
    """Composition root for config, provider registry, and session state."""

    def __init__(self, settings: RuntimeSettings | None = None) -> None:
        self.settings = settings or resolve_runtime_settings()
        self.providers = build_provider_registry()
        provider = self.providers.resolve(self.settings.default_provider)
        self.state = RuntimeState(
            model=self.settings.default_model,
            provider_id=provider.id,
        )

    def current_provider(self) -> ProviderSpec:
        return self.providers.resolve(self.state.provider_id)

    def switch_model(self, model: str, provider: str | None = None) -> None:
        if provider:
            resolved = self.providers.resolve(provider)
            self.state.provider_id = resolved.id
        if model:
            self.state.model = model
