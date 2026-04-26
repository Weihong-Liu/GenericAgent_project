"""Tool approval store + async gate.

The store persists ``always-allow`` decisions to
``$GENERIC_AGENT_HOME/approvals.json`` so the user does not have to
re-approve the same tool every session. The gate wraps the tool
registry: for tools whose name appears in ``HIGH_RISK_TOOLS`` we ask
the frontend, await a decision, and either pass the call through or
return a rejection ToolResult.

The waiter API is intentionally simple — ``request_decision`` returns
an asyncio.Future the caller can await; the gateway sets the result
when the chat.approve RPC arrives. ``yolo`` mode short-circuits the
whole gate.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from generic_agent_engineered.runtime.messages import ToolCall, ToolResult

ApprovalDecision = Literal["allow_once", "allow_always", "deny"]

HIGH_RISK_TOOLS: frozenset[str] = frozenset(
    {
        "shell",
        "code_run",
        "file_write",
        "file_patch",
    }
)


@dataclass
class ApprovalStore:
    """Persistent ``always-allow`` set keyed by tool name."""

    path: Path
    always_allow: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, path: Path) -> ApprovalStore:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return cls(path=path, always_allow=set())
        names = raw.get("always_allow", [])
        if not isinstance(names, list):
            names = []
        return cls(path=path, always_allow={str(name) for name in names if isinstance(name, str)})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"always_allow": sorted(self.always_allow)}
        # Atomic write to keep the file consistent on crash.
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)

    def is_always_allowed(self, tool_name: str) -> bool:
        return tool_name in self.always_allow

    def add_always_allow(self, tool_name: str) -> None:
        self.always_allow.add(tool_name)
        self.save()

    def remove_always_allow(self, tool_name: str) -> bool:
        if tool_name not in self.always_allow:
            return False
        self.always_allow.remove(tool_name)
        self.save()
        return True

    def clear(self) -> None:
        self.always_allow.clear()
        self.save()


@dataclass
class PendingApproval:
    """An in-flight approval request awaiting a frontend decision."""

    tool_use_id: str
    name: str
    arguments_preview: str
    future: asyncio.Future[ApprovalDecision]


class ApprovalGate:
    """Thin tool-executor wrapper that gates risky tools on user approval."""

    def __init__(
        self,
        *,
        inner: object,
        store: ApprovalStore,
        request_decision: Callable[[PendingApproval], Awaitable[None]],
        yolo: bool = False,
    ) -> None:
        self._inner = inner
        self._store = store
        self._request_decision = request_decision
        self.yolo = yolo
        self._pending: dict[str, asyncio.Future[ApprovalDecision]] = {}

    async def run(self, tool_call: ToolCall) -> ToolResult:
        decision = await self._decide(tool_call)
        if decision == "deny":
            return ToolResult(
                tool_use_id=tool_call.id,
                content=f"tool {tool_call.name} denied by user",
                is_error=True,
            )
        if decision == "allow_always":
            self._store.add_always_allow(tool_call.name)
        return await self._inner.run(tool_call)  # type: ignore[attr-defined]

    async def _decide(self, tool_call: ToolCall) -> ApprovalDecision:
        if self.yolo:
            return "allow_once"
        if tool_call.name not in HIGH_RISK_TOOLS:
            return "allow_once"
        if self._store.is_always_allowed(tool_call.name):
            return "allow_once"

        loop = asyncio.get_running_loop()
        future: asyncio.Future[ApprovalDecision] = loop.create_future()
        self._pending[tool_call.id] = future
        try:
            preview = _preview_arguments(tool_call.arguments)
            await self._request_decision(
                PendingApproval(
                    tool_use_id=tool_call.id,
                    name=tool_call.name,
                    arguments_preview=preview,
                    future=future,
                )
            )
            decision = await future
            return decision
        finally:
            self._pending.pop(tool_call.id, None)

    def resolve(self, tool_use_id: str, decision: ApprovalDecision) -> bool:
        """Set the decision for a pending request. Returns True on hit."""

        future = self._pending.get(tool_use_id)
        if future is None or future.done():
            return False
        future.set_result(decision)
        return True


def _preview_arguments(arguments: dict[str, object]) -> str:
    if not arguments:
        return ""
    try:
        rendered = json.dumps(arguments, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(arguments)[:160]
    return rendered if len(rendered) <= 160 else rendered[:157] + "..."


def default_approvals_path() -> Path:
    home = os.environ.get("GENERIC_AGENT_HOME", "").strip()
    if home:
        return Path(home).expanduser() / "approvals.json"
    return Path.home() / ".generic-agent" / "approvals.json"


__all__ = [
    "ApprovalDecision",
    "ApprovalGate",
    "ApprovalStore",
    "HIGH_RISK_TOOLS",
    "PendingApproval",
    "default_approvals_path",
]
