"""Workspace-constrained shell command tool."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from generic_agent_engineered.runtime.messages import ToolCall, ToolResult

from .base import ToolPermission, ToolSchema, ToolSpec
from .path_security import PathSecurityError, WorkspacePolicy
from .permissions import ExecutionPolicy, decide_execution

StopSignal = Callable[[], bool]
OutputCallback = Callable[[str], None]


SHELL_SPEC = ToolSpec(
    schema=ToolSchema(
        name="shell",
        description="Execute a shell command inside the workspace with timeout and risk checks.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
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
            "required": ["command"],
        },
    ),
    permissions=(ToolPermission("shell:execute", "execute workspace shell commands"),),
)


@dataclass
class ShellTool:
    workspace_root: Path
    default_timeout: float = 60.0
    max_timeout: float = 600.0
    max_output_chars: int = 120_000
    yolo: bool = False
    stop_signal: StopSignal | None = None
    output_callback: OutputCallback | None = None

    @property
    def spec(self) -> ToolSpec:
        return SHELL_SPEC

    async def run(self, tool_call: ToolCall) -> ToolResult:
        try:
            command = _required_str(tool_call.arguments, "command")
            timeout = _timeout_seconds(
                tool_call.arguments.get("timeout", self.default_timeout),
                max_timeout=self.max_timeout,
            )
            policy = ExecutionPolicy(yolo=self.yolo)
            decision = decide_execution(command, policy)
            if not decision.allowed:
                return ToolResult(
                    tool_use_id=tool_call.id,
                    content=f"command requires approval: {', '.join(decision.risk.reasons)}",
                    is_error=True,
                    metadata={
                        "risk": decision.risk.level,
                        "reasons": decision.risk.reasons,
                        "approved_by_yolo": False,
                    },
                )

            workspace_policy = WorkspacePolicy(self.workspace_root)
            cwd = _resolve_cwd(workspace_policy, tool_call.arguments.get("cwd"))
            result = await _run_process(
                _shell_argv(command),
                cwd=cwd,
                timeout=timeout,
                max_output_chars=self.max_output_chars,
                stop_signal=self.stop_signal,
                output_callback=self.output_callback,
            )
            metadata = {
                "command": command,
                "cwd": workspace_policy.relative_path(cwd) or ".",
                "exit_code": result.exit_code,
                "timed_out": result.timed_out,
                "stopped": result.stopped,
                "truncated": result.truncated,
                "risk": decision.risk.level,
                "reasons": decision.risk.reasons,
                "approved_by_yolo": decision.approved_by_yolo,
            }
            return ToolResult(
                tool_use_id=tool_call.id,
                content=_format_process_result(result),
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


@dataclass(frozen=True)
class ProcessResult:
    stdout: str
    exit_code: int | None
    timed_out: bool = False
    stopped: bool = False
    truncated: bool = False
    duration_seconds: float = 0.0


async def _run_process(
    argv: list[str],
    *,
    cwd: Path,
    timeout: float,
    max_output_chars: int,
    stop_signal: StopSignal | None = None,
    output_callback: OutputCallback | None = None,
) -> ProcessResult:
    process = await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    chunks: list[str] = []
    truncated = False
    started_at = time.monotonic()

    async def read_output() -> None:
        nonlocal truncated
        if process.stdout is None:
            return
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace")
            output_callback and output_callback(text)
            current_size = sum(len(chunk) for chunk in chunks)
            if current_size < max_output_chars:
                remaining = max_output_chars - current_size
                chunks.append(text[:remaining])
                if len(text) > remaining:
                    truncated = True
            else:
                truncated = True

    reader_task = asyncio.create_task(read_output())
    wait_task = asyncio.create_task(process.wait())
    timed_out = False
    stopped = False

    while not wait_task.done():
        if stop_signal is not None and stop_signal():
            stopped = True
            await _terminate(process, wait_task)
            break
        if time.monotonic() - started_at >= timeout:
            timed_out = True
            await _terminate(process, wait_task)
            break
        await asyncio.sleep(0.05)

    exit_code = await wait_task
    await reader_task
    stdout = "".join(chunks)
    if truncated:
        stdout = f"{stdout.rstrip()}\n... [TRUNCATED]"
    if timed_out:
        stdout = f"{stdout.rstrip()}\n[Timeout] process killed after {timeout:g}s".strip()
    if stopped:
        stdout = f"{stdout.rstrip()}\n[Stopped] process killed by stop signal".strip()
    return ProcessResult(
        stdout=stdout,
        exit_code=exit_code,
        timed_out=timed_out,
        stopped=stopped,
        truncated=truncated,
        duration_seconds=time.monotonic() - started_at,
    )


async def _terminate(process: asyncio.subprocess.Process, wait_task: asyncio.Task[int]) -> None:
    if process.returncode is None:
        process.terminate()
    try:
        await asyncio.wait_for(asyncio.shield(wait_task), timeout=1)
    except TimeoutError:
        if process.returncode is None:
            process.kill()


def _format_process_result(result: ProcessResult) -> str:
    status = (
        "success"
        if result.exit_code == 0 and not result.timed_out and not result.stopped
        else "error"
    )
    return f"status={status}\nexit_code={result.exit_code}\nstdout:\n{result.stdout}"


def _shell_argv(command: str) -> list[str]:
    if os.name == "nt":
        return ["powershell", "-NoProfile", "-NonInteractive", "-Command", command]
    shell = "/bin/bash" if Path("/bin/bash").exists() else "/bin/sh"
    return [shell, "-lc", command]


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


def _timeout_seconds(value: Any, *, max_timeout: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("timeout must be a number")
    if value <= 0:
        raise ValueError("timeout must be positive")
    return min(float(value), max_timeout)
