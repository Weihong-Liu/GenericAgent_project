"""Compatibility surfaces for migrating legacy GenericAgent behavior."""

from __future__ import annotations

import importlib.util
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Literal

LegacyMigrationStatus = Literal["implemented", "planned", "deprecated"]
TaskHandler = Callable[[str], str]


@dataclass(frozen=True)
class LegacyToolMigration:
    name: str
    status: LegacyMigrationStatus
    replacement: str
    notes: str


@dataclass(frozen=True)
class LegacyEntrypointMigration:
    legacy: str
    replacement: str
    status: LegacyMigrationStatus
    notes: str


@dataclass(frozen=True)
class LegacyTaskResult:
    prompt: str
    output: str
    output_path: Path


@dataclass(frozen=True)
class LegacyReflectResult:
    script_path: Path
    triggered: bool
    prompt: str
    output: str
    log_path: Path | None = None


LEGACY_ENTRYPOINT_MIGRATIONS: dict[str, LegacyEntrypointMigration] = {
    "repl": LegacyEntrypointMigration(
        legacy="python agentmain.py",
        replacement="uv run gae chat",
        status="implemented",
        notes=(
            "Interactive slash-command gateway is available; provider-backed "
            "chat loop is wired through AgentLoop fixtures before live REPL integration."
        ),
    ),
    "task": LegacyEntrypointMigration(
        legacy="python agentmain.py --task IODIR --input PROMPT",
        replacement="uv run gae task IODIR --input PROMPT",
        status="implemented",
        notes="Preserves input.txt/output.txt file I/O contract for batch callers.",
    ),
    "reflect": LegacyEntrypointMigration(
        legacy="python agentmain.py --reflect SCRIPT",
        replacement="uv run gae reflect SCRIPT --once",
        status="implemented",
        notes=(
            "Loads a check() script once, captures triggered prompt output, "
            "and appends a reflect log."
        ),
    ),
}


LEGACY_TOOL_MIGRATIONS: dict[str, LegacyToolMigration] = {
    "code_run": LegacyToolMigration(
        name="code_run",
        status="implemented",
        replacement="tools.CodeRunTool",
        notes=(
            "Python execution is implemented; legacy powershell usage should "
            "migrate to ShellTool when shell approval UI lands."
        ),
    ),
    "file_read": LegacyToolMigration(
        name="file_read",
        status="implemented",
        replacement="tools.FileReadTool",
        notes=(
            "Preserves path/start/count/keyword/show_linenos behavior with "
            "workspace-root enforcement."
        ),
    ),
    "file_patch": LegacyToolMigration(
        name="file_patch",
        status="implemented",
        replacement="tools.FilePatchTool",
        notes="Preserves unique exact replacement semantics and safe file reference expansion.",
    ),
    "file_write": LegacyToolMigration(
        name="file_write",
        status="implemented",
        replacement="tools.FileWriteTool",
        notes=(
            "Preserves overwrite/append/prepend modes; content is passed "
            "explicitly instead of reply-block scraping."
        ),
    ),
    "web_scan": LegacyToolMigration(
        name="web_scan",
        status="implemented",
        replacement="tools.WebScanTool",
        notes=(
            "Legacy name is preserved behind BrowserBridge and HTML "
            "simplification output budgets."
        ),
    ),
    "web_execute_js": LegacyToolMigration(
        name="web_execute_js",
        status="implemented",
        replacement="tools.WebExecuteJsTool",
        notes=(
            "Legacy name is preserved; execution is isolated behind "
            "BrowserBridge for TMWebDriver/CDP adapters."
        ),
    ),
    "update_working_checkpoint": LegacyToolMigration(
        name="update_working_checkpoint",
        status="planned",
        replacement="state.SessionStore + runtime.Compaction + memory.MemoryService",
        notes=(
            "Short-term notepad behavior will be promoted through session "
            "metadata and reviewed memory writes."
        ),
    ),
    "ask_user": LegacyToolMigration(
        name="ask_user",
        status="planned",
        replacement="commands.CommandRouter + interactive REPL interrupt",
        notes=(
            "Human-question flow needs the live interactive REPL loop; no "
            "silent automatic substitute."
        ),
    ),
    "start_long_term_update": LegacyToolMigration(
        name="start_long_term_update",
        status="planned",
        replacement="skills.SkillCrystallizer + memory.MemoryService",
        notes=(
            "Long-term memory updates become reviewed SOP drafts instead of "
            "automatic background writes."
        ),
    ),
}


def legacy_tool_names() -> tuple[str, ...]:
    return tuple(sorted(LEGACY_TOOL_MIGRATIONS))


def run_task_io(
    task_dir: Path,
    *,
    input_text: str | None = None,
    handler: TaskHandler | None = None,
    output_name: str = "output.txt",
) -> LegacyTaskResult:
    """Run a single legacy-style task I/O round.

    This preserves the old `--task` contract: prompt text comes from `input.txt`
    unless provided explicitly, and the result is written to an output file with
    the old round delimiter.
    """
    directory = task_dir.expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    input_path = directory / "input.txt"
    if input_text is not None:
        input_path.write_text(input_text, encoding="utf-8")
    if not input_path.exists():
        raise FileNotFoundError(f"legacy task input not found: {input_path}")

    prompt = input_path.read_text(encoding="utf-8")
    output = (handler or _default_task_handler)(prompt).rstrip()
    output_path = directory / output_name
    output_path.write_text(f"{output}\n\n[ROUND END]\n", encoding="utf-8")
    return LegacyTaskResult(prompt=prompt, output=output, output_path=output_path)


def run_reflect_once(
    script_path: Path,
    *,
    handler: TaskHandler | None = None,
    log_dir: Path | None = None,
) -> LegacyReflectResult:
    """Run one legacy-style reflect `check()` cycle."""
    script = script_path.expanduser().resolve()
    module = _load_reflect_module(script)
    check = getattr(module, "check", None)
    if not callable(check):
        raise AttributeError(f"reflect script must define check(): {script}")

    task = check()
    if task is None:
        return LegacyReflectResult(script_path=script, triggered=False, prompt="", output="")

    prompt = str(task)
    output = (handler or _default_task_handler)(prompt).rstrip()
    target_log_dir = (log_dir or script.parent / "reflect_logs").expanduser()
    target_log_dir.mkdir(parents=True, exist_ok=True)
    log_path = target_log_dir / f"{script.stem}_{time.strftime('%Y-%m-%d')}.log"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{time.strftime('%m-%d %H:%M')}]\n{output}\n\n")

    on_done = getattr(module, "on_done", None)
    if callable(on_done):
        on_done(output)
    return LegacyReflectResult(
        script_path=script,
        triggered=True,
        prompt=prompt,
        output=output,
        log_path=log_path,
    )


def _default_task_handler(prompt: str) -> str:
    stripped = prompt.strip()
    if stripped.startswith("/"):
        from generic_agent_engineered.commands import CommandContext, CommandRouter

        return CommandRouter().dispatch(stripped, CommandContext()).content
    return (
        "GenericAgent Engineered received the legacy task prompt. "
        "Provider-backed execution is covered by AgentLoop compatibility fixtures "
        "and will be connected to the live REPL integration path."
    )


def _load_reflect_module(script: Path) -> ModuleType:
    if not script.is_file():
        raise FileNotFoundError(f"reflect script not found: {script}")
    spec = importlib.util.spec_from_file_location(f"gae_reflect_{script.stem}", script)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load reflect script: {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
