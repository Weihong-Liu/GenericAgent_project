# GenericAgent Engineered

`ga_engineered` is the engineered Python runtime and TypeScript/Ink terminal UI
for GenericAgent. It preserves the original GenericAgent idea — a small agent
loop, atomic tools, layered memory, and self-improving skills — while adding
provider abstraction, OAuth/auth storage, a tested tool runtime, sessions,
slash commands, and a free-code-style TUI.

This package is intentionally separate from the legacy `GenericAgent/` folder.
The legacy repo remains a migration/reference source; new runtime work happens
here.

## What Is Included

- Python agent runtime with provider-neutral messages, tool calls, tool
  results, lifecycle events, retry/stop/max-turn handling, and history
  compaction.
- Provider clients for OpenAI Responses, OpenAI-compatible Chat Completions,
  Anthropic Messages, OpenAI Codex OAuth, Kimi/Moonshot, DashScope, MiniMax,
  and custom OpenAI-compatible endpoints.
- Auth and configuration stores under `~/.generic-agent` by default, with
  free-code-style `GENERIC_AGENT_CONFIG_DIR` / `GA_CONFIG_DIR` overrides and
  project-level `.generic-agent/settings.json` support.
- Default tools: file read/write/patch, shell, Python code execution,
  `web_open`, `web_scan`, and `web_execute_js`.
- Legacy browser bridge support through `uv run gae bridge` plus the bundled
  Chrome extension.
- SQLite session store with WAL and FTS5 search support.
- Layered memory service that can import legacy GenericAgent memory and prepare
  reviewed SOP/skill drafts.
- Slash command registry and handlers for status, sessions, config, auth,
  tools, memory, extensions, integrations, permissions, and TUI controls.
- TypeScript/Ink TUI with a blue GenericAgent startup banner, streaming
  transcript, markdown rendering, tool folding, command overlay, session panels,
  integration status dialogs, and free-code-style `ctrl+o` / `ctrl+e`
  transcript modes.
- Task plan and implementation history in `tasks.json` and `tasks/TASK_REPORT.md`.

## Quick Start

```bash
cd ga_engineered
uv sync --extra dev
SKIP_INSTALL=1 ./scripts/build_tui.sh
uv run GenericAgent
```

Equivalent entry points:

```bash
uv run GenericAgent
uv run ga
uv run gae
uv run gae tui
```

Useful non-interactive commands:

```bash
uv run gae --version
uv run gae doctor
uv run gae status
uv run gae commands
uv run gae chat /status
uv run gae task .generic-agent/tasks/demo --input "/status"
```

## Install Globally

From this directory:

```bash
uv tool install .
GenericAgent
```

After updating the checkout, rebuild the TUI bundle and reinstall:

```bash
SKIP_INSTALL=1 ./scripts/build_tui.sh
uv tool install --force .
```

See [Installation](docs/INSTALLATION.md) for editable installs, global tool
installs, shell PATH notes, and Node/TUI build requirements.

## Configuration

Project configuration belongs in `.generic-agent/settings.json`; global
configuration belongs in `$GENERIC_AGENT_CONFIG_DIR/settings.json` (default
`~/.generic-agent/settings.json`). `GENERIC_AGENT_HOME` remains a legacy alias,
and `CLAUDE_CONFIG_DIR` is accepted as a migration fallback for free-code-style
shell profiles.

```bash
export GENERIC_AGENT_CONFIG_DIR="$HOME/.generic-agent"
# or, for a separate profile:
export GENERIC_AGENT_CONFIG_DIR=".generic-agent-glm"
```

Minimal project config:

```json
{
  "provider": "openai",
  "model": "gpt-5.4",
  "language": "zh",
  "yolo": false,
  "env": {
    "OPENAI_API_KEY": "sk-...",
    "HTTPS_PROXY": "http://127.0.0.1:7890"
  }
}
```

Resolution order is:

1. CLI overrides
2. environment variables
3. nearest project config
4. global user config
5. defaults

See [Configuration](docs/CONFIGURATION.md) for the full schema, environment
variables, provider examples, proxy setup, browser bridge settings, and
the full free-code-inspired home layout (`agents`, `projects`, `sessions`,
`skills`, `tasks`, `transcripts`, `telemetry`, caches, backups, and more).

## Browser Bridge

`web_open` opens URLs/searches directly. `web_scan` and `web_execute_js` read
live browser state through the legacy TMWebDriver bridge:

```bash
uv sync --extra bridge
uv run gae bridge
```

Load the Chrome extension from `assets/tmwd_cdp_bridge/` through
`chrome://extensions` -> "Load unpacked". The TUI gateway tries to auto-spawn
the bridge, but the explicit foreground command is still the most reliable
debug path. `/bridge` prints the current bridge guidance inside the TUI.

## Documentation

- [Installation](docs/INSTALLATION.md)
- [Configuration](docs/CONFIGURATION.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Development](docs/DEVELOPMENT.md)
- [TUI architecture](docs/TUI.md)
- [Slash commands](docs/COMMANDS.md)
- [Keyboard shortcuts](docs/SHORTCUTS.md)
- [Integrations](docs/INTEGRATIONS.md)
- [Migration from legacy GenericAgent](docs/MIGRATION.md)
- [Release checklist](docs/RELEASE_CHECKLIST.md)

## Verification

Common local gate:

```bash
python3 -m json.tool tasks.json >/dev/null
python3 -m compileall -q src tests
python3 -m unittest discover -s tests
cd ui-tui && npm run type-check && npm test
SKIP_INSTALL=1 ./scripts/build_tui.sh
```

Some full-suite checks depend on local Node, pytest, browser-bridge port
availability, and installed dev extras. Focused task reports in
`tasks/TASK_REPORT.md` record any environment-specific gaps.

## Repository Boundary

`ga_engineered` is the primary implementation in `GenericAgent_project`. For
the current GitHub upload it is vendored directly as a normal directory in the
parent repository. The legacy/reference repositories (`GenericAgent`,
`free-code`, and `hermes-agent`) are kept as separate child repositories.
