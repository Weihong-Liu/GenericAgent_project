# Task Report

## Scope Completed

- Created a new isolated Python project scaffold at workspace root `ga_engineered/`.
- Added `pyproject.toml` for `uv`-managed development.
- Added provider registry, command registry, config resolution, auth store, and
  runtime skeleton modules.
- Added company-style development plan in `tasks.json`.
- Added unit tests for the first foundation modules.
- Completed `GAE-004` with layered runtime configuration:
  defaults < user config < project config < environment < CLI overrides.
- Retained legacy `.generic-agent.yaml` discovery from nested project
  directories and proxy/env boolean parsing coverage.
- Added free-code-style JSON settings support through
  `.generic-agent/settings.json` and `GA_CONFIG_JSON`, including `"env": {...}`
  blocks.
- Moved task reporting into `tasks/` and recorded the configuration/reporting
  conventions in `tasks.json`.
- Completed `GAE-006` with OpenAI Codex OAuth PKCE primitives:
  deterministic S256 challenge generation, authorization URL/session creation,
  loopback callback capture, injectable token exchange/refresh transport, and
  AuthStore-backed logout.
- Registered `/login [provider=openai-codex]` metadata so the command layer can
  expose Codex OAuth as the first login flow.
- Completed `GAE-007` with concrete provider clients for OpenAI Responses,
  OpenAI-compatible Chat Completions, Anthropic Messages, and Codex OAuth.
- Added normalized streaming events, `ChatResponse`/`ToolCall` aggregation,
  tool schema conversion, provider error mapping, and a provider factory.
- Recorded the new requirement that `/login openai-codex --headless` must avoid
  browser launch and print/wait for callback credentials in the command layer.
- Completed `GAE-008` with provider-neutral runtime `Message`, `ToolCall`,
  `ToolResult`, `ChatResponse`, and `RuntimeEvent` models.
- Moved provider-facing chat/event types to the runtime layer while preserving
  `providers.base` re-export compatibility.
- Completed `GAE-009` with a provider-neutral `AgentLoop`, explicit turn
  lifecycle events, final-response path, tool-call continuation, max-turns
  stop result, and stop-signal result.
- After Ruff was installed locally, cleaned up existing lint findings and added
  `uv run ruff check .` to the verified gate.
- Completed `GAE-010` with provider-neutral token budget estimation, turn-based
  history compaction, explainable compaction summaries, and optional AgentLoop
  pre-provider compaction when a token budget is configured.
- Completed `GAE-011` with provider-neutral tool schema/spec abstractions,
  permission metadata separated from provider schemas, a `ToolRegistry` with
  register/resolve/enable/disable behavior, and normalized `ToolResult`
  execution output.
- Completed `GAE-012` with workspace-root constrained file read/write/patch
  tools, safe `{{file:path:start:end}}` expansion, ranged and keyword reads,
  truncation metadata, and unique-match-only patch behavior.
- Completed `GAE-013` with separated shell and Python code execution tools,
  timeout and stop-signal process termination, stdout streaming callbacks,
  command risk classification, and yolo-only bypass for commands requiring
  approval.
- Completed `GAE-014` with browser bridge/session abstractions, TMWebDriver-style
  result normalization, dependency-free HTML simplification, legacy
  `web_scan`/`web_execute_js` tool names, independent active-tab state, and
  output budgets for page scans and JS return values.
- Extended browser tooling with `web_open`, which opens http(s) URLs or search
  queries in the system browser before optional bridge-backed scan/JS execution.
- Completed `GAE-016` with a CLI package bootstrap, `--version` fast path,
  structured doctor diagnostics for provider/auth/state/tool/command readiness,
  status rendering for session/model/provider/home paths, and CLI-focused tests.
- Completed `GAE-017` with Rich/plain console selection, startup banner,
  model/provider statusbar rendering, disable-able tool progress animation,
  prompt-toolkit slash command completion sourced from the command registry, and
  non-TTY/plain fallback tests.
- Extended `GAE-017` with a Python prompt-toolkit TUI shell inspired by
  `free-code` and `hermes-agent`: `gae --tui`, `gae tui`, and empty
  `gae chat` all enter the same interface, with slash completion, status
  toolbar, local prompt history, deterministic test input, and plain fallback.
- Added `ChatTurnService` so TUI non-slash prompts now call the active provider
  through `AgentLoop`; missing API key or OAuth token errors are surfaced
  explicitly instead of returning a placeholder response.
- Attached the default file/shell/code/browser tool registry to TUI chat turns
  and command context, so providers receive tool schemas and `/tools` can show
  `web_open`, `web_scan`, and `web_execute_js`.
- Hardened the existing browser tool path without adding a web-fetch fallback:
  local TMWebDriver `/link` requests bypass inherited proxy environment
  variables, TUI `tool< ... error` lines include concise tool error details,
  and shell risk classification distinguishes `curl ... || echo` fallback from
  a real `curl ... | sh` download pipe.
- Completed `GAE-018` with decoupled slash command handlers for session,
  configuration/auth, tools/doctor, memory, and skills; wired `gae chat /...`
  through `CommandRouter`; added unknown-command suggestions, command
  availability filtering, and headless OpenAI Codex login output that does not
  call `webbrowser`.
- Completed `GAE-019` with a SQLite `SessionStore`, WAL-enabled schema
  initialization, `sessions`/`messages` tables, FTS5-backed message search,
  provider-neutral `Message` round-trip persistence, and `parent_session_id`
  branches with optional message copying.
- Completed `GAE-020` with layered `MemoryIndex`/`MemoryService`, legacy
  `GenericAgent/memory` migration loading, L1/L2/L3/L4 classification, reviewed
  memory writes, SOP draft generation from successful task summaries, and
  duplicate skill detection before crystallization.
- Completed `GAE-021` with a `compat` migration surface, legacy task/reflect
  file-I/O shims, `tests/compat` fixtures for no-tool final response,
  `file_read`, and `code_run`, plus a `docs/MIGRATION.md` entry/tool mapping.
- Completed `GAE-022` with `CHANGELOG.md`, `docs/RELEASE_CHECKLIST.md`,
  release document/link validation tests, all task statuses marked done, and a
  final release verification matrix.

## Verification

- `python3 -m json.tool tasks.json`
- `python3 -m unittest discover -s tests`
- `UV_CACHE_DIR=/tmp/ga-engineered-uv-cache uv run --no-sync pytest`
- `python3 -m compileall -q src tests`
- `UV_CACHE_DIR=/tmp/ga-engineered-uv-cache uv run --no-sync ruff check .`
- `UV_CACHE_DIR=/tmp/ga-engineered-uv-cache uv run --no-sync mypy src`
- `PYTHONPATH=src python3 -m generic_agent_engineered.cli --version`
- `PYTHONPATH=src python3 -m generic_agent_engineered.cli doctor`
- `PYTHONPATH=src python3 -m generic_agent_engineered.cli status`
- `PYTHONPATH=src python3 -m generic_agent_engineered.cli --plain --no-animations chat /status`
- `PYTHONPATH=src python3 -m generic_agent_engineered.cli --plain --no-animations chat /tools`
- `printf '/status\n/exit\n' | PYTHONPATH=src python3 -m generic_agent_engineered.cli --plain tui`
- `printf '/tools\n/exit\n' | PYTHONPATH=src python3 -m generic_agent_engineered.cli --plain tui`
- `python3 -m unittest tests.test_ui tests.test_cli`
- `python3 -m unittest tests.test_chat tests.test_ui tests.test_cli`
- `UV_CACHE_DIR=/tmp/ga-engineered-uv-cache uv run --no-sync gae --version`
- `PYTHONPATH=src python3 -m generic_agent_engineered.cli task /tmp/ga-engineered-task-smoke --input /status`
- `test -f CHANGELOG.md`
- `test -f docs/RELEASE_CHECKLIST.md`
- `test -f tasks/TASK_REPORT.md`
- `test ! -e TASK_REPORT.md`
- `git diff --check`
- `python3 -m unittest tests.test_browser_tools tests.test_shell_tools tests.test_ui`

Result: all checks passed locally.

## Not Run

- Live provider calls, live OAuth callback exchange, and exact model tokenizer
  accounting are not run in local unit tests.

## Important Notes

- This is a greenfield engineering track. It does not modify the legacy
  `GenericAgent` runtime yet.
- Future project-level configuration files belong under `.generic-agent/`;
  future global configuration files belong under `$GENERIC_AGENT_HOME/`.
- OAuth implementations are intentionally staged. The current code covers
  PKCE, local callback capture, mocked token exchange/refresh seams, and
  AuthStore persistence. Browser launch and live OpenAI endpoint validation are
  deferred until the CLI/provider runtime tasks.
- Provider clients are HTTP-capable through lazy `httpx` transports, but unit
  tests inject fake transports and never touch live providers.
- Runtime message serialization intentionally omits provider raw response
  payloads. Raw provider events should go to a later tracing/logging layer if
  needed.
- Token budget uses a deterministic heuristic estimator for runtime decisions.
  Exact model tokenizer accounting is intentionally deferred to provider/model
  adapters.
- Tool permissions are metadata only for now. File, shell, and browser tools now
  apply their own concrete safety/budget boundaries; registry-level approval UI
  remains deferred.
- File tools currently target UTF-8 text files. Binary/image/notebook handling is
  deferred to dedicated tool tasks if needed.
- Shell permission classification is a conservative local rule set, not a full
  shell parser. It blocks known dangerous patterns until a richer approval UI
  and parser-backed policy layer exists.
- Browser testing uses fake bridges only. Live TMWebDriver/CDP browser integration
  is intentionally deferred until the interactive runtime wiring task.
- CLI diagnostics are local readiness checks. Missing auth is a warning so a
  clean scaffold can still pass `doctor`; live provider credential validation is
  deferred to login/provider integration tasks.
- Rich and prompt-toolkit imports have plain fallbacks so local `python3`
  verification still works before `uv sync`; `uv` remains the canonical managed
  environment for full interactive behavior.
- Slash command handlers currently execute local command behavior and return
  metadata for future REPL/runtime integration; provider retry/resume still
  needs wiring to the new session store.
- Loopback OAuth server tests skip under pytest when the local sandbox denies
  binding a 127.0.0.1 port; mocked OAuth token exchange remains covered.
- Session store currently persists runtime messages and search index only; wiring
  it into `/resume`, checkpoints, and the interactive REPL is staged in later
  tasks.
- Memory service is local-file based for now. Runtime-triggered crystallization,
  reviewer UI, and checkpoint-backed memory promotion remain later integration
  work.
- Compatibility task/reflect shims preserve old file I/O contracts. The TUI
  now provides the interactive shell, local slash command surface, and live
  provider-backed chat turn path; broader task execution remains the next
  integration step.
- Release checklist links and task completion state are validated by
  `tests/test_release_docs.py`.
- In the current no-network sandbox, plain `uv run ...` tried to rebuild the
  local package and fetch `setuptools>=68.0`, which failed due network
  restrictions. Verification used `uv run --no-sync ...` against the already
  installed uv environment.

## Planned Next Track

- Added the M7/M8 TUI redesign track to `tasks.json`.
- Added `tasks/TUI_REDESIGN_PLAN.md` with the Textual-first route, runtime
  event protocol, future TS/Ink boundary, `GenericAgent`/`ga` default TUI
  command behavior, welcome page direction, and realtime tool/command rendering
  requirements.
- The plan keeps Python as the only Agent runtime backend. A future TS frontend
  must talk to Python through `gae runtime serve --stdio` and must not duplicate
  provider/tool/session logic.

## GAE-031 — Gateway 协议设计与 M9 登记 (2026-04-25)

### Decision

Per user direction, the M7 (Textual TUI) and M8 (optional TS prototype)
tracks are **superseded** by a new milestone **M9 "TypeScript TUI Primary
Frontend"**. The Python prompt-toolkit TUI under
`src/generic_agent_engineered/ui/` will be deleted in GAE-037; a TypeScript /
Ink frontend in `ga_engineered/ui-tui/` becomes the only TUI, talking to a
Python `gateway` backend over stdio JSON-RPC. Console scripts `GenericAgent`,
`ga`, and `gae` will all launch the TS TUI.

### Scope Completed

- `tasks/TUI_TS_PROTOCOL.md` defines the wire protocol:
  - Transport: line-delimited UTF-8 JSON over stdio; stderr reserved for
    diagnostics.
  - Frame types: `request`, `response`, `event` (with optional `request_id`).
  - Methods: `chat.send`, `chat.cancel`, `commands.list`, `commands.dispatch`,
    `tools.list`, `runtime.status`, `session.new`, `gateway.shutdown`.
  - Strict result schemas (`ChatSendResult`, `RuntimeStatus`, etc.) declared
    inline so both Python and zod can derive validators from one source.
  - 8 runtime event kinds reused verbatim from `RuntimeEvent.to_dict()`,
    plus two gateway events (`gateway.ready`, `gateway.shutdown`).
  - Error code allocation (`-32700`/`-32600`/`-32601`/`-32602` standard;
    `-32001` runtime busy; `-32002` request rejected; `-32003` auth required;
    `-32004` provider error; `-32099` unknown server error).
  - Cancellation semantics clarified: a cancelled `chat.send` returns a
    normal response with `status: "cancelled"`; `-32002` is reserved for
    `chat.cancel` against an unknown / already-finished `request_id`.
  - Concurrency policy: single in-flight `chat.send`; read-only and control
    methods dispatch on a worker task and never block the event stream.
- `tasks.json`:
  - M7 / M8 marked `superseded` with `superseded_by: "M9"` and a
    `supersede_reason`.
  - GAE-024…GAE-030 each marked `superseded_by_*` pointing at their M9
    successor.
  - New milestone `M9` recorded with `supersedes: ["M7", "M8"]`.
  - 8 new tasks added: GAE-031 (this one) through GAE-038, covering
    protocol, Python gateway, TS scaffold + client, branding, tool
    timeline, slash overlay + status bar, entry-point cutover and old-TUI
    deletion, build / e2e / docs.
  - Stale references cleaned: assumptions[] block describing M7 Textual
    work rewritten to point at M9; open question Q1 default updated to the
    `GenericAgent / ga / gae` cutover; `current_verification` note that
    `--plain / --no-animations` flags are removed in M9.
- Task plan reviewed by `codex:codex-rescue`; review feedback was applied:
  - Added `protocol_version` and full `tokens_used / tokens_budget /
    tool_count / skill_count / busy / max_turns` fields to `RuntimeStatus`.
  - Disambiguated `-32002` vs `status: "cancelled"`.
  - Added App shell ownership to GAE-033 (`App.tsx`, `transcriptStore.ts`,
    `schemas.ts`).

### Verification

- `python3 -m json.tool ga_engineered/tasks.json` parses cleanly.
- Codex review (one round) returned implementable verdict; all listed
  concrete issues addressed in the same task.

### Not Tested / Deferred

- The protocol is design-only here. Behavioural validation happens in
  GAE-032 (Python gateway tests) and GAE-033 (TS gatewayClient tests).
- Versioning policy assumes a single major version `1.0` for the M9 cycle;
  bumping to `2.0` is not yet specified.

## GAE-032 — Python Gateway stdio JSON-RPC Service (2026-04-25)

### Scope Completed

- New package `src/generic_agent_engineered/gateway/`:
  - `protocol.py` — frame types (`Request` / `Response` / `Event`), the
    `ProtocolError` exception, error code constants, `encode_frame` and
    `parse_request`.
  - `server.py` — `GatewayServer` and `serve_stdio()` async entry. One
    line-per-frame inbound parser, eight method handlers (`chat.send`,
    `chat.cancel`, `commands.list`, `commands.dispatch`, `tools.list`,
    `runtime.status`, `session.new`, `gateway.shutdown`), in-flight task
    tracking, single-slot busy guard for `chat.send`.
  - `__main__.py` — `python -m generic_agent_engineered.gateway` runner.
  - `__init__.py` — package surface.
- `runtime/agent_loop.py`: optional `event_sink: EventSink | None` parameter.
  Every `events.append(event)` is now `await self._emit(event, events)`,
  which mirrors the event to the sink in real time. When no sink is
  passed, the loop behaves exactly as before; the existing 5 AgentLoop
  unit tests still pass without modification.
- `chat.py`: `ChatTurnService.run_turn` accepts optional `event_sink` and
  `stop_signal` keyword arguments and threads them through `AgentLoop`.
- Tests:
  - `tests/test_gateway_protocol.py` — 18 unit tests covering frame
    encode/decode, parse rejection paths, and result/event frame shapes.
  - `tests/test_gateway_server.py` — 19 integration tests driving the real
    `GatewayServer` against a fake `asyncio.StreamReader` and a captured
    `BytesIO` stdout, with a fake `ChatProvider` injected through
    `ChatTurnService(provider=...)`. Coverage includes: ready event,
    method-not-found, malformed JSON, runtime.status full payload,
    chat.send streaming order, runtime busy rejection, chat.cancel against
    unknown id, chat.cancel mid-stream produces `status: "cancelled"` /
    `is_error: false`, chat.cancel without `request_id` targets the
    in-flight call (and -32002 when idle), `ProviderAuthError` →
    `-32003`, `ProviderError` → `-32004`, `tool_call` / `tool_result`
    events for tool turns, gateway.shutdown exits cleanly.

### Codex Review Round (Applied Fixes)

- **Race window between `chat.send` dispatch and a racing `chat.cancel`**:
  busy claim moved out of `_method_chat_send` into `_handle_line` so that
  the busy slot is set synchronously on the dispatcher path before the
  handler awaits anything. A cancel for the same id is now always
  observed.
- **Cancellation `is_error` correctness**: when a `chat.send` is
  cancelled, the response now reports `is_error: false` alongside
  `status: "cancelled"` (it previously inherited `is_error: true` from
  `ChatTurnResult`).
- **Blocking stdout I/O**: `_write_frame` now wraps the
  `write` + `flush` pair in `loop.run_in_executor(None, ...)` so a
  back-pressured pipe cannot stall the event loop while a large delta
  ships out.
- **Stdin EOF vs shutdown distinction**: only an explicit
  `gateway.shutdown` cancels in-flight tasks. Plain stdin EOF now drains
  in-flight requests (their final responses still reach the client).

### Verification

- `uv run --no-sync pytest -q` → 183 passed (+37 from M9 work).
- `uv run --no-sync ruff check .` → clean.
- `uv run --no-sync mypy src` → 74 source files, 0 issues.
- Smoke test: `python -m generic_agent_engineered.gateway` fed
  `runtime.status` + `gateway.shutdown` round-trips correctly with
  `gateway.ready` and `gateway.shutdown` event frames bracketing the
  responses.

### Not Tested / Deferred

- The blocking-I/O fix is structural only; we did not benchmark a
  back-pressured pipe scenario.
- `runtime.status.tokens_used` is a coarse `len(content) // 4`
  approximation. A token-budget hook lands later when the token-budget
  config is wired into the active session.
- E2E launch from a TS subprocess is GAE-T08 work; the Python side is
  feature-complete here.

## GAE-033 — TS Scaffold + Gateway Client (2026-04-25)

### Scope Completed

- New `ga_engineered/ui-tui/` workspace (npm, ESM, strict TypeScript):
  - `package.json` — `ink ^6.8`, `react ^19.2`, `ink-text-input`,
    `unicode-animations`, `zod ^4`. Dev deps: `tsx`, `vitest`, `esbuild`,
    `typescript`. Engine: Node ≥ 20.
  - `tsconfig.json` — strict, `exactOptionalPropertyTypes: true`,
    `noUncheckedIndexedAccess: true`.
  - `esbuild.config.mjs` — single-file ESM bundle (`dist/bundle.js`,
    ~2.2 MB), Node 20 target, `react-devtools-core` marked external.
  - `vitest.config.ts` — Node env, picks up `__tests__` folders.
- `src/schemas.ts` — zod runtime schemas mirroring
  `tasks/TUI_TS_PROTOCOL.md`. Strict `RuntimeStatus`, `ChatSendResult`,
  `CommandDef`, `ToolSpec`, plus per-event payload schemas
  (`toolCallPayloadSchema`, `toolResultPayloadSchema`).
- `src/types.ts` — UI-side `RuntimeEventKind` plus gateway event kinds.
- `src/gatewayClient.ts` — async client. Spawns
  `python -m generic_agent_engineered.gateway`, owns a `LineSplitter`
  for line-delimited JSON, parses inbound frames (events validated by
  zod, responses dispatched by raw `id`/`error` peek), exposes
  Promise-based RPCs (`runtimeStatus`, `commandsList`,
  `commandsDispatch`, `toolsList`, `sessionNew`, `chatSend`,
  `chatCancel`, `shutdown`) and `EventEmitter`-based event subscription.
  Includes `FakeChild` test double.
- `src/state/transcriptStore.ts` — pure reducer over
  `TranscriptState` with five item kinds (user / assistant / tool /
  system / error). Streams `content_delta` into the active assistant
  bubble; opens / closes tool nodes from `tool_call` + `tool_result`;
  validates per-event payloads via zod and surfaces malformed payloads
  as visible error items.
- `src/App.tsx` — Ink top-level component. Wires gatewayClient events
  into the reducer, owns the `TextInput` composer, renders the
  transcript and a status bar. Ctrl-C cancels in flight (via
  `useRef`), second Ctrl-C exits cleanly.
- `src/entry.tsx` — `node` entry. Awaits `gateway.ready`, fetches
  initial `runtime.status`, renders `<App />`. On ready failure, shuts
  down the Python child before exiting.
- Tests:
  - `__tests__/gatewayClient.test.ts` — 13 vitest cases covering line
    splitter (incl. split frames), `ready` resolve / protocol-mismatch
    reject, `runtime.status` round-trip, error response → `GatewayError`,
    schema-mismatch → `GatewayProtocolError`, event subscriber dispatch,
    malformed-frame fallback, `chatSend` request-id, child-error path.
  - `__tests__/transcriptStore.test.ts` — 10 vitest cases covering all
    item-kind transitions, late `content_delta` after `end_turn`, and
    malformed `tool_call` surfacing as an error item.

### Codex Review Round (Applied Fixes)

- **Ctrl-C race with `useState` (App.tsx)**: introduced
  `activeRequestRef` so Ctrl-C reads the in-flight id synchronously.
  Without this, a Ctrl-C during the gap between `client.chatSend()` and
  the next React render would have orphaned the active turn.
- **Out-of-order `content_delta` after `end_turn`**: the reducer's
  fallback branch now requires `state.activeTurn === turnId` before
  spawning a fresh bubble, so a late delta cannot create a phantom
  streaming bubble that never finishes.
- **Schema robustness**: `chatSendResultSchema.error_type` /
  `retry_reason` switched from `.nullable()` to `.nullish()` so a
  future Python change that omits empty fields will not break parsing.
- **EventEmitter listener cap**: `setMaxListeners(0)` in the
  `GatewayClient` constructor to silence the default 10-listener
  warning under realistic UI subscription counts.
- **`shutdown()` hygiene**: now also calls `failPending(...)` and
  `removeAllListeners('data')` on stdout/stderr in the `finally`
  block, so a hung `gateway.shutdown` RPC cannot leave dangling
  promises or stream handlers.
- **Orphaned Python child on `ready()` rejection**: `entry.tsx` now
  calls `client.shutdown()` (best-effort) before `process.exit(1)` so
  protocol-mismatch and similar startup failures still reap the
  subprocess.
- **Per-event payload validation**: added
  `toolCallPayloadSchema` / `toolResultPayloadSchema` and made the
  reducer use `safeParse`. Malformed payloads now surface as user-
  visible error items rather than silent drops.

### Verification

- `npm run type-check` — clean (strict TypeScript with all the
  above-mentioned strict flags).
- `npm test` — 23 vitest tests passing (13 gatewayClient + 10
  transcriptStore).
- `npm run build` — `dist/bundle.js` produced (~2.2 MB ESM).
- Smoke test: spawning `python3 -m generic_agent_engineered.gateway`
  from a Node script via `child_process.spawn` and feeding the same
  byte stream the gatewayClient reads round-trips `gateway.ready` and
  `runtime.status` correctly. (Python side runs from
  `PYTHONPATH=src`.)

### Not Tested / Deferred

- No Ink rendering tests yet — visual / branded layout lands in
  GAE-T04 and gets snapshot-tested there.
- `dist/bundle.js` size is unoptimised (no minify, no tree-shake hints
  beyond defaults). Acceptable for a CLI invoked via `node bundle.js`;
  size optimisation is GAE-T08 work.
- Slash overlay, status bar polish, and the full transcript
  scroll-back layout are GAE-T06 work.
- The hand-rolled `TextInput` + completion will replace
  `ink-text-input` in GAE-T06.

## GAE-034 — Welcome Page + Branding (2026-04-25)

### Scope Completed

- `ui-tui/src/banner.ts`:
  - `LOGO_ART` — six-line "GENERIC AGENT" block-letter brand mark in
    the ANSI Shadow font (103 cols wide).
  - `EMBLEM_ART` — 14-row, 30-col Caduceus-style decorative pixel art,
    matching the visual style of hermes-agent's left panel.
  - `COMPACT_LOGO` — narrow fallback for terminals under the wide
    threshold.
  - Three-tier palette helper (`gold`, `amber`, `bronze`, `dim`) and
    `colorize()` that paints a per-row gradient onto the art, exactly
    as hermes-agent does.
  - `WIDE_LOGO_THRESHOLD` and `SPLIT_LAYOUT_THRESHOLD` derived from
    the actual measured art widths so a future re-design cannot
    accidentally introduce a horizontal overflow.
- `ui-tui/src/components/branding.tsx`:
  - `Welcome` component with three layout tiers — emblem + logo +
    session split (>= SPLIT_LAYOUT_THRESHOLD), stacked logo + session
    (>= WIDE_LOGO_THRESHOLD), compact mark + tip (otherwise).
  - `Banner`, `EmblemPanel`, `SessionPanel` exported separately so
    later work can reassemble them in a different shell if needed.
  - `SessionPanel` reads provider / model / session_id / tool_count /
    skill_count / turn count / max_turns from a `RuntimeStatus` prop.
- `ui-tui/src/App.tsx`:
  - Renders `<Welcome />` persistently at the top of every frame —
    matching hermes-agent's behaviour where the welcome panel stays
    visible above the transcript rather than disappearing on first
    user input.
  - Tracks terminal width via `useStdout` and a guarded
    `stdout.on('resize', ...)` subscription so the welcome layout
    re-tier on resize. The handler is no-op when stdout is not a TTY.
- `ui-tui/src/__tests__/banner.test.ts` — 10 vitest cases pinning row
  widths, the gradient mapping, the threshold relationships, and the
  `selectLogo` fallback boundary.

### Codex Review Round (Applied Fixes)

- **Logo overflow**: codex caught that `LOGO_ART` is actually 103 cols
  but the original `WIDE_THRESHOLD = 95` would have overflowed every
  terminal between 95 and 102 cols. Replaced with
  `WIDE_LOGO_THRESHOLD = LOGO_WIDTH + 1` (104) and added
  `SPLIT_LAYOUT_THRESHOLD = LOGO_WIDTH + EMBLEM_LOGO_GAP + EMBLEM_WIDTH + 1`
  (136) for the side-by-side layout.
- **Welcome only-when-empty**: original code rendered Welcome only
  while the transcript was empty, so it disappeared on the first
  message. Now persistent at the top, matching hermes-agent.
- **Resize handler crash on non-TTY**: added
  `typeof stdout.on === 'function'` guards on both the `.on` and
  `.off` calls so a piped or mocked stdout no longer throws.
- **Test enshrined wrong boundary**: rewrote the threshold tests to
  derive expectations from `LOGO_WIDTH` rather than hard-coded 95, so
  a row-width regression now fails the test.

### Verification

- `npm run type-check` — clean (strict).
- `npm test` — 33 passing (10 banner + 13 gatewayClient + 10
  transcriptStore).
- `npm run build` — `dist/bundle.js` builds without warnings.

### Not Tested / Deferred

- No Ink rendering snapshot tests; layout correctness was verified by
  reasoning about widths, not pixel-comparing rendered frames.
  Snapshot harness lands in GAE-T08.
- Custom logo override (per-user `customLogo` prop) not yet exposed
  through configuration; hermes-agent allows this via Rich markup. Can
  be added when CLI configuration is extended.

## GAE-035 — Real-time Tool Display + Spinner (2026-04-25)

### Scope Completed

- `ui-tui/src/hooks/useSpinner.ts`:
  - `useSpinnerState(name, options)` — returns `{ frame, index }` for
    the named braille spinner and ticks via `setInterval`. Supports
    `paused` and a custom `interval` override.
  - `useSpinner(name, options)` — convenience wrapper returning just
    the frame string.
- `ui-tui/src/components/spinner.tsx`:
  - `<SpinnerText name? color? paused? />` — drops a single-line
    braille spinner anywhere; default is `cascade` in yellow.
  - `<StreamCursor color? />` — blinking ▍ cursor used at the tail of
    a streaming assistant bubble. Drives the blink off the spinner's
    frame *index* parity (not character-length parity), so a future
    change to the underlying braille frames cannot freeze the cursor.
- `ui-tui/src/App.tsx`:
  - `TranscriptRow` for assistant items now renders `<StreamCursor />`
    while `streaming === true` instead of a static "▍".
  - New `ToolRow` extracts the running-tool render path: uses
    `<SpinnerText />` while `status === "running"`, swaps in `✓` /
    `✗` once the tool resolves, shows elapsed-seconds and result
    preview as in the previous static version.
- `ui-tui/src/__tests__/useSpinner.test.tsx`:
  - 3 cases asserting that the underlying `unicode-animations` data is
    well-formed (frame strings non-empty, all glyphs in the U+2800
    block, intervals positive) and the hook export signature is the
    expected `(name?, options?)`.
  - 2 modeled cases for the index-wrap state machine (the actual hook
    requires a React renderer that vitest's Node env doesn't ship; the
    pure model covers wrap and zero-frame edge cases).

### Codex Review Round (Applied Fixes)

- **`StreamCursor` parity hack**: codex flagged that the original
  implementation read the cursor visibility off `frame.length % 2`,
  which depended on accidental UTF-16 code-unit parity in the
  `breathe` spinner data. Replaced with `index % 2`, derived from the
  new `useSpinnerState` hook so the visibility cycles deterministically
  regardless of the spinner data shape.
- **Dead `options` prop on `SpinnerTextProps`**: removed; the
  component already passed primitive `paused` directly.
- **Redundant `color` / `name` overrides on `<SpinnerText />` inside
  `ToolRow`**: dropped — `SpinnerText`'s defaults (`cascade` / yellow)
  already match the running-tool theme.
- **Redundant `% total` guard** in the frame lookup: removed; the
  setter already wraps via `(idx + 1) % total`.

### Verification

- `npm run type-check` — clean (strict).
- `npm test` — 38 passing (10 banner + 13 gatewayClient + 10
  transcriptStore + 5 useSpinner).
- `npm run build` — `dist/bundle.js` builds (~2.2 MB).

### Not Tested / Deferred

- The actual React-driven setInterval tick is not exercised by tests
  because `react-test-renderer` is not installed and pulling it in
  for a single hook isn't worth the dep weight. A modeled
  pure-function test covers the wrap math; the visual / timing path
  is covered by the e2e harness in GAE-T08.
- N concurrent spinners create N intervals. Acceptable for typical
  1–3 tool fan-out per turn; if a future workflow does heavy
  parallel tool fan-out, refactor to a single shared ticker via
  context.

## GAE-036 — Slash Overlay + Input + Status Bar (2026-04-25)

### Scope Completed

- `ui-tui/src/state/commandFilter.ts`:
  - `filterCommands(commands, query)` — pure helper that returns the
    matching commands sorted by score (name-exact > name-prefix >
    alias-exact > alias-prefix > name-substring > alias-substring).
  - `applyCompletion(command)` — produces the draft replacement when
    the user accepts a suggestion (adds a trailing space when the
    command has an `args_hint`).
- `ui-tui/src/components/slashOverlay.tsx`:
  - Floating-style suggestion list. Highlights the selected row,
    shows description + args hint, summarises overflow as
    "…and N more", and renders a `↑↓ navigate · Tab complete · Enter
    run` hint footer.
- `ui-tui/src/components/statusBar.tsx`:
  - `provider · model · turn N/max · tokens M/budget · tools T ·
    busy/idle · /help /commands /exit`. Token segment turns yellow at
    75 % budget and red at 90 %; turn segment turns red when the
    AgentLoop max is hit. Warning colours drop the dim attribute so
    they are legible on dark terminals.
- `ui-tui/src/App.tsx`:
  - Caches `commandsList()` once at startup; surfaces a system error
    item if the RPC fails (otherwise the user has no clue why Tab
    does nothing).
  - `useInput` block now handles Ctrl-C, ↑/↓ navigation in the
    overlay, and Tab to apply the highlighted completion.
  - `<TextInput focus={!overlayActive} />` so ink-text-input does
    not also receive Tab as a literal character.
  - Slash overlay rendered **above** the input box so a tall match
    list cannot push the prompt off short terminals.
- `ui-tui/src/__tests__/commandFilter.test.ts` — 11 vitest cases
  including a regression case for "alias order must not change the
  score".

### Codex Review Round (Applied Fixes)

- **Tab race with `ink-text-input`**: codex flagged that `useInput`
  and `ink-text-input` both consume Tab on the same stdin stream, so
  a Tab press could both invoke completion *and* append a literal
  tab character to the controlled draft. Fixed with
  `<TextInput focus={!overlayActive} />`.
- **Multi-alias scoring bug**: the original `scoreCommand` returned
  on the first matching alias, so an alias array of `["qu", "q"]`
  queried with `"q"` would score 70 (prefix) instead of 80 (exact).
  Rewritten to scan all aliases and keep the best score; added a
  regression test for alias order independence.
- **Stale `selectedSuggestion` on filter swap**: original effect
  reset only when the *length* changed, so a filter that swapped
  which commands matched without changing the count left the
  selection pointing at a stale row. Now keyed off the joined match
  names so any change to the match identity resets the highlight.
- **Silent `commands.list` failure**: the catch handler was a
  no-op; it now dispatches a `command_output` system error so the
  user sees a visible "slash-command catalogue unavailable" line.
- **`dimColor` + red contrast**: dropped the dim attribute on the
  token and turn segments when they switch to a warning colour so
  the warning is legible on dark terminals.
- **Overlay below input clipping the prompt**: re-ordered the JSX so
  the overlay renders above the `<TextInput>`. A 6-row match list
  + footer no longer pushes the input off-screen on short terminals.

### Verification

- `npm run type-check` — clean.
- `npm test` — 49 passing (11 commandFilter + 10 banner + 13
  gatewayClient + 10 transcriptStore + 5 useSpinner).
- `npm run build` — `dist/bundle.js` ~2.2 MB.

### Not Tested / Deferred

- No interactive Ink test for the Tab handler (would require
  `ink-testing-library` which isn't installed); the focus-suppression
  behaviour relies on documented `ink-text-input` API and is verified
  by manual inspection.
- Token-budget colour state machine has no explicit test; the helper
  is small enough that the assertion would be redundant.

## GAE-037 — Python Entry-point Cutover + Old TUI Removal (2026-04-25)

### Scope Completed

- `pyproject.toml`:
  - `[project.scripts]` now exposes `GenericAgent`, `ga`, and `gae`,
    all pointing at `generic_agent_engineered.cli:main`.
  - Dropped `rich` and `prompt-toolkit` from `dependencies` — they
    were the legacy TUI's only consumers.
  - Added `[tool.setuptools.package-data]` so the wheel includes
    `_tui_dist/bundle.js`.
- `src/generic_agent_engineered/cli/launcher.py` (NEW):
  - Locates the bundled TS frontend via `importlib.resources` and
    runs it through `node`.
  - Default path uses `os.execvp` so signals and the process tree
    belong to node directly. `GA_LAUNCHER_NO_EXEC=1` falls back to
    `subprocess.call` for tests / scripted callers.
  - `GA_TUI_BUNDLE` overrides the bundle location (lets `npm run dev`
    iterate without rebuilding the wheel). `GA_NODE` overrides the
    node binary.
  - Returns 1 if the bundle is missing, 127 if `node` is missing, 130
    on KeyboardInterrupt.
- `src/generic_agent_engineered/cli/__init__.py` (REWRITTEN):
  - Removed `--tui`, `--plain`, `--no-animations` flags entirely.
  - Bare invocation, `chat` (no prompt or with free-text), and `tui`
    all route through the launcher.
  - `tui` is intercepted before argparse so its flags forward to the
    TS bundle without the top-level parser rejecting them.
  - `chat /<command>` retains one-shot slash-command dispatch (still
    useful for CI / scripts).
- `src/generic_agent_engineered/_tui_dist/__init__.py` (NEW): empty
  package marker so `importlib.resources.files()` can find the
  shipped `bundle.js`.
- DELETED `src/generic_agent_engineered/ui/` (the entire Python
  prompt-toolkit TUI: `tui.py`, `banner.py`, `console.py`,
  `statusbar.py`, `completion.py`, `spinner.py`, `widgets/`).
- DELETED `tests/test_ui.py` — covered the deleted module's
  `SlashCommandCompleter` and `create_console`. Equivalent coverage
  for the TS frontend lives in `ui-tui/src/__tests__/`.
- `tests/test_cli.py` (REWRITTEN):
  - Removed all `--tui`/`--plain`/`--no-animations` cases.
  - New `LauncherRoutingTests`: bare `[]`, `tui`, `chat`,
    `chat hello`, and `tui --example foo` all reach the launcher.
  - New `LauncherInternalsTests`: bundle override via env, missing
    node returns 127, missing bundle returns 1, the default path
    actually calls `os.execvp` with the right argv.

### Codex Review Round (Applied Fixes)

- **Signal / process-tree handling**: codex flagged that
  `subprocess.call` keeps Python as the parent. Switched the default
  path to `os.execvp`; the test suite uses `GA_LAUNCHER_NO_EXEC=1` to
  preserve the previous behaviour for assertions.
- **`tui` argument forwarding**: codex flagged that the original
  argparse setup discarded any args after `tui`. Now `tui` is
  intercepted before argparse — so e.g. `gae tui --profile prod`
  forwards `["--profile", "prod"]` to the TS bundle. Added a
  regression test.
- **No residual `rich` / `prompt_toolkit` imports** elsewhere in the
  source tree (codex audited and confirmed clean).

### Verification

- `uv run --no-sync pytest -q` — **178 passing** (was 172; net +6:
  removed 5 Python-TUI tests, added 11 launcher tests).
- `uv run --no-sync ruff check .` — clean.
- `uv run --no-sync mypy src` — 69 source files (was 74; the 5-file
  delta is the deleted `ui/` package), 0 issues.
- Smoke: `GA_LAUNCHER_NO_EXEC=1 GA_NODE=/usr/bin/false gae tui --foo`
  forwards `--foo` to the bundle and returns 1 (bundle "ran" with the
  fake binary).

### Not Tested / Deferred

- `os.execvp` cannot be exercised in-process by unittest (it would
  replace the test runner). The tests verify the call site by
  patching `os.execvp`; the actual exec semantics are validated by
  manual smoke and by the GAE-T08 e2e harness.
- The wheel-vs-zipped-resource path: the launcher comment documents
  the assumption that `bundle.js` is a real on-disk file. If the
  project ever ships as a zipped wheel or zipapp, the launcher needs
  `importlib.resources.as_file()` plus a copy step to keep the file
  alive across `execvp`.

## GAE-038 — Build / Dist / e2e / Docs / Milestone Close-out (2026-04-25)

### Scope Completed

- `scripts/build_tui.sh`:
  - Runs `npm install` (skipped if `node_modules` exists or
    `SKIP_INSTALL=1`), `npm run type-check`, `npm test`, `npm run
    build`, then copies `ui-tui/dist/bundle.js` into
    `src/generic_agent_engineered/_tui_dist/bundle.js` so the wheel
    includes it via `[tool.setuptools.package-data]`.
  - Documents the bash requirement and the `SKIP_INSTALL` semantics.
- `tests/test_tui_e2e.py`:
  - Spawns `python -m generic_agent_engineered.gateway` directly,
    feeds `runtime.status` + `gateway.shutdown`, asserts that the
    expected `gateway.ready` event, both responses, and the
    `gateway.shutdown` event arrive in the right shape. Skip-guarded
    on `node` / `BUNDLE` so the test only runs on machines that
    *could* host the full chain.
  - Documented as a Python-only e2e; the full launcher → node →
    gatewayClient round-trip needs a TTY (Ink refuses to render
    without one) and is left to manual smoke testing.
- `docs/TUI.md` (NEW): architecture diagram, project layout,
  environment variables, build commands, testing commands, and the
  rationale for the two-language split. Calls out
  `GA_GATEWAY_PYTHON`'s default-to-`python3` quirk so users on
  pyenv / uv don't silently invoke the wrong interpreter.
- `README.md`:
  - Replaced the `gae --tui` quick-start path with `GenericAgent` /
    `ga` / `gae` and a pointer to `scripts/build_tui.sh`.
  - Migration table now points at `GenericAgent` instead of
    `gae chat / gae tui`.
  - Design anchors block updated: rendering is no longer a Python
    concern.
- `CHANGELOG.md`: new `[Unreleased]` section listing the M9 deltas
  (added gateway, console scripts, launcher, build script, e2e;
  changed AgentLoop / ChatTurnService event_sink hook; removed the
  Python TUI, `tests/test_ui.py`, `rich`, `prompt-toolkit`, and the
  three legacy CLI flags).
- `tasks.json`: M9 marked `done`; GAE-031..GAE-038 all marked `done`.
- `tests/test_release_docs.py`: relaxed the `M9 == in_progress`
  assertion to accept either `in_progress` or `done`, so future
  reruns of the suite after this milestone closes don't regress.

### Codex Review Round (Applied Fixes)

- **e2e docstring lied**: original docstring claimed the test went
  through the launcher; rewritten to describe what the test actually
  does (Python-only gateway round-trip).
- **Frame-count comment off by one**: "expect three frames" → "expect
  four frames" in the e2e.
- **`docs/TUI.md` test count stale**: bumped 178 → 179 to reflect the
  new e2e test.
- **`GA_GATEWAY_DEBUG` mis-attributed in CHANGELOG**: clarified that
  it is read by `gateway/server.py`, not by `cli/launcher.py`.
- **`GA_GATEWAY_PYTHON` default surprise**: documented that it
  defaults to `python3` (not the launching interpreter).
- **CHANGELOG section heading**: switched to the standard Keep a
  Changelog `## [Unreleased]` form with the M9 callout in the body.
- **Spurious `chmod +x` on `bundle.js`**: removed; node loads the
  file via `node bundle.js`, never exec's it directly.
- **`SKIP_INSTALL` comment misleading**: clarified that the variable
  only matters when `node_modules` is *missing* (it doesn't force a
  reinstall).

### Verification

- `uv run --no-sync pytest -q` — **179 passing**.
- `uv run --no-sync ruff check .` — clean.
- `uv run --no-sync mypy src` — clean (69 files).
- `cd ui-tui && npm test` — **49 passing**.
- `cd ui-tui && npm run type-check` — clean.
- `scripts/build_tui.sh` round-trips: 2.2 MB bundle staged into
  `_tui_dist/`.
- Smoke: `(echo runtime.status; echo gateway.shutdown) |
  python -m generic_agent_engineered.gateway` round-trips frames.

### Not Tested / Deferred

- The full launcher → node → gatewayClient → python-gateway chain
  is not tested in CI. Adding it requires a `pty` harness so Ink
  can render or a TS-side `--protocol-check` flag that bypasses
  rendering — out of scope for this milestone.
- Bundle-size optimisation: 2.2 MB is acceptable for a CLI invoked
  once per session; minification/tree-shaking can shave it down if
  installs become a concern.

### Milestone close-out

`M9 TypeScript TUI Primary Frontend` is complete. All eight task
deltas (GAE-031..GAE-038) are committed, every quality gate passes,
the legacy Python TUI is gone, and `GenericAgent` / `ga` / `gae` all
land the user in the new TS interface.

## GAE-047 — Free-code TUI 全量缺口扫描 + M11 任务队列 (2026-04-26)

### Scope Completed

- Scanned the free-code TUI entrypoints and high-signal surfaces:
  `src/screens/REPL.tsx`, `src/components/PromptInput/PromptInput.tsx`,
  `src/components/Messages.tsx`, `src/components/VirtualMessageList.tsx`,
  `src/components/MessageRow.tsx`, `src/components/MessageSelector.tsx`,
  `src/commands.ts`, and command/dialog/tool renderer components.
- Compared those areas with the current ga_engineered TypeScript TUI
  (`ui-tui/src/App.tsx`, `components/*`, `state/*`) and Python command
  registry (`src/generic_agent_engineered/commands/registry.py`).
- Added `free_code_tui_parity_scan` to `tasks.json` with the migration
  categories and explicit missing feature groups.
- Added M11 `Free-code TUI Full Parity Migration` and ordered tasks
  GAE-047..GAE-060. The execution rule is now encoded in `tasks.json`:
  implement in ascending task id order, then verify, write this report,
  commit, and continue.

### Missing Free-code TUI Areas Now Tracked

- Prompt input shell: queued commands, stashed prompt restore, quick
  open, global search, model/theme/output-style pickers, thinking mode
  toggles, paste references, IDE mentions, background task/team dialogs.
- Message surface: virtualized transcript, message selection/actions,
  transcript search, sticky prompts, unseen divider, grouped/collapsed
  tool output, and offscreen render safeguards.
- Tool rendering: structured file diffs, bash progress, tool-specific
  renderers, read/search/fetch/todo grouping, and long-output disclosure.
- Commands/settings: free-code command surfaces such as diff, export,
  copy, cost/stats, theme/vim/keybindings/model/effort/statusline,
  output-style, rename/resume/rewind/branch/session/tasks, plugins,
  agents, hooks, MCP, integrations, rate-limit, and release notes.
- Permission/sandbox, session/task/worktree, MCP/plugin/agents/hooks,
  onboarding/status notices, and IDE/desktop/chrome/voice/remote/mobile
  integration surfaces.

### Verification

- `python3 -m json.tool tasks.json` — clean.

### Not Tested / Deferred

- This task is planning and inventory only. Implementation starts at
  GAE-048 and proceeds through the M11 queue.
- The scan is evidence-backed by source traversal, but individual
  command semantics will still be rechecked when each implementation
  task begins so stale assumptions do not leak into code.

## GAE-048 — 浏览器桥接/扫描可靠性 + 工具结果摘要迁移 (2026-04-26)

### Scope Completed

- `assets/tmwd_cdp_bridge/background.js` now sends `current` and
  `windowId` metadata for both `ext_ready` and `tabs_update`, so the
  backend can identify the active browser tab instead of blindly using
  the first scriptable tab.
- `BrowserSessionStore.refresh()` now prefers a tab whose metadata has
  `current: true` when the previous active session is absent.
- `CdpBridge.execute_js()` now gives the HTTP request timeout a margin
  above the script execution timeout. This avoids the Python client
  timing out before the bridge has a chance to return the tool-level
  timeout result.
- Bridge connection failures now include the concrete recovery path:
  start or restart with `uv run gae bridge`, then verify the bundled
  Chrome extension is loaded and connected.
- Browser tool descriptions now warn the model that `web_open` only
  opens a tab, and that failed or empty `web_scan` output must not be
  treated as page content.
- Extracted TUI tool result summaries from `App.tsx` into
  `ui-tui/src/toolSummary.ts`, with payload-aware browser summaries:
  `web_open` includes the host when available, `web_scan` distinguishes
  tabs-only output from scanned text/page content, and errors remain
  explicit.
- Rebuilt `src/generic_agent_engineered/_tui_dist/bundle.js`.

### Verification

- `UV_NO_CACHE=1 /opt/homebrew/bin/uv run python tests/test_browser_tools.py`
  — 12 passing.
- `SKIP_INSTALL=1 ./scripts/build_tui.sh` — TypeScript type-check
  passed; Vitest 16 files / 171 tests passed; bundle rebuilt.
- `python3 -m json.tool tasks.json` — clean.

### Not Tested / Deferred

- Did not launch a real Chrome extension/bridge session from the test
  environment. The bridge metadata and timeout behavior are covered by
  unit tests and the user-facing error now points to the required
  runtime command.
- `uv run pytest` was not rerun for this task because the focused
  browser unittest plus full TUI build cover the changed paths.

## GAE-049 — Free-code dialog/fuzzy-picker 设计系统基础 (2026-04-26)

### Scope Completed

- Added shared TUI primitives:
  - `DialogFrame` for consistent overlay framing, title, instructions,
    footer, and optional bordered dialog presentation.
  - `SearchBox` for prompt/search rows with cursor rendering.
  - `FuzzyPicker` plus `filterFuzzyItems()` and `clampSelection()` for
    reusable keyboard picker rows and deterministic matching.
  - `Tabs` for future multi-pane dialogs.
  - `overlayStackReducer` and `topOverlay()` for future modal/overlay
    ownership instead of ad hoc booleans.
- Migrated existing overlays to the new primitives:
  - `SlashOverlay` now renders command rows through `DialogFrame` and
    `FuzzyPicker`.
  - `FileMentionOverlay` now shares the same picker shell with magenta
    accent styling and loading state preservation.
  - `HistorySearchOverlay` now uses `DialogFrame`, `SearchBox`, and
    `FuzzyPicker` while keeping the existing Ctrl-R keyboard behavior.
  - `HelpOverlay` now uses `DialogFrame` for its bordered dialog.
- Added focused tests for fuzzy matching/selection and overlay stack
  behavior.
- Rebuilt `src/generic_agent_engineered/_tui_dist/bundle.js`.

### Verification

- `cd ui-tui && npm run type-check` — clean.
- `cd ui-tui && npm test` — 18 files / 177 tests passing.
- `SKIP_INSTALL=1 ./scripts/build_tui.sh` — type-check passed, tests
  passed, bundle rebuilt.
- `python3 -m json.tool tasks.json` — clean.

### Not Tested / Deferred

- The new `Tabs` and `overlayStackReducer` are foundation pieces; later
  M11 tasks will wire them into model/theme/search/session dialogs.
- No visual snapshot harness exists for Ink overlays yet. Behavioral
  coverage is via reducers/pure helpers plus the full TypeScript build.

## GAE-050 — PromptInput parity pass 1：footer、队列、stashed prompt、输入状态 (2026-04-26)

### Scope Completed

- Added `promptQueueReducer` plus helpers for FIFO prompt queuing. Queued
  prompts keep detected mode metadata (`chat`, `bash`, `slash`, or
  `mention`) and deterministic ids.
- Added `PromptFooter`, a free-code-style prompt status strip that shows
  current input mode, running state, queued prompt count/next prompt,
  and stashed prompt restore hint.
- `App.tsx` now queues submissions made while a chat turn is running
  instead of starting overlapping turns. Once the current turn finishes,
  queued prompts are executed in FIFO order without duplicating history.
- Local slash commands and `!` shell commands also drain the queue after
  they finish, so queued work continues through mixed command/chat
  sequences.
- Ctrl-G now stashes any non-empty draft before cancelling a running
  turn; Ctrl-Y restores the stashed prompt when the input is empty.
- Added `promptQueue.test.ts`.
- Rebuilt `src/generic_agent_engineered/_tui_dist/bundle.js`.

### Verification

- `cd ui-tui && npm run type-check` — clean after fixing
  `exactOptionalPropertyTypes` handling for optional queue mode.
- `cd ui-tui && npm test` — 19 files / 181 tests passing.
- `SKIP_INSTALL=1 ./scripts/build_tui.sh` — type-check passed, tests
  passed, bundle rebuilt.
- `python3 -m json.tool tasks.json` — clean.

### Not Tested / Deferred

- Queue execution is covered by reducer tests and TypeScript build, but
  not yet by an end-to-end Ink input harness. A future TUI e2e harness
  should exercise live keypresses for queue draining and stash restore.
- Vim input uses the same submit path, but its own history/navigation
  parity remains unchanged in this task.

## GAE-051 — PromptInput parity pass 2：Quick Open、Global Search、Model/Theme/Thinking pickers (2026-04-26)

### Scope Completed

- Added `QuickOpenDialog` on Ctrl-P. It uses the existing
  `files.search` gateway RPC, supports typed filtering, keyboard
  selection, and inserts the picked file as an `@path` mention.
- Added `GlobalSearchDialog` on Ctrl-F. It searches the current
  transcript across user, assistant, system/error, and tool rows, then
  jumps into the message navigator at the selected hit.
- Added `ModelPicker` on Ctrl-M. Because the backend does not yet expose
  a model catalogue, this is intentionally feature-gated to the current
  active model and reports "model unchanged" instead of pretending to
  switch.
- Added `ThemePicker` on Ctrl-T. The current built-in theme is selectable;
  custom themes are shown as feature-gated and produce a warning toast.
- Added `ThinkingToggle` on Ctrl-X as a UI marker with explicit copy
  that backend effort control is deferred to a later command task.
- Added transcript search tests in `globalSearchDialog.test.ts`.
- Rebuilt `src/generic_agent_engineered/_tui_dist/bundle.js`.

### Verification

- `cd ui-tui && npm run type-check` — clean after fixing
  `TranscriptItem` test fixture types.
- `cd ui-tui && npm test` — 20 files / 183 tests passing.
- `SKIP_INSTALL=1 ./scripts/build_tui.sh` — type-check passed, tests
  passed, bundle rebuilt.
- `python3 -m json.tool tasks.json` — clean.

### Not Tested / Deferred

- No backend model catalogue, theme backend, or effort-control command
  exists yet. These controls are keyboard-operable but explicitly
  feature-gated where backend support is missing.
- Quick Open and Global Search keypress behavior is not covered by an
  Ink e2e harness yet; pure transcript search logic and the full build
  are covered.

## GAE-052 — 消息面板 parity：虚拟列表、搜索、选择、动作 (2026-04-26)

### Scope Completed

- Extracted transcript row rendering from `App.tsx` into
  `MessageRow`, preserving user, assistant, streaming, system/error,
  and tool-result rendering behavior.
- Added `VirtualMessageList` with deterministic windowing. Long
  transcripts now render a bounded tail window by default and keep a
  selected row visible when the message navigator/search selects an
  older item.
- Added hidden-before/hidden-after markers so long transcript truncation
  is visible rather than silent.
- Updated `App.tsx` to render the transcript through
  `VirtualMessageList`, using terminal height to size the message
  window and passing navigator selection into the list.
- Updated `MessageNavigator` to reuse the same message windowing logic,
  so Shift-Up navigation does not render the entire transcript at once.
- Added `MessageSelector` as the free-code-aligned export surface for
  future selector work.
- Added `virtualMessageList.test.ts` for edge, tail, middle selection,
  and selected-index clamping behavior.
- Rebuilt `src/generic_agent_engineered/_tui_dist/bundle.js`.

### Verification

- `cd ui-tui && npm run type-check` — clean.
- `cd ui-tui && npm test` — 21 files / 187 tests passing.
- `SKIP_INSTALL=1 ./scripts/build_tui.sh` — type-check passed, tests
  passed, bundle rebuilt.
- `python3 -m json.tool tasks.json` — clean.

### Not Tested / Deferred

- This pass adds bounded rendering and selector visibility, but it does
  not yet implement richer message actions such as copy/export per row.
  Those remain tied to upcoming slash/local command parity work.
- No visual snapshot harness exists for Ink transcript layout yet.

## GAE-053 — 工具渲染 parity：diff、bash progress、tool-specific renderers (2026-04-26)

### Scope Completed

- Added `StructuredDiff` with unified-diff line classification for
  headers, hunks, additions, removals, and context.
- Added `FileEditToolDiff`, which detects common unified diff shapes
  and renders expanded file patch output as structured diff rows.
- Added `BashModeProgress` for running `shell` / `code_run` tools and
  `ToolUseLoader` for other running tools.
- Updated `MessageRow` tool rendering to:
  - keep the existing collapsed summary path;
  - show bash/code progress while the tool is running;
  - show a generic loader for non-bash running tools;
  - render expanded `file_patch` or unified diff output through
    `FileEditToolDiff`;
  - fall back to the existing full result body for other tools.
- Added `structuredDiff.test.ts`.
- Rebuilt `src/generic_agent_engineered/_tui_dist/bundle.js`.

### Verification

- `cd ui-tui && npm run type-check` — clean.
- `cd ui-tui && npm test` — 22 files / 190 tests passing.
- `SKIP_INSTALL=1 ./scripts/build_tui.sh` — type-check passed, tests
  passed, bundle rebuilt.
- `python3 -m json.tool tasks.json` — clean.

### Not Tested / Deferred

- Tool renderers are helper-tested and build-tested, but not visually
  snapshot-tested in Ink.
- More specialized renderers for web fetch/search and todo-style output
  remain available for later command/tool parity passes if backend
  metadata becomes richer.

## GAE-054 — Slash/local command parity core (2026-04-26)

### Scope Completed

- Added a local/free-code-style command handler module for:
  `/version`, `/stats`, `/summary`, `/export`, `/diff`, `/rename`,
  `/keybindings`, `/statusline`, `/vim`, `/theme`, `/copy`,
  `/output-style`, `/effort`, `/branch`, and `/rewind`.
- Registered those commands in `COMMAND_REGISTRY` with categories,
  argument hints, and feature-gated entries where backend support is not
  implemented yet.
- Feature-gated commands return explicit errors with
  `metadata.unavailable=true` instead of silently succeeding.
- `/stats`, `/summary`, `/export`, `/diff`, and `/rename` operate on
  existing runtime/session state without adding new persistence.
- Updated `SlashOverlay` so feature-gated commands are marked as
  `unavailable` in the picker description, while supported commands show
  their category.
- Added `docs/COMMANDS.md` covering supported and feature-gated command
  surfaces.
- Extended `tests/test_commands.py` to cover the new registry entries,
  executable local commands, and explicit gating behavior.
- Rebuilt `src/generic_agent_engineered/_tui_dist/bundle.js`.

### Verification

- `python3 -m compileall -q src tests` — clean.
- `UV_NO_CACHE=1 /opt/homebrew/bin/uv run python tests/test_commands.py`
  — 15 tests passing.
- `cd ui-tui && npm run type-check` — clean.
- `cd ui-tui && npm test` — 22 files / 190 tests passing.
- `SKIP_INSTALL=1 ./scripts/build_tui.sh` — type-check passed, tests
  passed, bundle rebuilt.
- `python3 -m json.tool tasks.json` — clean.

### Not Tested / Deferred

- `python3 -m unittest discover -s tests` was attempted and failed on
  environment/suite issues unrelated to this task: the local bridge port
  was already in use, and direct Python 3.13 unittest discovery lacked
  the `pytest` module required by pytest-style gateway tests.
- Ruff could not be executed in this sandbox: `ruff` is not on PATH and
  `python3 -m ruff` reports `No module named ruff`. The task was covered
  by compileall and focused command/TUI tests.

## GAE-055 — 权限/沙箱模式 parity (2026-04-26)

### Scope Completed

- Added `ApprovalStore.remove_always_allow()` and `ApprovalStore.clear()`
  so persistent allow rules can be managed from commands.
- Added `/permissions` command:
  - `list/show` reports the approvals file, always-allowed tools, and
    high-risk gated tools.
  - `allow <tool>` persists an always-allow rule.
  - `revoke <tool>` removes one rule.
  - `clear` clears all always-allow rules.
- Added `/sandbox-toggle [status|on|off]` command. It switches the
  current runtime between approval-required mode and yolo/bypass mode by
  replacing the runtime settings object.
- Added `PermissionRequest` and `SandboxPermissionRequest` TUI
  components. `ApprovalPrompt` now delegates to `PermissionRequest`.
- App now surfaces sandbox approval mode in the TUI.
- Updated command docs for permissions/sandbox controls.
- Added tests for approval-store rule removal/clear and command-level
  permission/sandbox behavior.
- Rebuilt `src/generic_agent_engineered/_tui_dist/bundle.js`.

### Verification

- `python3 -m compileall -q src tests` — clean.
- `UV_NO_CACHE=1 /opt/homebrew/bin/uv run python tests/test_commands.py`
  — 16 tests passing.
- `UV_NO_CACHE=1 /opt/homebrew/bin/uv run python tests/test_approvals.py`
  — 11 tests passing.
- `cd ui-tui && npm run type-check` — clean.
- `cd ui-tui && npm test` — 22 files / 190 tests passing.
- `SKIP_INSTALL=1 ./scripts/build_tui.sh` — type-check passed, tests
  passed, bundle rebuilt.
- `python3 -m json.tool tasks.json` — clean.

### Not Tested / Deferred

- `/sandbox-toggle` updates the current runtime object; it does not
  persist yolo mode into config files yet.
- The TUI sandbox mode reads startup environment state. Live updates
  after `/sandbox-toggle` need a richer runtime-status field in a later
  task.

## GAE-056 — 会话/任务/worktree parity (2026-04-26)

### Scope Completed

- Added shared state view helpers for session summaries, session resume,
  background task summaries, and git worktree status.
- Added gateway RPC methods:
  `session.list`, `session.resume`, `tasks.list`, and `worktree.status`.
- Added slash commands `/sessions`, `/tasks`, and `/worktree`.
- Added TUI panels:
  - `SessionBrowser` opened with `Ctrl-S`; it filters sessions and resumes
    the selected session through the gateway.
  - `BackgroundTasksDialog` opened with `Ctrl-B`; it mirrors gateway busy
    state and in-flight chat work.
  - `WorktreeDialog` opened with `Ctrl-J`; it shows git branch, dirty
    count, and ahead/behind counts.
- Updated help/keybinding text, command docs, and protocol docs for the new
  session/task/worktree surfaces.
- Kept `/branch` and `/rewind` explicitly feature-gated; no fake rewind or
  branch semantics were added beyond the existing store primitives.
- Rebuilt `src/generic_agent_engineered/_tui_dist/bundle.js`.

### Verification

- `python3 -m compileall -q src tests` — clean.
- `UV_NO_CACHE=1 /opt/homebrew/bin/uv run python tests/test_commands.py`
  — 17 tests passing.
- `PYTHONPATH=src python3 -c "...gateway session/task/worktree RPC smoke..."`
  — clean.
- `cd ui-tui && npm run type-check` — clean.
- `cd ui-tui && npm test` — 23 files / 194 tests passing.
- `SKIP_INSTALL=1 ./scripts/build_tui.sh` — type-check passed, tests
  passed, bundle rebuilt.

### Not Tested / Deferred

- `python -m pytest tests/test_gateway_server.py` could not run because
  this environment's venv does not have `pytest` installed. The new RPCs
  were covered with a focused stdio gateway smoke test instead.
- Session persistence still depends on the existing SQLite store. Active
  in-memory sessions are shown as `persisted=false` until a later backend
  task writes every turn into the store.

## GAE-057 — MCP / Plugin / Agents / Hooks UI parity (2026-04-26)

### Scope Completed

- Added read-only extension discovery helpers for MCP servers, plugins,
  custom agents, and hooks.
- Added slash commands `/mcp`, `/plugin`, `/agents`, and `/hooks`.
  `list/show/status` are supported; write/edit/install subcommands return
  explicit unsupported metadata.
- Added gateway RPC methods:
  `mcp.list`, `plugins.list`, `agents.list`, and `hooks.list`.
- Added TUI dialog components:
  `McpDialog`, `PluginDialog`, `AgentsDialog`, and `HooksDialog`, sharing a
  compact `ExtensionList` renderer.
- Updated command docs and protocol docs for extension panels.
- Added command, gateway-client, and gateway smoke coverage.
- Rebuilt `src/generic_agent_engineered/_tui_dist/bundle.js`.

### Verification

- `python3 -m compileall -q src tests` — clean.
- `UV_NO_CACHE=1 /opt/homebrew/bin/uv run python tests/test_commands.py`
  — 18 tests passing.
- `PYTHONPATH=src python3 -c "...extension RPC smoke..."` — clean.
- `cd ui-tui && npm run type-check` — clean.
- `cd ui-tui && npm test` — 23 files / 195 tests passing.
- `SKIP_INSTALL=1 ./scripts/build_tui.sh` — type-check passed, tests
  passed, bundle rebuilt.

### Not Tested / Deferred

- Write flows are intentionally not implemented: plugin install/remove,
  agent editing, hook editing, and MCP mutation all remain gated.
- `pytest` is still unavailable in the active venv, so pytest-style gateway
  tests were not run directly; a focused stdio RPC smoke covered the new
  methods.

## GAE-058 — 外部集成 parity：IDE/desktop/chrome/voice/remote/mobile (2026-04-26)

### Scope Completed

- Added read-only integration status helpers for IDE, desktop, Chrome bridge,
  voice, remote session, mobile handoff, and teleport.
- Added slash commands `/integrations`, `/ide`, `/desktop`, `/chrome`,
  `/voice`, `/remote`, `/mobile`, and `/teleport`.
- Unsupported action subcommands such as `/voice on` now fail closed with
  `metadata.unavailable=true` and the integration status payload.
- Chrome bridge status now reports bundled extension presence, legacy bridge
  discovery, and whether the local bridge HTTP port is listening.
- Added gateway RPC methods `integrations.list` and `integrations.status`.
- Added `IntegrationStatusDialog` and TypeScript schema/client coverage for
  the new protocol methods.
- Added `docs/INTEGRATIONS.md` and updated command/protocol docs.
- Rebuilt `src/generic_agent_engineered/_tui_dist/bundle.js`.

### Verification

- `python3 -m compileall -q src tests` — clean.
- `UV_NO_CACHE=1 /opt/homebrew/bin/uv run python tests/test_commands.py`
  — 19 tests passing.
- `PYTHONPATH=src python3 -c "...integration RPC smoke..."` — clean.
- `cd ui-tui && npm run type-check` — clean.
- `cd ui-tui && npm test` — 23 files / 196 tests passing.
- `SKIP_INSTALL=1 ./scripts/build_tui.sh` — type-check passed, tests
  passed, bundle rebuilt.

### Not Tested / Deferred

- IDE, desktop, voice, remote, mobile, and teleport remain status-only until
  real integration backends exist.
- `python3 -m unittest discover -s tests` still fails on known environment
  gaps: local bridge port `18766` is already in use, and pytest-style gateway
  tests cannot import `pytest` from the active venv.
- `pytest` is still unavailable in the active venv, so pytest-style gateway
  tests were not run directly; a focused stdio RPC smoke covered the new
  integration methods.

## GAE-059 — Onboarding / Status notices / Rate-limit UX parity (2026-04-26)

### Scope Completed

- Added `Welcome` as a dedicated component that surfaces runtime provider,
  model, session id, gateway version, cwd, and recent M11 release notes.
- Added `StatusNotices` with runtime-derived onboarding, browser-bridge,
  Codex-auth, and token-budget warnings. Notices are dismissible with
  `Ctrl-N`.
- Added `RateLimitOptions` with recovery guidance for compaction, fresh
  sessions, model/provider switching, token-budget state, and Codex auth
  refresh.
- Added `/rate-limit-options` to the command registry and Python command
  handlers so the command is discoverable outside the TUI shortcut path.
- Wired `/rate-limit-options` in the TUI to open the local dialog without
  spending a backend command turn.
- Updated `CHANGELOG.md` and command docs with the M11 onboarding/status
  surfaces.
- Rebuilt `src/generic_agent_engineered/_tui_dist/bundle.js`.

### Verification

- `python3 -m compileall -q src tests` — clean.
- `UV_NO_CACHE=1 /opt/homebrew/bin/uv run python tests/test_commands.py`
  — 19 tests passing.
- `cd ui-tui && npm run type-check` — clean.
- `cd ui-tui && npm test` — 25 files / 201 tests passing.
- `SKIP_INSTALL=1 ./scripts/build_tui.sh` — type-check passed, tests
  passed, bundle rebuilt.
- `python3 -m json.tool tasks.json` — clean.

### Not Tested / Deferred

- Real provider rate-limit headers are not available through the current
  gateway protocol. This task surfaces local recovery options and token-budget
  pressure; provider-specific quota telemetry remains a future backend
  extension.

## GAE-060 — M11 parity QA、文档、最终收尾 (2026-04-26)

### Scope Completed

- Marked M11 and GAE-060 complete in `tasks.json`; all GAE-047 through
  GAE-060 tasks are now `done`.
- Updated `docs/TUI.md` so it reflects the current TS/Ink component surface,
  current RPC methods, current test counts, and the known Python discovery
  environment gaps.
- Added a final free-code parity map from each scanned TUI area to the
  migrated `ga_engineered` files and command/RPC surfaces.
- Updated `CHANGELOG.md` with the final M11 documentation/QA note.
- Rebuilt `src/generic_agent_engineered/_tui_dist/bundle.js`.

### Final M11 Parity Map

- Prompt input: queue/stash/footer, quick open, global search, file mentions,
  model/theme/thinking controls, and history search are migrated.
- Message surface: virtual transcript, row rendering, message selection,
  transcript/global search, and folding support are migrated.
- Tool rendering: structured diffs, file-edit display, bash progress, tool
  loading, and summaries are migrated.
- Commands/settings: core local slash commands are implemented; unsupported
  backend flows are explicitly feature-gated.
- Permissions/sandbox: approvals, persistent rules, sandbox mode display, and
  permission prompts are migrated.
- Session/task/worktree: sessions, resume, task state, and worktree state are
  visible through slash commands and TUI panels.
- MCP/plugin/agent/hooks: read-only discovery is migrated; write flows are
  gated.
- External integrations: IDE/desktop/Chrome/voice/remote/mobile/teleport
  status surfaces are migrated; unavailable actions fail closed.
- Onboarding/status/rate-limit: welcome, notices, release note surface, token
  budget warnings, and recovery options are migrated.

### Verification

- `python3 -m json.tool tasks.json` — clean.
- `python3 -m compileall -q src tests` — clean.
- `UV_NO_CACHE=1 /opt/homebrew/bin/uv run python tests/test_commands.py`
  — 19 tests passing.
- `cd ui-tui && npm run type-check` — clean.
- `cd ui-tui && npm test` — 25 files / 201 tests passing.
- `SKIP_INSTALL=1 ./scripts/build_tui.sh` — type-check passed, tests
  passed, bundle rebuilt.

### Not Tested / Deferred

- `python3 -m unittest discover -s tests` remains blocked in this local
  environment by the occupied browser bridge port `18766` and missing
  `pytest` dependency for pytest-style gateway tests.
- Provider-specific quota/rate-limit telemetry is deferred until the gateway
  protocol exposes concrete provider headers or quota status.

## GAE-061 — Free-code TUI 反馈修正：Bash 折叠、Crunched、slash/hooks audit (2026-04-26)

### Scope Completed

- Re-scanned free-code's Bash result rendering, command registry, and hooks
  surfaces against the current `ga_engineered` TUI.
- Changed shell/code-run rows to render as `Bash(...)` / `Python(...)` with
  free-code-style collapsed preview lines and `… +N lines (ctrl+o to expand)`.
- Added finalized assistant timing so completed assistant replies render
  `✻ Crunched for ...` after streaming ends.
- Registered the remaining visible free-code slash command names that were
  missing from `ga_engineered`; unsupported backend flows now appear as
  explicit feature-gated commands instead of unknown commands.
- Added `/bridge` output documenting `uv run gae bridge` and the gateway's
  best-effort bridge auto-spawn behavior.
- Updated `/hooks list` to disclose that hooks are read-only discovery only;
  free-code's hooks editor and execution lifecycle are not wired into
  GenericAgent.
- Updated `docs/COMMANDS.md`, `docs/TUI.md`, and `tasks.json`.

### Slash Command Audit Result

- Implemented/active: core session, config, tool, memory, skills, extension
  listing, integration status, permissions, sandbox, and bridge status
  commands.
- Explicitly feature-gated: free-code product/backend flows that do not have
  a GenericAgent runtime backend yet, including add-dir, context/cost/files,
  install app workflows, advisor/plan/review/security-review/ultrareview
  prompt workflows, insights, release notes, privacy settings, remote setup/env,
  share/tag/stickers, terminal setup, thinkback, and upgrade.
- Hooks: not complete parity. Discovery exists; edit/config/execute lifecycle
  remains gated.

### Verification

- `python3 -m unittest tests.test_commands` — 19 tests passing.
- `cd ui-tui && npm run type-check` — clean.
- `cd ui-tui && npm test` — 25 files / 203 tests passing.
- `python3 -m json.tool tasks.json` — clean.
- `python3 -m compileall -q src tests` — clean.
- `SKIP_INSTALL=1 ./scripts/build_tui.sh` — type-check passed, tests
  passed, bundle rebuilt.

### Not Tested / Deferred

- Full free-code hooks execution was not implemented because GenericAgent has
  no matching hook runtime boundary yet; the TUI now reports that gap
  explicitly.
- Full Python discovery was not rerun for this focused correction; prior M11
  environment blockers still apply.

## GAE-062 — Free-code transcript mode keybindings：ctrl+o / ctrl+e (2026-04-26)

### Scope Completed

- Replaced the previous `ctrl+o` behavior, which only expanded the latest
  collapsed tool row, with a global free-code-style detailed transcript mode.
- Added `ctrl+e` to toggle show-all transcript rendering. This disables the
  normal tail window so older transcript rows are visible in detailed mode.
- Threaded transcript mode through `VirtualMessageList` and `MessageRow` so
  collapsed tool results expand at render time without mutating transcript
  state.
- Added a detailed transcript footer in the status bar:
  `Showing detailed transcript · ctrl+o to toggle · ctrl+e to show all`.
- Kept message navigator Space as the per-tool expansion path.
- Updated `docs/TUI.md` and `tasks.json`.

### Verification

- `python3 -m unittest tests.test_commands` — 19 tests passing.
- `cd ui-tui && npm run type-check` — clean.
- `cd ui-tui && npm test` — 25 files / 204 tests passing.
- `python3 -m json.tool tasks.json` — clean.
- `python3 -m compileall -q src tests` — clean.
- `SKIP_INSTALL=1 ./scripts/build_tui.sh` — type-check passed, tests
  passed, bundle rebuilt.

### Not Tested / Deferred

- Full interactive keypress verification inside a live terminal was not run in
  this headless session; behavior is covered at the state/render boundary and
  the bundle is rebuilt in the normal TUI build gate.

## GAE-063 — OpenAI Responses duplicate tool-call guard (2026-04-26)

### Scope Completed

- Investigated duplicated `web_open(query=...)` transcript rows and traced the
  likely execution path to OpenAI Responses streaming normalization.
- Changed `response.output_item.done` handling to use the same duplicate guard
  as `response.completed` merging before emitting a `tool_call` event.
- Expanded the duplicate guard from provider id only to a semantic key of
  tool name plus normalized arguments, so identical calls with different
  provider ids execute once in the same model response.
- Added a regression test that streams two identical tool events with different
  ids, then repeats the same call in `response.completed`, and verifies only
  one tool event and one final tool call remain.

### Verification

- `python3 -m unittest tests.test_provider_clients` — provider client tests
  passing.
- `python3 -m json.tool tasks.json` — clean.
- `python3 -m compileall -q src tests` — clean.

### Not Tested / Deferred

- Live OpenAI Responses traffic was not replayed in this local session; the
  regression uses fake provider events matching the duplicated stream shape.
- The later duplicate `web_scan` in the pasted transcript may still be a model
  retry after an unhelpful scan result rather than a provider duplicate.

## GAE-064 — Remove stale M11 welcome release note (2026-04-26)

### Scope Completed

- Removed the TUI welcome release note:
  `M11 parity migration adds session panels, extension status, and integration gates.`
- Rebuilt the bundled TUI artifact so the packaged `gae` interface no longer
  contains the removed sentence.
- Kept the rest of the welcome panel unchanged.

### Verification

- `cd ui-tui && npm run type-check` — clean.
- `SKIP_INSTALL=1 ./scripts/build_tui.sh` — type-check passed, 25 test files /
  204 tests passed, bundle rebuilt.
- `rg "M11 parity migration adds session panels" ui-tui/src src/generic_agent_engineered/_tui_dist`
  — no matches in source or bundled TUI output after rebuild.

### Not Tested / Deferred

- No live terminal screenshot was captured for this text-only removal.

## GAE-065 — Blue GenericAgent welcome banner (2026-04-26)

### Scope Completed

- Reworked the TUI welcome panel to render the existing GenericAgent block
  ASCII logo instead of a single plain title line.
- Changed the banner palette to a cool blue slate range inspired by
  hermes-agent's slate skin.
- Replaced the old Hermes-style emblem art with a GenericAgent-specific
  runtime diagram showing core runtime, tool graph, memory layers, plan/act,
  check/learn, and local-first execution.
- Wired responsive rendering into `Welcome`: wide terminals show emblem plus
  logo, while narrower terminals keep the compact `GA` logo.
- Rebuilt the bundled TUI artifact.

### Verification

- `cd ui-tui && npm run type-check` — clean.
- `cd ui-tui && npm test -- src/__tests__/banner.test.ts` — 10 tests passed.
- `SKIP_INSTALL=1 ./scripts/build_tui.sh` — type-check passed, 25 test files /
  204 tests passed, bundle rebuilt.

### Not Tested / Deferred

- No live terminal screenshot was captured in this headless session.

## GAE-066 — Normalize public README and operations docs (2026-04-26)

### Scope Completed

- Rewrote `README.md` as the public entry point for current GenericAgent
  Engineered features, quick start, global installation, configuration, browser
  bridge, documentation map, and verification.
- Added `docs/INSTALLATION.md` with source checkout, global `uv tool install`,
  editable development, TUI bundle, gateway Python, and bridge troubleshooting
  guidance.
- Added `docs/CONFIGURATION.md` with `.generic-agent/settings.json`,
  `$GENERIC_AGENT_HOME/settings.json`, precedence rules, supported keys,
  environment variables, provider credential examples, OAuth commands, and
  gitignore guidance.
- Added `docs/DEPLOYMENT.md` covering local tool deployment, package builds,
  runtime directories, browser bridge operation, CI smoke checks, and release
  gates.
- Added `docs/DEVELOPMENT.md` covering repository boundaries, code layout,
  workflow, provider/tool/command extension, TUI rules, and git hygiene.

### Verification

- `python3 -m json.tool tasks.json` — clean.
- `python3 -m compileall -q src tests` — clean.
- `cd ui-tui && npm run type-check` — clean.

### Not Tested / Deferred

- No hosted documentation preview was generated locally.
