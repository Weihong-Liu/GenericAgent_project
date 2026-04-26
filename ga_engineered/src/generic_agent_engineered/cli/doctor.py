"""Doctor command diagnostics."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from generic_agent_engineered import __version__
from generic_agent_engineered.auth.store import AuthStore
from generic_agent_engineered.commands import COMMAND_REGISTRY
from generic_agent_engineered.engine import AgentRuntime
from generic_agent_engineered.tools import (
    CODE_RUN_SPEC,
    FILE_PATCH_SPEC,
    FILE_READ_SPEC,
    FILE_WRITE_SPEC,
    SHELL_SPEC,
    WEB_EXECUTE_JS_SPEC,
    WEB_SCAN_SPEC,
    ToolSpec,
)

CheckStatus = str


@dataclass(frozen=True)
class DiagnosticCheck:
    name: str
    status: CheckStatus
    detail: str

    @property
    def is_error(self) -> bool:
        return self.status == "error"


@dataclass(frozen=True)
class DiagnosticReport:
    version: str
    checks: tuple[DiagnosticCheck, ...]

    @property
    def ok(self) -> bool:
        return not any(check.is_error for check in self.checks)


def build_diagnostic_report(runtime: AgentRuntime | None = None) -> DiagnosticReport:
    resolved_runtime = runtime or AgentRuntime()
    checks = (
        _provider_check(resolved_runtime),
        _home_check(resolved_runtime),
        _auth_check(resolved_runtime),
        _state_check(resolved_runtime),
        _tool_check(),
        _command_check(),
    )
    return DiagnosticReport(version=__version__, checks=checks)


def render_diagnostic_report(report: DiagnosticReport | None = None) -> str:
    resolved_report = report or build_diagnostic_report()
    lines = ["GenericAgent Engineered", f"  version      {resolved_report.version}"]
    for check in resolved_report.checks:
        lines.append(f"  {check.name:<12} {check.status:<7} {check.detail}")
    lines.append(f"  status       {'scaffold-ok' if resolved_report.ok else 'needs-attention'}")
    return "\n".join(lines)


def run_doctor(runtime: AgentRuntime | None = None) -> int:
    report = build_diagnostic_report(runtime)
    print(render_diagnostic_report(report))
    return 0 if report.ok else 1


def _provider_check(runtime: AgentRuntime) -> DiagnosticCheck:
    provider = runtime.current_provider()
    return DiagnosticCheck(
        "provider",
        "ok",
        f"{provider.id} ({provider.transport}) model={runtime.state.model}",
    )


def _home_check(runtime: AgentRuntime) -> DiagnosticCheck:
    home = runtime.settings.home
    if home.exists() and not home.is_dir():
        return DiagnosticCheck("home", "error", f"{home} is not a directory")
    if home.exists():
        return DiagnosticCheck("home", "ok", str(home))
    if home.parent.exists():
        return DiagnosticCheck("home", "ok", f"{home} (ready to create)")
    return DiagnosticCheck("home", "error", f"parent does not exist: {home.parent}")


def _auth_check(runtime: AgentRuntime) -> DiagnosticCheck:
    auth_path = runtime.settings.auth_path
    if not auth_path.exists():
        return DiagnosticCheck("auth", "warn", f"{auth_path} (not logged in)")
    try:
        records = AuthStore(auth_path).load_all()
    except Exception as exc:
        return DiagnosticCheck("auth", "error", f"{auth_path} unreadable: {exc}")
    return DiagnosticCheck("auth", "ok", f"{auth_path} providers={len(records)}")


def _state_check(runtime: AgentRuntime) -> DiagnosticCheck:
    state_dir = runtime.settings.state_dir
    if state_dir.exists() and not state_dir.is_dir():
        return DiagnosticCheck("state", "error", f"{state_dir} is not a directory")
    if state_dir.exists():
        return DiagnosticCheck("state", "ok", str(state_dir))
    if _can_create_under(state_dir.parent):
        return DiagnosticCheck("state", "ok", f"{state_dir} (ready to create)")
    return DiagnosticCheck("state", "error", f"parent is not writable: {state_dir.parent}")


def _tool_check() -> DiagnosticCheck:
    names = sorted(spec.name for spec in _core_tool_specs())
    return DiagnosticCheck("tools", "ok", f"{len(names)} core tools: {', '.join(names)}")


def _command_check() -> DiagnosticCheck:
    return DiagnosticCheck("commands", "ok", f"{len(COMMAND_REGISTRY)} commands registered")


def _core_tool_specs() -> Iterable[ToolSpec]:
    return (
        FILE_READ_SPEC,
        FILE_WRITE_SPEC,
        FILE_PATCH_SPEC,
        SHELL_SPEC,
        CODE_RUN_SPEC,
        WEB_SCAN_SPEC,
        WEB_EXECUTE_JS_SPEC,
    )


def _can_create_under(path: Path) -> bool:
    if path.exists():
        return path.is_dir()
    return path.parent.exists() and path.parent.is_dir()
