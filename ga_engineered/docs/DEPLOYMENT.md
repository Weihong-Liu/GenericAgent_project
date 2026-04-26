# Deployment

GenericAgent can be deployed as a developer CLI, a globally installed local
tool, or a packaged artifact with the TypeScript TUI bundle embedded.

## Deployment Modes

| Mode | Use when | Command |
|---|---|---|
| Source checkout | Active development | `uv run GenericAgent` |
| Global local tool | Personal daily CLI | `uv tool install .` |
| Wheel/package artifact | Distribution or CI artifact | `python -m build` after bundling TUI |
| Headless command runner | CI / scripted tasks | `gae chat /status`, `gae task <iodir>` |

## Local Tool Deployment

```bash
cd ga_engineered
uv sync --extra dev
SKIP_INSTALL=1 ./scripts/build_tui.sh
uv tool install --force .
```

Smoke test:

```bash
GenericAgent --version
gae doctor
gae status
gae chat /status
```

## Package Build

The wheel must include `src/generic_agent_engineered/_tui_dist/bundle.js`.

```bash
cd ga_engineered
uv sync --extra dev
SKIP_INSTALL=1 ./scripts/build_tui.sh
uv build
```

Then install from `dist/`:

```bash
uv tool install --force dist/generic_agent_engineered-*.whl
```

## Runtime Directories

Set a stable home directory on deployed machines:

```bash
export GENERIC_AGENT_HOME=/opt/generic-agent/state
mkdir -p "$GENERIC_AGENT_HOME"
```

Recommended layout:

```text
/opt/generic-agent/
├── app/                 # source checkout or installed package reference
├── state/               # GENERIC_AGENT_HOME
│   ├── settings.json
│   ├── auth.json
│   └── state/sessions.sqlite
└── logs/                # shell/service logs if you wrap the CLI
```

Keep `auth.json` private:

```bash
chmod 700 "$GENERIC_AGENT_HOME"
chmod 600 "$GENERIC_AGENT_HOME/auth.json"
```

## Browser Bridge Deployment

For machines that need live browser tools:

```bash
uv sync --extra bridge
uv run gae bridge --port 18765
```

Operational notes:

- WebSocket listens on the selected port, default `18765`.
- HTTP `/link` listens on `PORT+1`, default `18766`.
- The Chrome extension must be loaded from `assets/tmwd_cdp_bridge/`.
- If another bridge already owns the port, the gateway will report the bridge
  as unavailable rather than killing the existing process.

For long-running local use, run the bridge in your terminal multiplexer or
service manager and start the TUI separately.

## CI Smoke Test

Example CI sequence:

```bash
uv sync --extra dev
SKIP_INSTALL=1 ./scripts/build_tui.sh
python3 -m json.tool tasks.json >/dev/null
python3 -m compileall -q src tests
python3 -m unittest tests.test_commands
cd ui-tui && npm run type-check && npm test
uv run gae --version
uv run gae chat /status
```

Use focused Python tests if the runner cannot bind browser bridge ports or does
not have every optional dependency installed.

## Release Checklist

Before publishing or pushing a deployment branch:

1. Build the TUI bundle.
2. Run Python compile/tests.
3. Run TypeScript type-check/tests.
4. Verify `tasks.json` is valid JSON.
5. Verify `gae doctor`, `gae status`, and `gae chat /status`.
6. Confirm no secrets are present in `.generic-agent/`, shell history, or docs.
7. Update `CHANGELOG.md` and `tasks/TASK_REPORT.md` for user-visible changes.

See [Release Checklist](RELEASE_CHECKLIST.md) for the standing project gates.
