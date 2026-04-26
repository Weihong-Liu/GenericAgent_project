# TUI ↔ Backend Protocol (stdio JSON-RPC)

This document specifies the wire protocol between the **TypeScript/Ink TUI
frontend** (`ga_engineered/ui-tui/`) and the **Python agent runtime backend**
(`generic_agent_engineered.gateway`).

## Transport

- The frontend spawns the backend with `python -m generic_agent_engineered.gateway`.
- All communication happens over the backend's `stdin` (frontend → backend) and
  `stdout` (backend → frontend).
- The backend's `stderr` is reserved for human-readable diagnostics and is
  surfaced to the user only when the backend dies.
- Wire format: **line-delimited JSON** (UTF-8). Each frame is exactly one JSON
  object terminated by `\n`. The frame must not contain a literal newline
  inside any string value (use `\n` escapes).
- The backend never writes anything to `stdout` that is not a valid frame.

## Frame Types

Every frame has a `type` field. Three types are defined:

### `request` (frontend → backend)

```json
{"type": "request", "id": 7, "method": "chat.send", "params": {"prompt": "hi"}}
```

- `id`: monotonic integer chosen by the frontend.
- `method`: one of the methods listed below.
- `params`: method-specific object.

### `response` (backend → frontend)

Success:
```json
{"type": "response", "id": 7, "result": {"turn_count": 3}}
```

Error:
```json
{"type": "response", "id": 7, "error": {"code": -32001, "message": "runtime busy"}}
```

Every `request` produces exactly one `response`. Long-running methods (notably
`chat.send`) emit zero or more `event` frames *before* the final `response`.

### `event` (backend → frontend, unsolicited)

```json
{"type": "event", "kind": "content_delta", "payload": {"delta": "hello"}, "request_id": 7}
```

- `kind`: see "Event Kinds" below.
- `payload`: kind-specific object. For runtime events, this is exactly the
  output of `RuntimeEvent.to_dict()` from `runtime/events.py`.
- `request_id`: present when the event is a side-effect of a specific request
  (e.g. all events emitted while `chat.send` is running). Absent for
  unsolicited events such as `gateway.ready`.

## Methods

| Method              | Params                              | Result schema                              |
|---------------------|-------------------------------------|--------------------------------------------|
| `chat.send`         | `ChatSendParams`                    | `ChatSendResult`                           |
| `chat.cancel`       | `{request_id: number}`              | `{cancelled: boolean}`                     |
| `commands.list`     | `{}`                                | `{commands: CommandDef[]}`                 |
| `commands.dispatch` | `{line: string}`                    | `CommandDispatchResult`                    |
| `tools.list`        | `{}`                                | `{tools: ToolSpec[]}`                      |
| `runtime.status`    | `{}`                                | `RuntimeStatus`                            |
| `session.new`       | `{}`                                | `{turn_count: 0}`                          |
| `session.list`      | `{}`                                | `SessionListResult`                        |
| `session.resume`    | `{session_id: string}`              | `SessionResumeResult`                      |
| `tasks.list`        | `{}`                                | `TasksListResult`                          |
| `worktree.status`   | `{}`                                | `WorktreeStatusResult`                     |
| `mcp.list`          | `{}`                                | `ExtensionListResult`                      |
| `plugins.list`      | `{}`                                | `ExtensionListResult`                      |
| `agents.list`       | `{}`                                | `ExtensionListResult`                      |
| `hooks.list`        | `{}`                                | `ExtensionListResult`                      |
| `integrations.list` | `{}`                                | `IntegrationsListResult`                   |
| `integrations.status` | `{name: string}`                  | `IntegrationStatusResult`                  |
| `gateway.shutdown`  | `{}`                                | `{}` (then backend exits)                  |

### Result schemas (strict — used to generate zod validators)

```ts
type ChatSendParams = {
  prompt: string;
};

type ChatSendResult = {
  status: "completed" | "max_turns_exceeded" | "cancelled" | "error" | "empty_prompt";
  content: string;             // final assistant message or error text
  is_error: boolean;
  turn_count: number;          // total turns used by AgentLoop
  provider: string;            // active provider id
  model: string;               // active model id
  error_type: string | null;   // exception class name when status = "error"
  retry_reason: string | null; // populated when status = "max_turns_exceeded"
};

type CommandDispatchResult = {
  content: string;
  is_error: boolean;
  should_exit: boolean;
  metadata: Record<string, unknown>;
};

type RuntimeStatus = {
  protocol_version: string;    // e.g. "1.0"
  gateway_version: string;     // generic_agent_engineered.__version__
  provider: string;
  model: string;
  turn_count: number;
  max_turns: number;
  tokens_used: number;         // estimated tokens in current history
  tokens_budget: number | null;// null when no budget configured
  tool_count: number;          // enabled tools
  skill_count: number;         // installed skills
  busy: boolean;               // true while a chat.send is in flight
};
```

Session/task/worktree panel methods use the same compact DTO names as
`ui-tui/src/schemas.ts`: `SessionSummary`, `BackgroundTask`, and
`WorktreeStatusResult`. They are status summaries for the TUI, not full
conversation or git APIs.

Extension panel methods return `ExtensionListResult` with compact
`ExtensionSummary` rows. Write flows such as plugin install, hook edit, and
MCP server mutation are not part of protocol v1.

Integration panel methods return compact read-only statuses:

```ts
type IntegrationStatus = {
  name: string;
  label: string;
  status: string;
  available: boolean;
  detail: string;
  action: string;
};

type IntegrationsListResult = {
  integrations: IntegrationStatus[];
};

type IntegrationStatusResult = {
  integration: IntegrationStatus;
};
```

Unsupported integration actions are represented through slash-command
`CommandDispatchResult` errors with `metadata.unavailable = true`, not through
these read-only methods.

### `CommandDef` (mirrors `commands/base.py:CommandDef`)

```json
{"name": "help", "description": "...", "category": "core", "aliases": ["?"], "args_hint": "[topic]", "subcommands": [], "cli_only": false}
```

### `ToolSpec` (mirrors `tools/base.py:ToolSpec`)

```json
{"name": "file_read", "description": "...", "enabled": true, "schema": {...}}
```

## Event Kinds

### Runtime events (forwarded from `RuntimeEvent.to_dict()`)

| Kind             | Payload shape                                     |
|------------------|---------------------------------------------------|
| `turn_started`   | `{turn: number}`                                  |
| `content_delta`  | `{delta: string}`                                 |
| `tool_call`      | `{tool_call: {id, name, arguments}}`              |
| `tool_result`    | `{tool_result: {tool_use_id, content, is_error}}` |
| `message_done`   | `{response: ChatResponse}`                        |
| `turn_finished`  | `{turn, reason}`                                  |
| `loop_stopped`   | `{reason, turn?}`                                 |
| `error`          | `{error: string}`                                 |

### Gateway events

| Kind                | Payload shape                          | When                          |
|---------------------|----------------------------------------|-------------------------------|
| `gateway.ready`     | `{version: string, pid: number}`       | After backend init, before first request is accepted. |
| `gateway.shutdown`  | `{reason: string}`                     | Just before the backend exits. |

## Error Codes

JSON-RPC inspired:

| Code     | Meaning                                              |
|----------|------------------------------------------------------|
| `-32700` | Parse error (invalid JSON frame)                     |
| `-32600` | Invalid request (missing/bad fields)                 |
| `-32601` | Method not found                                     |
| `-32602` | Invalid params                                       |
| `-32001` | Runtime busy (a `chat.send` is already in flight)    |
| `-32002` | Request rejected (e.g. `chat.cancel` for a request_id that no longer exists) |
| `-32003` | Provider auth required                               |
| `-32004` | Provider call failed (network/HTTP/etc.)             |
| `-32099` | Unknown server error (with `data.traceback` in dev)  |

> **Cancellation semantics**: a `chat.send` cancelled mid-flight returns a
> normal `response` with `result.status = "cancelled"` (not an error). The
> `-32002` code is reserved for `chat.cancel` itself when the target
> `request_id` is unknown or already finished.

## Lifecycle

```
backend start
  → backend writes {"type":"event","kind":"gateway.ready",...}
  → frontend may now send requests

frontend → {"type":"request","id":1,"method":"runtime.status","params":{}}
backend  → {"type":"response","id":1,"result":{...}}

frontend → {"type":"request","id":2,"method":"chat.send","params":{"prompt":"hi"}}
backend  → {"type":"event","kind":"turn_started","payload":{"turn":1},"request_id":2}
backend  → {"type":"event","kind":"content_delta","payload":{"delta":"He"},"request_id":2}
backend  → {"type":"event","kind":"content_delta","payload":{"delta":"llo"},"request_id":2}
backend  → {"type":"event","kind":"message_done","payload":{...},"request_id":2}
backend  → {"type":"event","kind":"turn_finished","payload":{...},"request_id":2}
backend  → {"type":"response","id":2,"result":{"status":"completed",...}}

frontend → {"type":"request","id":3,"method":"gateway.shutdown","params":{}}
backend  → {"type":"event","kind":"gateway.shutdown","payload":{"reason":"client_request"}}
backend  → {"type":"response","id":3,"result":{}}
backend exits with code 0
```

## Concurrency

The backend has **at most one in-flight `chat.send`** at a time, but
read-only / control methods are dispatched on a separate task and may
overlap with it.

- **Mutating turn-bound methods** — `chat.send`, `session.new` — are queued.
  If a `chat.send` is in flight and the frontend issues another, the second
  one fails fast with `-32001 runtime busy`.
- **Read-only methods** — `runtime.status`, `commands.list`, `tools.list`,
  `session.list`, `tasks.list`, `worktree.status`, `mcp.list`,
  `plugins.list`, `agents.list`, `hooks.list`, `integrations.list`, and
  `integrations.status` — always run immediately on a worker task and never
  block the event stream.
- **Control methods** — `chat.cancel`, `gateway.shutdown` — also run
  immediately. `chat.cancel` sets the `AgentLoop` stop signal; the running
  `chat.send` finishes with `result.status = "cancelled"`. If the
  `request_id` to cancel is unknown or already finished, the
  `chat.cancel` response carries `error.code = -32002`.

## Versioning

The first version of this protocol is `1.0`. The frontend should send
`{"type":"request","id":0,"method":"runtime.status","params":{}}` immediately
after receiving `gateway.ready` and read `result.protocol_version`.
Mismatched **major** versions abort startup with a clear error to the user.
