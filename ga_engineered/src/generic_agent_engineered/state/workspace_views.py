"""Read-only session, task, and worktree summaries for TUI surfaces."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from generic_agent_engineered.engine import AgentRuntime

from .session_store import SessionStore


@dataclass(frozen=True)
class SessionSummary:
    id: str
    title: str
    parent_session_id: str | None
    provider: str
    model: str
    created_at: str
    updated_at: str
    message_count: int
    current: bool
    persisted: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "parent_session_id": self.parent_session_id,
            "provider": self.provider,
            "model": self.model,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": self.message_count,
            "current": self.current,
            "persisted": self.persisted,
        }


@dataclass(frozen=True)
class BackgroundTaskSummary:
    id: str
    label: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
        }


def list_session_summaries(runtime: AgentRuntime) -> list[SessionSummary]:
    """Return persisted sessions plus the active in-memory session."""

    current_id = runtime.state.session_id
    store = SessionStore.from_settings(runtime.settings)
    summaries: list[SessionSummary] = []

    try:
        records = store.list_sessions()
    except Exception:  # noqa: BLE001 - status surfaces must stay best-effort.
        records = []

    for record in records:
        try:
            message_count = len(store.load_stored_messages(record.id))
        except Exception:  # noqa: BLE001
            message_count = 0
        summaries.append(
            SessionSummary(
                id=record.id,
                title=record.title,
                parent_session_id=record.parent_session_id,
                provider=record.provider_id,
                model=record.model,
                created_at=record.created_at,
                updated_at=record.updated_at,
                message_count=message_count,
                current=record.id == current_id,
                persisted=True,
            )
        )

    if not any(summary.id == current_id for summary in summaries):
        summaries.insert(
            0,
            SessionSummary(
                id=current_id,
                title=current_id,
                parent_session_id=None,
                provider=runtime.state.provider_id,
                model=runtime.state.model,
                created_at="",
                updated_at="",
                message_count=len(runtime.state.messages),
                current=True,
                persisted=False,
            ),
        )
    return summaries


def resume_session(runtime: AgentRuntime, session_id: str) -> SessionSummary:
    """Switch the in-memory runtime to a persisted session when available."""

    target = session_id
    if target == "latest":
        summaries = list_session_summaries(runtime)
        target = summaries[0].id if summaries else runtime.state.session_id

    store = SessionStore.from_settings(runtime.settings)
    record = None
    try:
        record = store.get_session(target)
    except Exception:  # noqa: BLE001
        record = None

    runtime.state.session_id = target
    if record is not None:
        if record.provider_id:
            runtime.state.provider_id = record.provider_id
        if record.model:
            runtime.state.model = record.model
        try:
            runtime.state.messages = store.load_messages(target)
            runtime.state.turn_count = sum(
                1 for message in runtime.state.messages if message.role == "user"
            )
        except Exception:  # noqa: BLE001
            runtime.state.messages = []
            runtime.state.turn_count = 0

    return next(
        (summary for summary in list_session_summaries(runtime) if summary.id == target),
        SessionSummary(
            id=target,
            title=target,
            parent_session_id=None,
            provider=runtime.state.provider_id,
            model=runtime.state.model,
            created_at="",
            updated_at="",
            message_count=len(runtime.state.messages),
            current=True,
            persisted=False,
        ),
    )


def list_background_tasks(
    *,
    busy: bool,
    request_id: int | None,
) -> list[BackgroundTaskSummary]:
    if not busy:
        return []
    return [
        BackgroundTaskSummary(
            id=str(request_id or "chat"),
            label="chat.send",
            status="running",
            detail="The current assistant turn is still in flight.",
        )
    ]


def worktree_status(root: Path | None = None) -> dict[str, Any]:
    """Return a compact git worktree summary for the current workspace."""

    cwd = root or Path.cwd()
    top = _git(cwd, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return {
            "is_git": False,
            "path": str(cwd),
            "branch": "",
            "dirty": False,
            "changes": 0,
            "ahead": 0,
            "behind": 0,
        }

    root_path = top.stdout.strip() or str(cwd)
    branch = _git(cwd, "branch", "--show-current").stdout.strip()
    if not branch:
        branch = _git(cwd, "rev-parse", "--short", "HEAD").stdout.strip()
    porcelain = _git(cwd, "status", "--porcelain=v1").stdout.splitlines()
    ahead, behind = _ahead_behind(cwd)
    return {
        "is_git": True,
        "path": root_path,
        "branch": branch,
        "dirty": bool(porcelain),
        "changes": len(porcelain),
        "ahead": ahead,
        "behind": behind,
    }


def _ahead_behind(cwd: Path) -> tuple[int, int]:
    upstream = _git(cwd, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if upstream.returncode != 0:
        return 0, 0
    counts = _git(cwd, "rev-list", "--left-right", "--count", "HEAD...@{u}")
    parts = counts.stdout.strip().split()
    if len(parts) != 2:
        return 0, 0
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return 0, 0


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", *args),
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
