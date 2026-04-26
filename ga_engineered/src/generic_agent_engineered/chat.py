"""Provider-backed chat turn service."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from generic_agent_engineered.auth.store import AuthStore
from generic_agent_engineered.engine import AgentRuntime
from generic_agent_engineered.providers.base import ProviderSpec
from generic_agent_engineered.providers.errors import ProviderAuthError, ProviderError
from generic_agent_engineered.providers.factory import create_provider_client
from generic_agent_engineered.runtime.agent_loop import (
    AgentLoop,
    AgentLoopConfig,
    ChatProvider,
    EventSink,
    MissingToolExecutorError,
    StopSignal,
)
from generic_agent_engineered.runtime.events import RuntimeEvent
from generic_agent_engineered.runtime.messages import Message
from generic_agent_engineered.tools import ToolRegistry, build_default_tool_registry


@dataclass(frozen=True)
class ChatTurnResult:
    content: str
    is_error: bool = False
    status: str = "completed"
    provider: str = ""
    model: str = ""
    messages: tuple[Message, ...] = ()
    events: tuple[RuntimeEvent, ...] = ()
    error_type: str = ""


class ChatTurnService:
    """Run one user prompt through the configured provider and AgentLoop."""

    def __init__(
        self,
        runtime: AgentRuntime,
        *,
        provider: ChatProvider | None = None,
        tool_registry: ToolRegistry | None = None,
        environment: Mapping[str, str] | None = None,
        max_turns: int = 8,
    ) -> None:
        self.runtime = runtime
        self.provider = provider
        self.tool_registry = tool_registry or build_default_tool_registry(runtime)
        self.environment = dict(environment or {})
        self.max_turns = max_turns
        # When set by callers (e.g. the gateway's ApprovalGate) AgentLoop
        # dispatches tool calls through this object instead of the raw
        # registry. ``schemas()`` / ``list_tools()`` always come from the
        # registry so the LLM sees the same tool set regardless.
        self.tool_executor: object | None = None

    async def run_turn(
        self,
        prompt: str,
        *,
        event_sink: EventSink | None = None,
        stop_signal: StopSignal | None = None,
    ) -> ChatTurnResult:
        line = prompt.strip()
        provider_spec = self.runtime.current_provider()
        model = self.runtime.state.model
        if not line:
            return ChatTurnResult(
                content="Prompt is empty.",
                is_error=True,
                status="empty_prompt",
                provider=provider_spec.id,
                model=model,
                error_type="ValueError",
            )

        history = [*self.runtime.state.messages, Message.user(line)]
        executor = self.tool_executor if self.tool_executor is not None else self.tool_registry
        try:
            loop = AgentLoop(
                self._build_provider(provider_spec, model),
                tool_executor=executor,  # type: ignore[arg-type]
                tools=self.tool_registry.schemas(),
                config=AgentLoopConfig(max_turns=self.max_turns),
                event_sink=event_sink,
                stop_signal=stop_signal,
            )
            result = await loop.run(history)
        except ProviderAuthError as exc:
            return self._error_result(provider_spec, model, exc, error_type="ProviderAuthError")
        except ProviderError as exc:
            return self._error_result(provider_spec, model, exc, error_type=exc.__class__.__name__)
        except MissingToolExecutorError as exc:
            return self._error_result(
                provider_spec,
                model,
                exc,
                error_type="MissingToolExecutorError",
            )

        if result.completed and result.final_message is not None:
            self.runtime.state.messages = list(result.messages)
            self.runtime.state.turn_count += 1
            return ChatTurnResult(
                content=result.final_message.content,
                status=result.status,
                provider=provider_spec.id,
                model=model,
                messages=result.messages,
                events=result.events,
            )

        content = f"Chat stopped: {result.retry_reason or result.status}"
        self.runtime.state.messages = list(result.messages)
        self.runtime.state.turn_count += 1
        return ChatTurnResult(
            content=content,
            is_error=True,
            status=result.status,
            provider=provider_spec.id,
            model=model,
            messages=result.messages,
            events=result.events,
            error_type="AgentLoopStopped",
        )

    def _build_provider(self, spec: ProviderSpec, model: str) -> ChatProvider:
        if self.provider is not None:
            return self.provider

        auth_store = AuthStore(self.runtime.settings.auth_path)
        env = _effective_environment(self.runtime, self.environment)
        api_key = _resolve_api_key(spec, env, auth_store)
        if spec.auth_kind == "api_key" and not api_key:
            raise ProviderAuthError(_missing_api_key_message(spec))
        if spec.auth_kind == "oauth_pkce":
            _require_oauth_token(spec, auth_store)

        base_url = None
        if spec.base_url_env_var:
            base_url = env.get(spec.base_url_env_var, "").strip() or None
        return create_provider_client(
            spec,
            model,
            api_key=api_key,
            base_url=base_url,
            auth_store=auth_store,
            auth_path=self.runtime.settings.auth_path,
        )

    def _error_result(
        self,
        spec: ProviderSpec,
        model: str,
        exc: BaseException,
        *,
        error_type: str,
    ) -> ChatTurnResult:
        return ChatTurnResult(
            content=str(exc),
            is_error=True,
            status="error",
            provider=spec.id,
            model=model,
            messages=tuple(self.runtime.state.messages),
            error_type=error_type,
        )


def _effective_environment(
    runtime: AgentRuntime,
    overlay: Mapping[str, str],
) -> dict[str, str]:
    env = dict(os.environ)
    env.update(runtime.settings.environment)
    env.update(overlay)
    return env


def _resolve_api_key(
    spec: ProviderSpec,
    env: Mapping[str, str],
    auth_store: AuthStore,
) -> str:
    for name in spec.api_key_env_vars:
        value = env.get(name, "").strip()
        if value:
            return value

    record = auth_store.get(spec.id)
    if record is not None and record.api_key:
        return record.api_key
    return ""


def _require_oauth_token(spec: ProviderSpec, auth_store: AuthStore) -> None:
    record = auth_store.get(spec.id)
    if record is None or not record.access_token:
        raise ProviderAuthError(
            f"Provider {spec.id} requires OAuth auth. Run /login {spec.id} --headless first."
        )


def _missing_api_key_message(spec: ProviderSpec) -> str:
    names = ", ".join(spec.api_key_env_vars) if spec.api_key_env_vars else "an API key"
    return (
        f"Provider {spec.id} requires {names}. Set it in the shell, "
        ".generic-agent/settings.json env, or the auth store."
    )
