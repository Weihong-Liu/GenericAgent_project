# Installation

This guide covers local development installs, global installs, and the
TypeScript TUI build that must be bundled before packaging.

## Requirements

- Python 3.11 or newer
- `uv`
- Node.js 20 or newer for building/running the TypeScript/Ink TUI from source
- Git
- Optional browser bridge extras for `web_scan` and `web_execute_js`

Check the local toolchain:

```bash
python3 --version
uv --version
node --version
npm --version
git --version
```

## Source Checkout Install

```bash
cd ga_engineered
uv sync --extra dev
SKIP_INSTALL=1 ./scripts/build_tui.sh
uv run gae doctor
uv run GenericAgent
```

`uv sync --extra dev` creates `.venv/` and installs Python test/dev tools.
`scripts/build_tui.sh` installs Node packages when needed, runs type-checks and
Vitest, builds `ui-tui/dist/bundle.js`, and copies the bundle to
`src/generic_agent_engineered/_tui_dist/bundle.js` so Python package installs
can launch the TUI.

## Global Install

Install from the local checkout:

```bash
cd ga_engineered
SKIP_INSTALL=1 ./scripts/build_tui.sh
uv tool install .
GenericAgent
```

The package exposes three equivalent console scripts:

- `GenericAgent`
- `ga`
- `gae`

If your shell cannot find those commands, ensure the `uv` tool bin directory is
on PATH:

```bash
uv tool dir
uv tool update-shell
```

Open a new shell after `uv tool update-shell`.

Upgrade a global install after pulling new code:

```bash
cd ga_engineered
SKIP_INSTALL=1 ./scripts/build_tui.sh
uv tool install --force .
```

Uninstall:

```bash
uv tool uninstall generic-agent-engineered
```

## Editable Development

Use `uv run` from the checkout during active development:

```bash
uv run gae status
uv run gae chat /status
uv run GenericAgent
```

If you want the TUI frontend to run directly from `ui-tui/dist/bundle.js`
without copying into `_tui_dist`, set:

```bash
export GA_TUI_BUNDLE="$PWD/ui-tui/dist/bundle.js"
```

When the TS frontend spawns the Python gateway, it defaults to `python3`.
For pyenv/uv-specific environments, set:

```bash
export GA_GATEWAY_PYTHON="$(pwd)/.venv/bin/python"
```

## Browser Bridge Extras

Install bridge dependencies only on machines that need browser page scanning:

```bash
uv sync --extra bridge
uv run gae bridge
```

Then load the Chrome extension from:

```text
ga_engineered/assets/tmwd_cdp_bridge/
```

Open `chrome://extensions`, enable Developer Mode, choose "Load unpacked", and
select that directory.

## Common Problems

`GenericAgent: command not found`

- Use `uv run GenericAgent` from the checkout, or run `uv tool update-shell`
  after `uv tool install .`.

`Cannot find bundled TUI`

- Run `SKIP_INSTALL=1 ./scripts/build_tui.sh`.
- Confirm `src/generic_agent_engineered/_tui_dist/bundle.js` exists.

`ModuleNotFoundError` from the TUI gateway

- Set `GA_GATEWAY_PYTHON` to the Python interpreter that has this package
  installed.

`browser bridge unavailable`

- Run `uv sync --extra bridge`.
- Start `uv run gae bridge`.
- Load the Chrome extension and keep Chrome running.
- Check whether ports `18765` and `18766` are already in use.
