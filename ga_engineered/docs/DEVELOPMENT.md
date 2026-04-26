# Development Guide

This guide describes how to work on `ga_engineered` without changing the legacy
GenericAgent runtime.

## Repository Boundaries

- `ga_engineered/` is the engineered implementation and owns new code.
- `GenericAgent/` is the legacy runtime and migration reference.
- `free-code/` and `hermes-agent/` are reference repositories for TUI and CLI
  behavior.
- Do not modify the legacy GenericAgent core unless a task explicitly calls for
  a compatibility migration.

## Development Setup

```bash
cd ga_engineered
uv sync --extra dev
cd ui-tui && npm install
cd ..
SKIP_INSTALL=1 ./scripts/build_tui.sh
```

Run the TUI from source:

```bash
export GA_GATEWAY_PYTHON="$PWD/.venv/bin/python"
uv run GenericAgent
```

## Code Layout

```text
src/generic_agent_engineered/
├── auth/                 # API key store, OAuth PKCE, callback server
├── browser/              # TMWebDriver/CDP bridge abstractions
├── cli/                  # launcher, doctor, status, bridge command
├── commands/             # slash command registry and handlers
├── compat/               # legacy GenericAgent migration shims
├── gateway/              # stdio JSON-RPC server for the TS TUI
├── memory/               # layered memory and skill crystallization helpers
├── providers/            # LLM provider clients and registry
├── runtime/              # agent loop, messages, events, compaction, approvals
├── state/                # sessions, extension/integration views
└── tools/                # file, shell, Python, browser tools

ui-tui/
├── src/App.tsx           # top-level Ink app
├── src/components/       # UI panels/dialogs/renderers
├── src/state/            # reducers and local UI state
├── src/markdown/         # parser/renderer
├── src/banner.ts         # startup logo/emblem
└── src/__tests__/        # Vitest tests
```

## Development Workflow

1. Add or update the task in `tasks.json`.
2. Make a small, scoped change.
3. Add or update focused tests.
4. Run the relevant verification commands.
5. Update `tasks/TASK_REPORT.md`.
6. Rebuild the TUI bundle when TS code changes.
7. Commit with the Lore Commit Protocol from `AGENTS.md`.

For TUI changes:

```bash
cd ui-tui
npm run type-check
npm test
cd ..
SKIP_INSTALL=1 ./scripts/build_tui.sh
```

For Python runtime changes:

```bash
python3 -m compileall -q src tests
python3 -m unittest discover -s tests
```

Use focused suites when full discovery is blocked by optional local services:

```bash
python3 -m unittest tests.test_provider_clients
python3 -m unittest tests.test_commands
python3 -m unittest tests.test_agent_loop
```

## Adding a Provider

1. Add a `ProviderSpec` in `providers/registry.py`.
2. Implement or reuse a transport adapter in `providers/`.
3. Normalize output into `StreamEvent`, `ChatResponse`, and `ToolCall`.
4. Keep live HTTP transport injectable for tests.
5. Add fake-transport tests in `tests/test_provider_clients.py`.
6. Document credentials in `docs/CONFIGURATION.md`.

## Adding a Tool

1. Implement `Tool` in `src/generic_agent_engineered/tools/`.
2. Register it in `tools/defaults.py`.
3. Keep schemas provider-neutral.
4. Enforce workspace and permission boundaries in the tool itself.
5. Add unit tests for success, failure, and boundary behavior.
6. Add rendering support in `ui-tui/src/toolSummary.ts` or a dedicated
   component if the output needs a richer view.

## Adding a Slash Command

1. Add command metadata to `commands/registry.py`.
2. Add the handler in the closest `commands/*.py` module.
3. Register the handler in `commands/__init__.py` or the router setup.
4. Add command tests in `tests/test_commands.py`.
5. Update `docs/COMMANDS.md`.
6. Add TUI handling only if the command opens a local dialog without backend
   work.

Feature-gated commands should be registered and return explicit unavailable
metadata rather than disappearing from the slash overlay.

## TUI Guidelines

- Keep the Python runtime as the source of truth for provider/tool/session
  behavior.
- Use the gateway protocol for backend state; do not duplicate runtime logic in
  TypeScript.
- Keep compact responsive layouts for terminals around 80 columns.
- Run `npm test` and `SKIP_INSTALL=1 ./scripts/build_tui.sh` after UI changes.
- Rebuild `_tui_dist/bundle.js` before committing TS changes.

## Git Hygiene

There may be unrelated dirty files in this workspace. Do not revert or stage
them unless the task explicitly asks for it. Before committing:

```bash
git status --short
git diff --check
git diff --cached --stat
```

Commit messages should explain why the change exists and include useful
trailers such as `Constraint`, `Rejected`, `Confidence`, `Scope-risk`,
`Tested`, and `Not-tested`.
