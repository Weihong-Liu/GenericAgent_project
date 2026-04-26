"""Status command formatting."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from generic_agent_engineered.engine import AgentRuntime


@dataclass(frozen=True)
class RuntimeStatus:
    session_id: str
    turn_count: int
    provider: str
    transport: str
    model: str
    home: Path
    state_dir: Path
    auth_path: Path
    language: str
    yolo: bool


def build_status(runtime: AgentRuntime | None = None) -> RuntimeStatus:
    resolved_runtime = runtime or AgentRuntime()
    provider = resolved_runtime.current_provider()
    return RuntimeStatus(
        session_id=resolved_runtime.state.session_id,
        turn_count=resolved_runtime.state.turn_count,
        provider=provider.id,
        transport=provider.transport,
        model=resolved_runtime.state.model,
        home=resolved_runtime.settings.home,
        state_dir=resolved_runtime.settings.state_dir,
        auth_path=resolved_runtime.settings.auth_path,
        language=resolved_runtime.settings.language,
        yolo=resolved_runtime.settings.yolo,
    )


def render_status(status: RuntimeStatus | None = None) -> str:
    resolved = status or build_status()
    return "\n".join(
        [
            "GenericAgent Engineered Status",
            f"  session      {resolved.session_id}",
            f"  turns        {resolved.turn_count}",
            f"  provider     {resolved.provider} ({resolved.transport})",
            f"  model        {resolved.model}",
            f"  home         {resolved.home}",
            f"  state        {resolved.state_dir}",
            f"  auth         {resolved.auth_path}",
            f"  language     {resolved.language}",
            f"  yolo         {str(resolved.yolo).lower()}",
        ]
    )
