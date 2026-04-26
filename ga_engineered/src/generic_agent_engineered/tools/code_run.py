"""Python code execution tool."""

from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from generic_agent_engineered.runtime.messages import ToolCall, ToolResult

from .base import ToolPermission, ToolSchema, ToolSpec
from .path_security import PathSecurityError, WorkspacePolicy
from .shell import OutputCallback, StopSignal, _run_process, _timeout_seconds

CODE_RUN_SPEC = ToolSpec(
    schema=ToolSchema(
        name="code_run",
        description="Run a temporary Python script inside the workspace.",
        parameters={
            "type": "object",
            "properties": {
                "script": {"type": "string", "description": "Python source code to execute"},
                "cwd": {
                    "type": "string",
                    "description": "Workspace-relative working directory",
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds",
                    "default": 60,
                },
            },
            "required": ["script"],
        },
    ),
    permissions=(ToolPermission("python:execute", "execute temporary Python scripts"),),
)


@dataclass
class CodeRunTool:
    workspace_root: Path
    default_timeout: float = 60.0
    max_timeout: float = 600.0
    max_output_chars: int = 120_000
    stop_signal: StopSignal | None = None
    output_callback: OutputCallback | None = None

    @property
    def spec(self) -> ToolSpec:
        return CODE_RUN_SPEC

    async def run(self, tool_call: ToolCall) -> ToolResult:
        temp_path: Path | None = None
        try:
            policy = WorkspacePolicy(self.workspace_root)
            script = _required_str(tool_call.arguments, "script")
            cwd = _resolve_cwd(policy, tool_call.arguments.get("cwd"))
            timeout = _timeout_seconds(
                tool_call.arguments.get("timeout", self.default_timeout),
                max_timeout=self.max_timeout,
            )
            temp_path = _write_temp_script(script, policy.root)
            result = await _run_process(
                [sys.executable, "-X", "utf8", "-u", str(temp_path)],
                cwd=cwd,
                timeout=timeout,
                max_output_chars=self.max_output_chars,
                stop_signal=self.stop_signal,
                output_callback=self.output_callback,
            )
            metadata = {
                "cwd": policy.relative_path(cwd) or ".",
                "exit_code": result.exit_code,
                "timed_out": result.timed_out,
                "stopped": result.stopped,
                "truncated": result.truncated,
                "language": "python",
            }
            return ToolResult(
                tool_use_id=tool_call.id,
                content=(
                    f"status={_status(result.exit_code, result.timed_out, result.stopped)}\n"
                    f"exit_code={result.exit_code}\nstdout:\n{result.stdout}"
                ),
                is_error=result.exit_code != 0 or result.timed_out or result.stopped,
                metadata=metadata,
            )
        except (OSError, PathSecurityError, ValueError, TypeError) as exc:
            return ToolResult(
                tool_use_id=tool_call.id,
                content=str(exc),
                is_error=True,
                metadata={"error": exc.__class__.__name__},
            )
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)


def _write_temp_script(script: str, workspace_root: Path) -> Path:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".gae.py",
        prefix=".code-run-",
        dir=workspace_root,
        delete=False,
    ) as handle:
        handle.write(script)
        return Path(handle.name)


def _resolve_cwd(policy: WorkspacePolicy, raw_cwd: Any) -> Path:
    if raw_cwd in (None, ""):
        return policy.root
    if not isinstance(raw_cwd, str):
        raise TypeError("cwd must be a string")
    cwd = policy.resolve_path(raw_cwd)
    if not cwd.is_dir():
        raise FileNotFoundError(f"cwd does not exist: {raw_cwd}")
    return cwd


def _required_str(arguments: dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} is required")
    return value


def _status(exit_code: int | None, timed_out: bool, stopped: bool) -> str:
    if exit_code == 0 and not timed_out and not stopped:
        return "success"
    return "error"
