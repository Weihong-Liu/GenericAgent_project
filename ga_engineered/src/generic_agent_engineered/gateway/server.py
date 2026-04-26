"""Stdio JSON-RPC gateway server for the TypeScript TUI frontend.

The gateway is a thin async wrapper around :class:`AgentRuntime`,
:class:`ChatTurnService`, :class:`CommandRouter` and :class:`ToolRegistry`.
It is launched as a subprocess by the TS Ink frontend and speaks
line-delimited JSON over stdin/stdout. The wire protocol is documented in
``tasks/TUI_TS_PROTOCOL.md``.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import traceback
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, BinaryIO

from generic_agent_engineered import __version__
from generic_agent_engineered.chat import ChatTurnService
from generic_agent_engineered.commands import (
    CommandContext,
    CommandRouter,
    available_commands,
)
from generic_agent_engineered.engine import AgentRuntime
from generic_agent_engineered.providers.errors import ProviderAuthError, ProviderError
from generic_agent_engineered.runtime.approvals import (
    ApprovalGate,
    ApprovalStore,
    PendingApproval,
    default_approvals_path,
)
from generic_agent_engineered.runtime.events import RuntimeEvent
from generic_agent_engineered.state import (
    list_background_tasks,
    list_extensions,
    list_integration_statuses,
    list_session_summaries,
    resume_session,
    worktree_status,
)

from .auto_bridge import maybe_spawn_bridge, terminate_bridge
from .protocol import (
    ERR_AUTH_REQUIRED,
    ERR_INVALID_PARAMS,
    ERR_METHOD_NOT_FOUND,
    ERR_PROVIDER_FAILURE,
    ERR_REQUEST_REJECTED,
    ERR_RUNTIME_BUSY,
    ERR_UNKNOWN,
    PROTOCOL_VERSION,
    Event,
    ProtocolError,
    Request,
    Response,
    encode_frame,
    parse_request,
)

MethodHandler = Callable[["GatewayServer", Request], Awaitable[dict[str, Any]]]


class GatewayServer:
    """Single-session JSON-RPC server bound to a Python AgentRuntime."""

    def __init__(
        self,
        *,
        runtime: AgentRuntime | None = None,
        chat_service: ChatTurnService | None = None,
        router: CommandRouter | None = None,
        debug: bool | None = None,
    ) -> None:
        self.runtime = runtime or AgentRuntime()
        self.chat_service = chat_service or ChatTurnService(self.runtime)
        self.router = router or CommandRouter()
        self.debug = bool(debug) if debug is not None else _env_truthy("GA_GATEWAY_DEBUG")
        self.approval_store = ApprovalStore.load(default_approvals_path())
        self.approval_gate = ApprovalGate(
            inner=self.chat_service.tool_registry,
            store=self.approval_store,
            request_decision=self._emit_approval_request,
            yolo=_env_truthy("GA_YOLO"),
        )
        # The chat service uses ``tool_executor`` (when set) for
        # AgentLoop's tool dispatch, falling back to ``tool_registry``.
        # Direct ``tools.run`` calls (the !bash path) hit the registry
        # directly and bypass the gate by design.
        self.chat_service.tool_executor = self.approval_gate

        self._busy = False
        self._busy_request_id: int | None = None
        self._cancel_flag = False
        self._writer_lock = asyncio.Lock()
        self._shutdown = asyncio.Event()
        self._reader: asyncio.StreamReader | None = None
        self._writer: BinaryIO | None = None
        self._bridge_proc: subprocess.Popen[bytes] | None = None

        self._methods: dict[str, MethodHandler] = {
            "chat.send": _method_chat_send,
            "chat.cancel": _method_chat_cancel,
            "commands.list": _method_commands_list,
            "commands.dispatch": _method_commands_dispatch,
            "tools.list": _method_tools_list,
            "runtime.status": _method_runtime_status,
            "session.new": _method_session_new,
            "session.list": _method_session_list,
            "session.resume": _method_session_resume,
            "gateway.shutdown": _method_gateway_shutdown,
            "tools.run": _method_tools_run,
            "files.search": _method_files_search,
            "chat.approve": _method_chat_approve,
            "tasks.list": _method_tasks_list,
            "worktree.status": _method_worktree_status,
            "mcp.list": _method_mcp_list,
            "plugins.list": _method_plugins_list,
            "agents.list": _method_agents_list,
            "hooks.list": _method_hooks_list,
            "integrations.list": _method_integrations_list,
            "integrations.status": _method_integration_status,
        }

    async def serve(
        self,
        *,
        reader: asyncio.StreamReader,
        writer: BinaryIO,
    ) -> int:
        """Run the request/event loop until stdin closes or shutdown is requested."""

        self._reader = reader
        self._writer = writer

        # Best-effort: bring the browser bridge up alongside the gateway
        # so ``web_scan`` / ``web_execute_js`` work without a separate
        # ``gae bridge`` step. ``maybe_spawn_bridge`` returns None when
        # the deps aren't installed, the legacy module isn't visible,
        # or the port is already in use — all of which are fine.
        self._bridge_proc = maybe_spawn_bridge()

        await self._emit_event(
            Event(
                kind="gateway.ready",
                payload={
                    "version": __version__,
                    "protocol_version": PROTOCOL_VERSION,
                    "pid": os.getpid(),
                    "bridge_started": self._bridge_proc is not None,
                },
            )
        )

        in_flight: set[asyncio.Task[Any]] = set()
        shutdown_requested = False
        try:
            while not self._shutdown.is_set():
                line_task = asyncio.create_task(reader.readline())
                shutdown_task = asyncio.create_task(self._shutdown.wait())
                done, pending = await asyncio.wait(
                    [line_task, shutdown_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()

                if shutdown_task in done and line_task not in done:
                    shutdown_requested = True
                    break

                line = line_task.result()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue

                task = asyncio.create_task(self._handle_line(text))
                in_flight.add(task)
                task.add_done_callback(in_flight.discard)
        finally:
            # On stdin EOF we let in-flight requests finish so their responses
            # reach the client before exit. Only an explicit shutdown request
            # cancels outstanding work.
            if shutdown_requested:
                for task in list(in_flight):
                    task.cancel()
            if in_flight:
                await asyncio.gather(*in_flight, return_exceptions=True)

        await self._emit_event(
            Event(kind="gateway.shutdown", payload={"reason": "stdin_closed_or_shutdown"})
        )
        terminate_bridge(self._bridge_proc)
        self._bridge_proc = None
        return 0

    async def _handle_line(self, line: str) -> None:
        try:
            request = parse_request(line)
        except ProtocolError as exc:
            await self._emit_response(
                Response(id=exc.request_id or 0, error=exc.to_error_dict())
            )
            return

        handler = self._methods.get(request.method)
        if handler is None:
            await self._emit_response(
                Response(
                    id=request.id,
                    error={
                        "code": ERR_METHOD_NOT_FOUND,
                        "message": f"unknown method: {request.method}",
                    },
                )
            )
            return

        # Pre-claim the busy slot for chat.send synchronously (no await between
        # check and set) so a concurrent chat.cancel for this id always
        # observes the in-flight state, even when the cancel task races ahead
        # of the chat.send task body. The handler trusts that busy is already
        # claimed and only clears it in the finally branch below.
        pre_claimed_chat_send = False
        if request.method == "chat.send":
            if self._busy:
                await self._emit_response(
                    Response(
                        id=request.id,
                        error={
                            "code": ERR_RUNTIME_BUSY,
                            "message": "another chat.send is already in flight",
                            "data": {"in_flight_request_id": self._busy_request_id},
                        },
                    )
                )
                return
            self._busy = True
            self._busy_request_id = request.id
            self._cancel_flag = False
            pre_claimed_chat_send = True

        try:
            try:
                result = await handler(self, request)
            except ProtocolError as exc:
                await self._emit_response(
                    Response(id=request.id, error=exc.to_error_dict())
                )
                return
            except Exception as exc:  # noqa: BLE001
                error: dict[str, Any] = {
                    "code": ERR_UNKNOWN,
                    "message": f"{exc.__class__.__name__}: {exc}",
                }
                if self.debug:
                    error["data"] = {"traceback": traceback.format_exc()}
                await self._emit_response(Response(id=request.id, error=error))
                return

            await self._emit_response(Response(id=request.id, result=result))
        finally:
            if pre_claimed_chat_send:
                self._busy = False
                self._busy_request_id = None
                self._cancel_flag = False

    async def _emit_response(self, response: Response) -> None:
        await self._write_frame(response.to_frame())

    async def _emit_event(self, event: Event) -> None:
        await self._write_frame(event.to_frame())

    async def _emit_approval_request(self, pending: PendingApproval) -> None:
        """Send an ``approval_request`` event so the TUI can render a prompt."""
        await self._emit_event(
            Event(
                kind="approval_request",
                payload={
                    "tool_use_id": pending.tool_use_id,
                    "name": pending.name,
                    "arguments_preview": pending.arguments_preview,
                },
            )
        )

    async def _write_frame(self, frame: dict[str, Any]) -> None:
        if self._writer is None:
            return
        line = encode_frame(frame).encode("utf-8")
        async with self._writer_lock:
            # ``sys.stdout.buffer`` is a blocking BinaryIO. A large delta on a
            # back-pressured pipe could otherwise stall the event loop, so we
            # always run the write+flush pair in the default executor.
            await asyncio.get_running_loop().run_in_executor(
                None, self._sync_write, line
            )

    def _sync_write(self, line: bytes) -> None:
        if self._writer is None:
            return
        self._writer.write(line)
        self._writer.flush()


# ---------------------------------------------------------------------------
# Method handlers
# ---------------------------------------------------------------------------


async def _method_chat_send(server: GatewayServer, request: Request) -> dict[str, Any]:
    # ``_handle_line`` has already validated the busy slot and claimed it on
    # behalf of this request, so there is no busy check here. The slot is
    # released by ``_handle_line``'s finally block after the response is
    # written.
    prompt = request.params.get("prompt")
    if not isinstance(prompt, str):
        raise ProtocolError(
            ERR_INVALID_PARAMS,
            "chat.send requires params.prompt: string",
        )

    async def event_sink(event: RuntimeEvent) -> None:
        await server._emit_event(
            Event(
                kind=event.kind,
                payload=event.to_dict(),
                request_id=request.id,
            )
        )

    def stop_signal() -> bool:
        return server._cancel_flag

    try:
        result = await server.chat_service.run_turn(
            prompt,
            event_sink=event_sink,
            stop_signal=stop_signal,
        )
    except ProviderAuthError as exc:
        raise ProtocolError(ERR_AUTH_REQUIRED, str(exc)) from exc
    except ProviderError as exc:
        raise ProtocolError(
            ERR_PROVIDER_FAILURE,
            str(exc),
            data={"error_type": exc.__class__.__name__},
        ) from exc

    # ``ChatTurnService`` catches a number of provider exceptions and surfaces
    # them as an error-shaped ``ChatTurnResult``. Mirror that into the matching
    # JSON-RPC error code so the frontend has one place to look for auth or
    # upstream issues, regardless of where the catch happened.
    if result.is_error and result.error_type == "ProviderAuthError":
        raise ProtocolError(ERR_AUTH_REQUIRED, result.content)
    if result.is_error and result.error_type and result.error_type.endswith("ProviderError"):
        raise ProtocolError(
            ERR_PROVIDER_FAILURE,
            result.content,
            data={"error_type": result.error_type},
        )

    cancelled = server._cancel_flag
    status = result.status
    is_error = bool(result.is_error)
    if cancelled and status in {"stopped", "completed"}:
        status = "cancelled"
        is_error = False

    return {
        "status": status,
        "content": result.content,
        "is_error": is_error,
        "turn_count": server.runtime.state.turn_count,
        "provider": result.provider,
        "model": result.model,
        "error_type": result.error_type or None,
        "retry_reason": _retry_reason_for(result, cancelled=cancelled),
    }


async def _method_chat_cancel(server: GatewayServer, request: Request) -> dict[str, Any]:
    target = request.params.get("request_id")
    if target is None:
        # Cancel whatever is in flight.
        if not server._busy:
            raise ProtocolError(
                ERR_REQUEST_REJECTED,
                "no chat.send is currently in flight",
            )
        server._cancel_flag = True
        return {"cancelled": True, "request_id": server._busy_request_id}

    if not isinstance(target, int):
        raise ProtocolError(ERR_INVALID_PARAMS, "params.request_id must be an integer")
    if not server._busy or server._busy_request_id != target:
        raise ProtocolError(
            ERR_REQUEST_REJECTED,
            f"request_id {target} is not in flight",
        )
    server._cancel_flag = True
    return {"cancelled": True, "request_id": target}


async def _method_commands_list(server: GatewayServer, request: Request) -> dict[str, Any]:
    commands = []
    for command in available_commands():
        commands.append(
            {
                "name": command.name,
                "description": command.description,
                "category": command.category,
                "aliases": list(command.aliases),
                "args_hint": command.args_hint,
                "subcommands": list(command.subcommands),
                "cli_only": command.cli_only,
            }
        )
    return {"commands": commands}


async def _method_commands_dispatch(server: GatewayServer, request: Request) -> dict[str, Any]:
    line = request.params.get("line")
    if not isinstance(line, str) or not line.strip():
        raise ProtocolError(
            ERR_INVALID_PARAMS,
            "commands.dispatch requires params.line: non-empty string",
        )

    context = CommandContext(
        runtime=server.runtime,
        tool_registry=server.chat_service.tool_registry,
        environment=server.chat_service.environment,
    )
    result = server.router.dispatch(line, context)
    return {
        "content": result.content,
        "is_error": bool(result.is_error),
        "should_exit": bool(result.should_exit),
        "metadata": dict(result.metadata),
    }


async def _method_tools_list(server: GatewayServer, request: Request) -> dict[str, Any]:
    tools = []
    for registration in server.chat_service.tool_registry.list_tools():
        spec = registration.tool.spec
        tools.append(
            {
                "name": spec.name,
                "description": spec.schema.description,
                "enabled": registration.enabled,
                "schema": spec.schema_dict(),
                "permissions": [
                    {"name": p.name, "reason": p.reason} for p in spec.permissions
                ],
            }
        )
    return {"tools": tools}


async def _method_runtime_status(server: GatewayServer, request: Request) -> dict[str, Any]:
    runtime = server.runtime
    provider = runtime.current_provider()
    enabled_tools = sum(
        1 for r in server.chat_service.tool_registry.list_tools() if r.enabled
    )
    skills_root = runtime.settings.skills_path if hasattr(runtime.settings, "skills_path") else None
    skill_count = 0
    if skills_root is not None:
        try:
            skill_count = sum(1 for _ in skills_root.iterdir() if _.is_dir())
        except (FileNotFoundError, NotADirectoryError):
            skill_count = 0

    tokens_used = sum(len(message.content) for message in runtime.state.messages) // 4
    return {
        "protocol_version": PROTOCOL_VERSION,
        "gateway_version": __version__,
        "provider": provider.id,
        "model": runtime.state.model,
        "session_id": runtime.state.session_id,
        "turn_count": runtime.state.turn_count,
        "max_turns": server.chat_service.max_turns,
        "tokens_used": tokens_used,
        "tokens_budget": None,
        "tool_count": enabled_tools,
        "skill_count": skill_count,
        "busy": server._busy,
        "bridge_running": _bridge_running(server),
    }


def _bridge_running(server: GatewayServer) -> bool:
    """True when an autospawned bridge is alive *or* something else owns 18766."""
    proc = server._bridge_proc
    if proc is not None and proc.poll() is None:
        return True
    from .auto_bridge import BRIDGE_HTTP_PORT, _port_in_use

    return _port_in_use(BRIDGE_HTTP_PORT)


async def _method_session_new(server: GatewayServer, request: Request) -> dict[str, Any]:
    server.runtime.state.messages = []
    server.runtime.state.turn_count = 0
    return {"turn_count": 0, "session_id": server.runtime.state.session_id}


async def _method_session_list(server: GatewayServer, request: Request) -> dict[str, Any]:
    sessions = [summary.to_dict() for summary in list_session_summaries(server.runtime)]
    return {"current_session_id": server.runtime.state.session_id, "sessions": sessions}


async def _method_session_resume(server: GatewayServer, request: Request) -> dict[str, Any]:
    session_id = request.params.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        raise ProtocolError(ERR_INVALID_PARAMS, "session.resume requires params.session_id")
    summary = resume_session(server.runtime, session_id.strip())
    return {
        "session_id": summary.id,
        "turn_count": server.runtime.state.turn_count,
        "messages": len(server.runtime.state.messages),
        "session": summary.to_dict(),
    }


async def _method_gateway_shutdown(server: GatewayServer, request: Request) -> dict[str, Any]:
    server._shutdown.set()
    return {}


async def _method_chat_approve(server: GatewayServer, request: Request) -> dict[str, Any]:
    """Resolve a pending approval. Frontend posts y/n/a here."""
    tool_use_id = request.params.get("tool_use_id")
    decision = request.params.get("decision")
    if not isinstance(tool_use_id, str) or not tool_use_id:
        raise ProtocolError(ERR_INVALID_PARAMS, "params.tool_use_id required")
    if decision not in ("allow_once", "allow_always", "deny"):
        raise ProtocolError(
            ERR_INVALID_PARAMS,
            "params.decision must be allow_once / allow_always / deny",
        )
    accepted = server.approval_gate.resolve(tool_use_id, decision)
    if not accepted:
        raise ProtocolError(
            ERR_REQUEST_REJECTED,
            f"no pending approval for tool_use_id {tool_use_id}",
        )
    return {"resolved": True, "decision": decision}


async def _method_tools_run(server: GatewayServer, request: Request) -> dict[str, Any]:
    """Invoke a tool directly without going through the LLM.

    Used by the TUI's bash-mode (``!cmd``) so the user can run a shell
    command in-line without burning a turn. Returns the same shape the
    chat path's ``tool_result`` event payload carries.
    """
    name = request.params.get("name")
    if not isinstance(name, str) or not name:
        raise ProtocolError(ERR_INVALID_PARAMS, "tools.run requires params.name")
    arguments = request.params.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise ProtocolError(ERR_INVALID_PARAMS, "params.arguments must be an object")

    from generic_agent_engineered.runtime.messages import ToolCall

    call_id = f"frontend-{request.id}"
    tool_call = ToolCall(id=call_id, name=name, arguments=arguments)
    result = await server.chat_service.tool_registry.run(tool_call)
    return {
        "tool_use_id": result.tool_use_id,
        "content": result.content,
        "is_error": bool(result.is_error),
        "metadata": dict(result.metadata),
    }


async def _method_files_search(server: GatewayServer, request: Request) -> dict[str, Any]:
    """Fuzzy-search workspace files for the @-mention overlay.

    Returns up to ``limit`` (default 25) matching paths sorted by score.
    The implementation walks ``runtime.settings.workspace_root`` once
    per request — fast enough for typical project sizes; we can add a
    cache later if it becomes a bottleneck.
    """
    query = request.params.get("query", "")
    if not isinstance(query, str):
        raise ProtocolError(ERR_INVALID_PARAMS, "params.query must be a string")
    limit_raw = request.params.get("limit", 25)
    limit = int(limit_raw) if isinstance(limit_raw, int) else 25
    matches = _search_workspace_files(server, query, limit=limit)
    return {"matches": matches}


async def _method_tasks_list(server: GatewayServer, request: Request) -> dict[str, Any]:
    tasks = [
        task.to_dict()
        for task in list_background_tasks(
            busy=server._busy,
            request_id=server._busy_request_id,
        )
    ]
    return {"busy": server._busy, "in_flight_request_id": server._busy_request_id, "tasks": tasks}


async def _method_worktree_status(server: GatewayServer, request: Request) -> dict[str, Any]:
    root = getattr(server.runtime.settings, "workspace_root", None)
    return worktree_status(root if isinstance(root, Path) else Path.cwd())


async def _method_mcp_list(server: GatewayServer, request: Request) -> dict[str, Any]:
    return _extension_list(server, "mcp")


async def _method_plugins_list(server: GatewayServer, request: Request) -> dict[str, Any]:
    return _extension_list(server, "plugin")


async def _method_agents_list(server: GatewayServer, request: Request) -> dict[str, Any]:
    return _extension_list(server, "agent")


async def _method_hooks_list(server: GatewayServer, request: Request) -> dict[str, Any]:
    return _extension_list(server, "hook")


def _extension_list(server: GatewayServer, kind: str) -> dict[str, Any]:
    items = [item.to_dict() for item in list_extensions(server.runtime, kind)]
    return {"kind": kind, "items": items}


async def _method_integrations_list(
    server: GatewayServer,
    request: Request,
) -> dict[str, Any]:
    items = [item.to_dict() for item in list_integration_statuses(server.runtime)]
    return {"integrations": items}


async def _method_integration_status(
    server: GatewayServer,
    request: Request,
) -> dict[str, Any]:
    name = request.params.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ProtocolError(
            ERR_INVALID_PARAMS,
            "integrations.status requires params.name: string",
        )
    items = list_integration_statuses(server.runtime)
    for item in items:
        if item.name == name.strip().lower():
            return {"integration": item.to_dict()}
    raise ProtocolError(
        ERR_INVALID_PARAMS,
        f"unknown integration: {name}",
        data={"known": [item.name for item in items]},
    )


def _search_workspace_files(
    server: GatewayServer,
    query: str,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    from pathlib import Path

    settings = server.runtime.settings
    root_attr = getattr(settings, "workspace_root", None)
    root: Path = root_attr if isinstance(root_attr, Path) else Path.cwd()
    needle = query.lower()

    results: list[tuple[int, str]] = []
    skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}

    try:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            relative_parts = path.relative_to(root).parts
            if any(part in skip_dirs for part in relative_parts):
                continue
            rel = "/".join(relative_parts)
            if needle and needle not in rel.lower():
                continue
            score = -rel.lower().find(needle) if needle else 0
            results.append((score, rel))
            if len(results) >= 5000:
                break
    except (OSError, ValueError):
        return []

    results.sort(key=lambda entry: (-entry[0], entry[1].lower()))
    return [{"path": rel} for _, rel in results[:limit]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _retry_reason_for(result: Any, *, cancelled: bool) -> str | None:
    if cancelled:
        return "cancelled"
    if result.status == "max_turns_exceeded":
        return "max_turns_exceeded"
    if result.is_error and result.error_type:
        return result.error_type
    return None


def _env_truthy(name: str) -> bool:
    value = os.environ.get(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


async def serve_stdio(server: GatewayServer | None = None) -> int:
    """Bind a :class:`GatewayServer` to the current process stdin/stdout."""

    server = server or GatewayServer()
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    return await server.serve(reader=reader, writer=sys.stdout.buffer)


__all__ = ["GatewayServer", "serve_stdio"]
