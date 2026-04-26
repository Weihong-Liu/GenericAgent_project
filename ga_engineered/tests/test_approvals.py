"""Unit tests for ApprovalStore + ApprovalGate."""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from generic_agent_engineered.runtime.approvals import (
    HIGH_RISK_TOOLS,
    ApprovalGate,
    ApprovalStore,
)
from generic_agent_engineered.runtime.messages import ToolCall, ToolResult


class FakeRegistry:
    def __init__(self) -> None:
        self.calls: list[ToolCall] = []

    async def run(self, tool_call: ToolCall) -> ToolResult:
        self.calls.append(tool_call)
        return ToolResult(
            tool_use_id=tool_call.id,
            content=f"ran {tool_call.name}",
        )


def _make_store(tmp_path: Path) -> ApprovalStore:
    return ApprovalStore.load(tmp_path / "approvals.json")


class ApprovalStoreTests(unittest.TestCase):
    def test_load_missing_file_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = _make_store(Path(tmp))
            self.assertEqual(store.always_allow, set())

    def test_save_and_reload_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = _make_store(Path(tmp))
            store.add_always_allow("shell")
            store.add_always_allow("file_write")
            reloaded = ApprovalStore.load(Path(tmp) / "approvals.json")
            self.assertEqual(reloaded.always_allow, {"shell", "file_write"})

    def test_remove_and_clear_always_allow_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = _make_store(Path(tmp))
            store.add_always_allow("shell")
            store.add_always_allow("file_patch")

            self.assertTrue(store.remove_always_allow("shell"))
            self.assertFalse(store.remove_always_allow("shell"))
            self.assertEqual(store.always_allow, {"file_patch"})

            store.clear()
            self.assertEqual(store.always_allow, set())

    def test_save_writes_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = _make_store(Path(tmp))
            store.add_always_allow("shell")
            data = json.loads((Path(tmp) / "approvals.json").read_text(encoding="utf-8"))
            self.assertEqual(data, {"always_allow": ["shell"]})

    def test_high_risk_set_is_what_we_expect(self) -> None:
        # Guard against accidental tool-name renames silently dropping a
        # tool out of the gate.
        self.assertIn("shell", HIGH_RISK_TOOLS)
        self.assertIn("code_run", HIGH_RISK_TOOLS)
        self.assertIn("file_write", HIGH_RISK_TOOLS)
        self.assertIn("file_patch", HIGH_RISK_TOOLS)


class ApprovalGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_yolo_passes_through(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inner = FakeRegistry()
            store = _make_store(Path(tmp))
            request_decision = AsyncMock()
            gate = ApprovalGate(
                inner=inner,
                store=store,
                request_decision=request_decision,
                yolo=True,
            )
            result = await gate.run(ToolCall(id="t1", name="shell", arguments={}))
            self.assertFalse(result.is_error)
            self.assertEqual(len(inner.calls), 1)
            request_decision.assert_not_called()

    async def test_low_risk_tool_skips_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inner = FakeRegistry()
            store = _make_store(Path(tmp))
            request_decision = AsyncMock()
            gate = ApprovalGate(
                inner=inner,
                store=store,
                request_decision=request_decision,
            )
            result = await gate.run(ToolCall(id="t1", name="file_read", arguments={}))
            self.assertFalse(result.is_error)
            request_decision.assert_not_called()

    async def test_always_allowed_tool_skips_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inner = FakeRegistry()
            store = _make_store(Path(tmp))
            store.add_always_allow("shell")
            request_decision = AsyncMock()
            gate = ApprovalGate(
                inner=inner,
                store=store,
                request_decision=request_decision,
            )
            result = await gate.run(ToolCall(id="t1", name="shell", arguments={}))
            self.assertFalse(result.is_error)
            request_decision.assert_not_called()

    async def test_high_risk_tool_awaits_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inner = FakeRegistry()
            store = _make_store(Path(tmp))

            async def schedule_resolve(pending) -> None:  # type: ignore[no-untyped-def]
                # Simulate the frontend: resolve "allow_once" on the next loop iteration.
                loop = asyncio.get_running_loop()
                loop.call_soon(lambda: gate.resolve(pending.tool_use_id, "allow_once"))

            gate = ApprovalGate(
                inner=inner,
                store=store,
                request_decision=schedule_resolve,
            )
            result = await gate.run(
                ToolCall(id="t1", name="shell", arguments={"command": "ls"})
            )
            self.assertFalse(result.is_error)
            self.assertEqual(len(inner.calls), 1)

    async def test_deny_returns_error_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inner = FakeRegistry()
            store = _make_store(Path(tmp))

            async def schedule_resolve(pending) -> None:  # type: ignore[no-untyped-def]
                loop = asyncio.get_running_loop()
                loop.call_soon(lambda: gate.resolve(pending.tool_use_id, "deny"))

            gate = ApprovalGate(
                inner=inner,
                store=store,
                request_decision=schedule_resolve,
            )
            result = await gate.run(
                ToolCall(id="t1", name="shell", arguments={"command": "rm -rf /"})
            )
            self.assertTrue(result.is_error)
            self.assertIn("denied by user", result.content)
            self.assertEqual(len(inner.calls), 0)

    async def test_allow_always_persists_to_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inner = FakeRegistry()
            store = _make_store(Path(tmp))

            async def schedule_resolve(pending) -> None:  # type: ignore[no-untyped-def]
                loop = asyncio.get_running_loop()
                loop.call_soon(lambda: gate.resolve(pending.tool_use_id, "allow_always"))

            gate = ApprovalGate(
                inner=inner,
                store=store,
                request_decision=schedule_resolve,
            )
            await gate.run(ToolCall(id="t1", name="shell", arguments={}))
            self.assertIn("shell", store.always_allow)
            reloaded = ApprovalStore.load(store.path)
            self.assertIn("shell", reloaded.always_allow)


if __name__ == "__main__":
    unittest.main()
