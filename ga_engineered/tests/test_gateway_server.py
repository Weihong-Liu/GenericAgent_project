"""Integration tests for :mod:`generic_agent_engineered.gateway.server`.

Tests inject a fake provider into :class:`ChatTurnService` so they exercise the
real :class:`AgentLoop` and event_sink wiring without needing a real LLM
client. Stdin is faked with an :class:`asyncio.StreamReader` we feed by hand;
stdout is captured into a :class:`BytesIO`.
"""

from __future__ import annotations

import asyncio
import io
import json

import pytest

from generic_agent_engineered.chat import ChatTurnService
from generic_agent_engineered.config import RuntimeSettings
from generic_agent_engineered.engine import AgentRuntime
from generic_agent_engineered.gateway import GatewayServer
from generic_agent_engineered.gateway.protocol import (
    ERR_INVALID_PARAMS,
    ERR_METHOD_NOT_FOUND,
    ERR_REQUEST_REJECTED,
    ERR_RUNTIME_BUSY,
    PROTOCOL_VERSION,
)
from generic_agent_engineered.runtime.events import RuntimeEvent
from generic_agent_engineered.runtime.messages import ChatResponse, Message, ToolCall
from generic_agent_engineered.state import SessionStore

pytestmark = pytest.mark.asyncio


class TextProvider:
    """Yield a single content_delta and a message_done."""

    def __init__(self, content: str = "hello world") -> None:
        self.content = content

    async def stream_chat(self, messages, tools=None):
        # Emit two deltas so the transcript can prove streaming works.
        mid = len(self.content) // 2
        first, second = self.content[:mid], self.content[mid:]
        if first:
            yield RuntimeEvent.content_delta(first)
        if second:
            yield RuntimeEvent.content_delta(second)
        yield RuntimeEvent.message_done(ChatResponse(content=self.content))


class SlowProvider:
    """Yield deltas with explicit awaits so cancellation has a window to fire."""

    def __init__(self, chunks: int = 5) -> None:
        self.chunks = chunks
        self.emitted = 0

    async def stream_chat(self, messages, tools=None):
        for i in range(self.chunks):
            await asyncio.sleep(0)
            yield RuntimeEvent.content_delta(f"chunk-{i}")
            self.emitted += 1
        yield RuntimeEvent.message_done(ChatResponse(content="done"))


class ToolProvider:
    """First call asks for a tool; second call returns final text."""

    def __init__(self) -> None:
        self.calls = 0

    async def stream_chat(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            tool_call = ToolCall(id="t-1", name="echo_tool", arguments={"x": 1})
            yield RuntimeEvent.from_tool_call(tool_call)
            yield RuntimeEvent.message_done(
                ChatResponse(tool_calls=(tool_call,))
            )
            return
        yield RuntimeEvent.message_done(ChatResponse(content="done"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_server(provider) -> tuple[GatewayServer, AgentRuntime]:
    runtime = AgentRuntime()
    chat = ChatTurnService(runtime, provider=provider)
    server = GatewayServer(runtime=runtime, chat_service=chat)
    return server, runtime


class FlushingBytesIO(io.BytesIO):
    """BytesIO subclass that ignores .flush() (the gateway calls it)."""

    def flush(self) -> None:  # pragma: no cover - trivial
        pass


def _read_frames(buffer: io.BytesIO) -> list[dict]:
    text = buffer.getvalue().decode("utf-8")
    frames: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            frames.append(json.loads(line))
    return frames


async def _drive(server: GatewayServer, frames: list[dict]) -> list[dict]:
    """Run ``server.serve`` against a hand-fed reader; return all output frames.

    Each input frame is fed as one line. After all lines are written, the
    reader is closed so ``readline()`` returns b'' and ``serve`` exits.
    """

    reader = asyncio.StreamReader()
    writer = FlushingBytesIO()

    for frame in frames:
        reader.feed_data((json.dumps(frame) + "\n").encode("utf-8"))
    reader.feed_eof()

    rc = await server.serve(reader=reader, writer=writer)
    assert rc == 0
    return _read_frames(writer)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_gateway_emits_ready_event_on_startup() -> None:
    server, _ = _build_server(TextProvider())
    out = await _drive(server, [])

    kinds = [(f.get("type"), f.get("kind")) for f in out]
    assert ("event", "gateway.ready") in kinds
    assert ("event", "gateway.shutdown") in kinds

    ready = next(f for f in out if f.get("kind") == "gateway.ready")
    assert ready["payload"]["protocol_version"] == PROTOCOL_VERSION
    assert isinstance(ready["payload"]["pid"], int)


async def test_runtime_status_returns_protocol_version() -> None:
    server, _ = _build_server(TextProvider())
    out = await _drive(
        server,
        [{"type": "request", "id": 1, "method": "runtime.status", "params": {}}],
    )

    response = next(f for f in out if f.get("type") == "response" and f["id"] == 1)
    assert response["result"]["protocol_version"] == PROTOCOL_VERSION
    assert response["result"]["busy"] is False
    assert "tool_count" in response["result"]
    assert "tokens_used" in response["result"]


async def test_method_not_found_returns_minus_32601() -> None:
    server, _ = _build_server(TextProvider())
    out = await _drive(
        server,
        [{"type": "request", "id": 99, "method": "no.such.method", "params": {}}],
    )

    response = next(f for f in out if f.get("type") == "response" and f["id"] == 99)
    assert response["error"]["code"] == ERR_METHOD_NOT_FOUND


async def test_invalid_json_frame_is_reported() -> None:
    server, _ = _build_server(TextProvider())
    reader = asyncio.StreamReader()
    writer = FlushingBytesIO()

    reader.feed_data(b"{not json\n")
    reader.feed_eof()

    await server.serve(reader=reader, writer=writer)
    frames = _read_frames(writer)
    errors = [f for f in frames if f.get("type") == "response" and "error" in f]
    assert errors, "expected an error response for malformed JSON"
    assert errors[0]["error"]["code"] == -32700


async def test_chat_send_streams_events_then_response() -> None:
    server, runtime = _build_server(TextProvider("hello world"))
    out = await _drive(
        server,
        [{"type": "request", "id": 5, "method": "chat.send", "params": {"prompt": "hi"}}],
    )

    events_for_5 = [
        f for f in out if f.get("type") == "event" and f.get("request_id") == 5
    ]
    response = next(f for f in out if f.get("type") == "response" and f["id"] == 5)

    kinds = [event["kind"] for event in events_for_5]
    assert kinds[0] == "turn_started"
    assert "content_delta" in kinds
    assert "message_done" in kinds
    assert "turn_finished" in kinds

    # Response carries final shape and busy must have flipped back to false.
    assert response["result"]["status"] == "completed"
    assert response["result"]["content"] == "hello world"
    assert response["result"]["is_error"] is False
    assert response["result"]["turn_count"] == 1
    assert runtime.state.turn_count == 1


async def test_chat_send_missing_prompt_returns_invalid_params() -> None:
    server, _ = _build_server(TextProvider())
    out = await _drive(
        server,
        [{"type": "request", "id": 1, "method": "chat.send", "params": {}}],
    )

    response = next(f for f in out if f.get("type") == "response" and f["id"] == 1)
    assert response["error"]["code"] == ERR_INVALID_PARAMS


async def test_second_chat_send_while_busy_returns_runtime_busy() -> None:
    """Two concurrent chat.send: the second is rejected with -32001."""

    server, _ = _build_server(SlowProvider(chunks=20))
    reader = asyncio.StreamReader()
    writer = FlushingBytesIO()

    # Feed two chat.send back to back. They will be dispatched on separate
    # tasks; the first claims the busy slot, the second hits -32001.
    for frame in (
        {"type": "request", "id": 1, "method": "chat.send", "params": {"prompt": "a"}},
        {"type": "request", "id": 2, "method": "chat.send", "params": {"prompt": "b"}},
    ):
        reader.feed_data((json.dumps(frame) + "\n").encode("utf-8"))
    reader.feed_eof()

    await server.serve(reader=reader, writer=writer)
    frames = _read_frames(writer)

    response_2 = next(
        f
        for f in frames
        if f.get("type") == "response" and f.get("id") == 2
    )
    assert response_2["error"]["code"] == ERR_RUNTIME_BUSY


async def test_chat_cancel_unknown_request_id_rejected() -> None:
    server, _ = _build_server(TextProvider())
    out = await _drive(
        server,
        [
            {
                "type": "request",
                "id": 1,
                "method": "chat.cancel",
                "params": {"request_id": 999},
            }
        ],
    )

    response = next(f for f in out if f.get("type") == "response" and f["id"] == 1)
    assert response["error"]["code"] == ERR_REQUEST_REJECTED


async def test_session_new_resets_runtime_state() -> None:
    server, runtime = _build_server(TextProvider())
    runtime.state.turn_count = 5
    runtime.state.messages = []  # default

    out = await _drive(
        server,
        [{"type": "request", "id": 1, "method": "session.new", "params": {}}],
    )

    response = next(f for f in out if f.get("type") == "response" and f["id"] == 1)
    assert response["result"]["turn_count"] == 0
    assert runtime.state.turn_count == 0


async def test_session_list_and_resume_use_session_store(tmp_path) -> None:
    runtime = AgentRuntime(settings=RuntimeSettings(home=tmp_path))
    chat = ChatTurnService(runtime, provider=TextProvider())
    server = GatewayServer(runtime=runtime, chat_service=chat)
    store = SessionStore.from_settings(runtime.settings)
    store.create_session("saved", title="Saved chat")
    store.append_message("saved", Message.user("remember this"))

    out = await _drive(
        server,
        [
            {"type": "request", "id": 1, "method": "session.list", "params": {}},
            {
                "type": "request",
                "id": 2,
                "method": "session.resume",
                "params": {"session_id": "saved"},
            },
        ],
    )

    listed = next(f for f in out if f.get("type") == "response" and f["id"] == 1)
    resumed = next(f for f in out if f.get("type") == "response" and f["id"] == 2)

    assert any(session["id"] == "saved" for session in listed["result"]["sessions"])
    assert resumed["result"]["session_id"] == "saved"
    assert resumed["result"]["messages"] == 1
    assert runtime.state.session_id == "saved"
    assert runtime.state.messages[0].content == "remember this"


async def test_tasks_and_worktree_status_methods_return_panel_data() -> None:
    server, _ = _build_server(TextProvider())
    out = await _drive(
        server,
        [
            {"type": "request", "id": 1, "method": "tasks.list", "params": {}},
            {"type": "request", "id": 2, "method": "worktree.status", "params": {}},
        ],
    )

    tasks = next(f for f in out if f.get("type") == "response" and f["id"] == 1)
    worktree = next(f for f in out if f.get("type") == "response" and f["id"] == 2)

    assert tasks["result"]["busy"] is False
    assert tasks["result"]["tasks"] == []
    assert "is_git" in worktree["result"]
    assert "path" in worktree["result"]


async def test_extension_list_methods_return_items(tmp_path) -> None:
    runtime = AgentRuntime(settings=RuntimeSettings(home=tmp_path))
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "demo.md").write_text("# demo\n", encoding="utf-8")
    server = GatewayServer(
        runtime=runtime,
        chat_service=ChatTurnService(runtime, provider=TextProvider()),
    )
    out = await _drive(
        server,
        [
            {"type": "request", "id": 1, "method": "mcp.list", "params": {}},
            {"type": "request", "id": 2, "method": "plugins.list", "params": {}},
            {"type": "request", "id": 3, "method": "agents.list", "params": {}},
            {"type": "request", "id": 4, "method": "hooks.list", "params": {}},
        ],
    )

    by_id = {f["id"]: f for f in out if f.get("type") == "response"}
    assert by_id[1]["result"]["kind"] == "mcp"
    assert by_id[2]["result"]["kind"] == "plugin"
    assert any(item["name"] == "demo" for item in by_id[3]["result"]["items"])
    assert by_id[4]["result"]["kind"] == "hook"


async def test_commands_list_returns_registered_commands() -> None:
    server, _ = _build_server(TextProvider())
    out = await _drive(
        server,
        [{"type": "request", "id": 1, "method": "commands.list", "params": {}}],
    )

    response = next(f for f in out if f.get("type") == "response" and f["id"] == 1)
    commands = response["result"]["commands"]
    assert isinstance(commands, list)
    assert len(commands) > 0
    names = {c["name"] for c in commands}
    assert "help" in names
    sample = next(c for c in commands if c["name"] == "help")
    expected_keys = (
        "name",
        "description",
        "category",
        "aliases",
        "args_hint",
        "subcommands",
        "cli_only",
    )
    for key in expected_keys:
        assert key in sample


async def test_commands_dispatch_routes_to_router() -> None:
    server, _ = _build_server(TextProvider())
    out = await _drive(
        server,
        [
            {
                "type": "request",
                "id": 1,
                "method": "commands.dispatch",
                "params": {"line": "/help"},
            }
        ],
    )

    response = next(f for f in out if f.get("type") == "response" and f["id"] == 1)
    assert response["result"]["is_error"] is False
    assert isinstance(response["result"]["content"], str)
    assert response["result"]["content"]


async def test_tools_list_returns_default_tools() -> None:
    server, _ = _build_server(TextProvider())
    out = await _drive(
        server,
        [{"type": "request", "id": 1, "method": "tools.list", "params": {}}],
    )

    response = next(f for f in out if f.get("type") == "response" and f["id"] == 1)
    tools = response["result"]["tools"]
    assert isinstance(tools, list)
    assert tools, "default tool registry should not be empty"
    sample = tools[0]
    for key in ("name", "description", "enabled", "schema", "permissions"):
        assert key in sample


async def test_gateway_shutdown_request_exits_loop() -> None:
    server, _ = _build_server(TextProvider())
    reader = asyncio.StreamReader()
    writer = FlushingBytesIO()

    shutdown_frame = json.dumps(
        {"type": "request", "id": 1, "method": "gateway.shutdown", "params": {}}
    )
    reader.feed_data((shutdown_frame + "\n").encode("utf-8"))
    # Do NOT feed_eof — the server must exit on its own when shutdown is set.

    rc = await asyncio.wait_for(
        server.serve(reader=reader, writer=writer),
        timeout=2.0,
    )
    assert rc == 0
    frames = _read_frames(writer)
    response = next(f for f in frames if f.get("type") == "response" and f["id"] == 1)
    assert response["result"] == {}
    assert any(f.get("kind") == "gateway.shutdown" for f in frames if f.get("type") == "event")


async def test_chat_cancel_mid_stream_returns_cancelled_status() -> None:
    """A cancel sent while chat.send is streaming yields status=cancelled, is_error=False."""

    server, _ = _build_server(SlowProvider(chunks=20))
    reader = asyncio.StreamReader()
    writer = FlushingBytesIO()

    chat_frame = json.dumps(
        {"type": "request", "id": 7, "method": "chat.send", "params": {"prompt": "hi"}}
    )
    cancel_frame = json.dumps(
        {"type": "request", "id": 8, "method": "chat.cancel", "params": {}}
    )
    reader.feed_data((chat_frame + "\n").encode("utf-8"))
    reader.feed_data((cancel_frame + "\n").encode("utf-8"))
    reader.feed_eof()

    await server.serve(reader=reader, writer=writer)
    frames = _read_frames(writer)

    chat_response = next(
        f for f in frames if f.get("type") == "response" and f.get("id") == 7
    )
    cancel_response = next(
        f for f in frames if f.get("type") == "response" and f.get("id") == 8
    )

    assert cancel_response["result"]["cancelled"] is True
    assert cancel_response["result"]["request_id"] == 7
    assert chat_response["result"]["status"] == "cancelled"
    assert chat_response["result"]["is_error"] is False
    assert chat_response["result"]["retry_reason"] == "cancelled"


async def test_chat_cancel_no_request_id_targets_in_flight() -> None:
    """``chat.cancel`` without ``request_id`` cancels the active chat.send."""

    server, _ = _build_server(SlowProvider(chunks=20))
    reader = asyncio.StreamReader()
    writer = FlushingBytesIO()

    chat_frame = json.dumps(
        {"type": "request", "id": 11, "method": "chat.send", "params": {"prompt": "x"}}
    )
    cancel_frame = json.dumps({"type": "request", "id": 12, "method": "chat.cancel"})
    reader.feed_data((chat_frame + "\n").encode("utf-8"))
    reader.feed_data((cancel_frame + "\n").encode("utf-8"))
    reader.feed_eof()

    await server.serve(reader=reader, writer=writer)
    frames = _read_frames(writer)

    cancel_response = next(
        f for f in frames if f.get("type") == "response" and f.get("id") == 12
    )
    assert cancel_response["result"]["cancelled"] is True
    assert cancel_response["result"]["request_id"] == 11


async def test_chat_cancel_no_request_id_when_idle_rejected() -> None:
    """Cancelling without a request_id while idle returns -32002."""

    server, _ = _build_server(TextProvider())
    out = await _drive(
        server,
        [{"type": "request", "id": 1, "method": "chat.cancel", "params": {}}],
    )

    response = next(f for f in out if f.get("type") == "response" and f["id"] == 1)
    assert response["error"]["code"] == ERR_REQUEST_REJECTED


class AuthFailingProvider:
    async def stream_chat(self, messages, tools=None):
        from generic_agent_engineered.providers.errors import ProviderAuthError

        raise ProviderAuthError("login required")
        # Make this an async generator so AgentLoop's ``async for`` accepts it.
        yield  # pragma: no cover


class GenericFailingProvider:
    async def stream_chat(self, messages, tools=None):
        from generic_agent_engineered.providers.errors import ProviderError

        raise ProviderError("upstream 502")
        yield  # pragma: no cover


async def test_provider_auth_error_maps_to_minus_32003() -> None:
    server, _ = _build_server(AuthFailingProvider())
    out = await _drive(
        server,
        [{"type": "request", "id": 1, "method": "chat.send", "params": {"prompt": "x"}}],
    )

    response = next(f for f in out if f.get("type") == "response" and f["id"] == 1)
    assert response["error"]["code"] == -32003
    assert "login required" in response["error"]["message"]


async def test_provider_error_maps_to_minus_32004() -> None:
    server, _ = _build_server(GenericFailingProvider())
    out = await _drive(
        server,
        [{"type": "request", "id": 1, "method": "chat.send", "params": {"prompt": "x"}}],
    )

    response = next(f for f in out if f.get("type") == "response" and f["id"] == 1)
    assert response["error"]["code"] == -32004
    assert response["error"]["data"]["error_type"] == "ProviderError"


async def test_tools_run_invokes_registered_tool() -> None:
    """``tools.run`` bypasses the LLM and runs the tool directly."""

    server, _ = _build_server(TextProvider())
    out = await _drive(
        server,
        [
            {
                "type": "request",
                "id": 1,
                "method": "tools.run",
                "params": {
                    "name": "shell",
                    "arguments": {"command": "echo gateway-tools-run"},
                },
            }
        ],
    )

    response = next(f for f in out if f.get("type") == "response" and f["id"] == 1)
    assert response["result"]["is_error"] is False
    assert "gateway-tools-run" in response["result"]["content"]


async def test_tools_run_unknown_name_yields_tool_error_result() -> None:
    server, _ = _build_server(TextProvider())
    out = await _drive(
        server,
        [
            {
                "type": "request",
                "id": 1,
                "method": "tools.run",
                "params": {"name": "no_such_tool", "arguments": {}},
            }
        ],
    )

    response = next(f for f in out if f.get("type") == "response" and f["id"] == 1)
    assert response["result"]["is_error"] is True
    assert "unknown tool" in response["result"]["content"]


async def test_files_search_returns_workspace_paths() -> None:
    server, _ = _build_server(TextProvider())
    out = await _drive(
        server,
        [
            {
                "type": "request",
                "id": 1,
                "method": "files.search",
                "params": {"query": "pyproject", "limit": 5},
            }
        ],
    )

    response = next(f for f in out if f.get("type") == "response" and f["id"] == 1)
    matches = response["result"]["matches"]
    assert isinstance(matches, list)
    # Test runs from ga_engineered which contains pyproject.toml at root.
    paths = [m["path"] for m in matches]
    assert any("pyproject.toml" in p for p in paths)


async def test_integration_methods_return_statuses() -> None:
    server, _ = _build_server(TextProvider())
    out = await _drive(
        server,
        [
            {"type": "request", "id": 1, "method": "integrations.list", "params": {}},
            {
                "type": "request",
                "id": 2,
                "method": "integrations.status",
                "params": {"name": "chrome"},
            },
        ],
    )

    listed = next(f for f in out if f.get("type") == "response" and f["id"] == 1)
    names = {item["name"] for item in listed["result"]["integrations"]}
    assert {"ide", "desktop", "chrome", "voice", "remote", "mobile"} <= names

    chrome = next(f for f in out if f.get("type") == "response" and f["id"] == 2)
    assert chrome["result"]["integration"]["name"] == "chrome"
    assert "action" in chrome["result"]["integration"]


async def test_chat_send_with_tool_call_emits_tool_events() -> None:
    server, _ = _build_server(ToolProvider())
    out = await _drive(
        server,
        [{"type": "request", "id": 1, "method": "chat.send", "params": {"prompt": "use tool"}}],
    )

    events = [
        f for f in out if f.get("type") == "event" and f.get("request_id") == 1
    ]
    kinds = [event["kind"] for event in events]
    # The first turn should at least emit tool_call and a tool_result.
    assert "tool_call" in kinds
    assert "tool_result" in kinds
