# Changelog

## [Unreleased]

### M11 — Free-code TUI full parity migration

Added parity surfaces for the TypeScript TUI migration:

- Session/task/worktree panels, MCP/plugin/agent/hook discovery dialogs, and
  external integration status commands now mirror free-code's visible command
  surface while unsupported write/connect flows fail closed.
- Welcome and status notices now surface runtime state, recent release notes,
  bridge readiness, token-budget pressure, and rate-limit recovery options.
- Final M11 docs now map each scanned free-code TUI area to the migrated
  `ga_engineered` implementation and record remaining unsupported flows.

### M10 — Free-code-style interactivity

Added free-code-equivalent input and transcript polish:

- **Multiline TextInput** with cursor movement (arrows, Ctrl-Left/Right
  word jump, Ctrl-A/E line start/end), editing (Backspace, Ctrl-W kill
  word, Ctrl-U/K kill line), Shift-Enter newline, and bracketed-paste
  detection.
- **History recall** with mode-filtered ↑/↓ + draft preservation,
  persistent JSON-lines under `$GENERIC_AGENT_HOME/history.jsonl`, and
  Ctrl-R fuzzy search overlay.
- **Mode prefixes**: `!<cmd>` runs shell via the new `tools.run` RPC,
  `@<query>` opens a fuzzy file picker via the new `files.search` RPC,
  glyph + colour change per mode.
- **Vim mode** (opt-in via `GA_VIM_MODE=1`) covering INSERT / NORMAL /
  VISUAL / OPERATOR-PENDING with hjkl, w/b, 0/$/^, gg/G, x, dd/cc/yy,
  d/c/y + motion, u, and a status bar pill showing the current vim
  mode.
- **Streaming polish**: 60Hz frame batching for `content_delta` so a
  fast LLM no longer starves the input loop, plus a "thinking" spinner
  before the first token lands.
- **Markdown rendering** for finished assistant messages (bold, italic,
  inline code, three heading levels, fenced code blocks with a
  language label, links).
- **Tool result fold/unfold**: tool outputs over 200 chars start
  collapsed; Shift-↑ opens a read-only message navigator with
  Space-to-expand and Esc-to-exit.
- **Tool approval prompts**: shell / code_run / file_write / file_patch
  now require y/n/a confirmation. Decisions persist to
  `$GENERIC_AGENT_HOME/approvals.json`. `GA_YOLO=1` skips the gate.
- **Shortcuts**: Ctrl-G interrupt, Ctrl-L clear-transcript, Ctrl-D
  empty-exit, Ctrl-C cancel-then-exit, `?` / `/shortcuts` help overlay,
  toast notifications.
- New gateway methods: `tools.run`, `files.search`, `chat.approve`. New
  event kind: `approval_request`.

### M9 — TypeScript TUI as the only frontend (recap)

See the M9 section below for the original cutover.

### Added

- **TypeScript / Ink frontend** (`ui-tui/`) is now the only TUI. It
  spawns the Python runtime via a stdio JSON-RPC gateway and renders
  the welcome page, transcript, tool tree, slash overlay, and status
  bar in React.
- `generic_agent_engineered.gateway` package: line-delimited JSON
  protocol server (`protocol.py`, `server.py`) wired to
  `ChatTurnService`, with pre-claimed busy slot, cancellation
  semantics, and `RuntimeEvent` streaming through an `event_sink`
  hook on `AgentLoop`.
- New console scripts `GenericAgent` and `ga` (alongside `gae`); all
  three drop into the TS TUI when invoked without a non-interactive
  subcommand.
- `cli/launcher.py` locates `_tui_dist/bundle.js` and `os.execvp`s
  node so signals belong to the TS frontend directly. Honours
  `GA_TUI_BUNDLE`, `GA_NODE`, `GA_LAUNCHER_NO_EXEC`. The gateway
  itself separately reads `GA_GATEWAY_DEBUG` to include Python
  tracebacks in `-32099` error frames.
- `scripts/build_tui.sh` runs the TS toolchain (`npm install`,
  `type-check`, vitest, esbuild) and stages `bundle.js` for the wheel.
- `tests/test_tui_e2e.py` round-trips a real `runtime.status` request
  through the gateway (skips when node is missing).

### Changed

- `AgentLoop` and `ChatTurnService` accept optional `event_sink` and
  `stop_signal` keyword args so the gateway can stream events in real
  time. Default behaviour is unchanged.

### Removed

- `src/generic_agent_engineered/ui/` (the entire Python prompt-toolkit
  TUI: `tui.py`, `banner.py`, `console.py`, `statusbar.py`,
  `completion.py`, `spinner.py`, `widgets/`).
- `tests/test_ui.py`.
- `rich` and `prompt-toolkit` dependencies from `pyproject.toml`.
- `--tui`, `--plain`, and `--no-animations` CLI flags.

## 0.1.0 - 2026-04-25

Initial engineered Python track for GenericAgent.

### Added

- Independent `uv` Python project using `src/` layout and `gae` console script.
- Layered JSON settings resolution for CLI overrides, env, project
  `.generic-agent/settings.json`, global `$GENERIC_AGENT_HOME/settings.json`,
  and defaults.
- Provider registry, provider specs, and concrete clients for OpenAI Responses,
  OpenAI-compatible Chat Completions, Anthropic Messages, and Codex OAuth.
- Auth store with atomic `auth.json` writes, API-key records, OpenAI Codex OAuth
  PKCE helpers, loopback callback handling, refresh seam, headed login, and
  headless login command support.
- Provider-neutral runtime message models, `AgentLoop`, streaming events,
  stop/max-turn handling, token-budget estimation, and history compaction.
- Tool runtime with schemas, permissions metadata, enable/disable registry,
  workspace-constrained file tools, shell/code execution tools, browser bridge
  tools preserving `web_scan` / `web_execute_js`, and `web_open` for URL/search
  browser launch.
- Central slash command registry and handlers for session, configuration,
  auth, tools, memory, skills, doctor, usage, and command discovery.
- Rich/plain terminal presentation layer with statusbar, startup banner,
  spinner fallback, prompt-toolkit slash completion, and Python TUI entry points
  through `gae --tui`, `gae tui`, and empty `gae chat`.
- Provider-backed chat turn service that connects non-slash TUI input to the
  current provider through `AgentLoop` and reports missing auth explicitly.
- Default interactive tool registry injected into TUI chat turns, with tool-call
  transcript lines for `tool>` and `tool<` events.
- SQLite `SessionStore` with WAL initialization, sessions/messages tables,
  FTS5 message search, and parent/child session branches.
- Layered memory service for L1/L2/L3/L4 indexing, legacy `GenericAgent/memory`
  migration reads, reviewed writes, SOP draft crystallization, and duplicate
  skill detection.
- Legacy migration surface with task/reflect file I/O shims, tool migration
  mapping, migration guide, and compatibility fixtures for no-tool, `file_read`,
  and `code_run` paths.
- Release checklist, task report, and validation tests for release docs.

### Fixed

- Browser `/link` bridge requests now bypass inherited proxy environment
  variables, so `web_scan`/`web_execute_js` do not accidentally send local
  `127.0.0.1:18766` traffic to `http_proxy`/`all_proxy`.
- TUI tool transcripts now print concise error details after `tool< ... error`.
- Shell risk classification no longer treats `curl ... || echo ...` fallback
  commands as download pipes, while `curl ... | sh` remains blocked.

### Verification

- `python3 -m unittest discover -s tests`
- `UV_CACHE_DIR=/tmp/ga-engineered-uv-cache uv run --no-sync pytest`
- `UV_CACHE_DIR=/tmp/ga-engineered-uv-cache uv run --no-sync ruff check .`
- `UV_CACHE_DIR=/tmp/ga-engineered-uv-cache uv run --no-sync mypy src`
- CLI smoke tests for `--version`, `doctor`, `status`, `chat /status`,
  TUI routing, and `task --input /status`.
- Targeted tool checks for browser bridge proxy bypass, shell fallback
  classification, and TUI tool error rendering.

### Known Gaps

- Live provider calls and live OAuth callback exchange remain manual integration
  validation tasks because unit tests use injected transports.
- Live provider-backed task execution is staged after this release track; the
  TUI path now calls the provider, while task/reflect compatibility shims still
  preserve file I/O contracts.
- Browser integration uses fake bridges in tests; live TMWebDriver/CDP sessions
  need environment-specific validation.
- `uv run --no-sync` is used in the current restricted sandbox to avoid network
  package resolution.
