# TUI Architecture

GenericAgent's terminal interface is a **TypeScript / Ink frontend** that
talks to the existing **Python agent runtime** over stdio JSON-RPC. The two
halves run in separate processes; the Python launcher (`GenericAgent`,
`ga`, or `gae`) spawns the TS bundle, which in turn spawns the Python
gateway as its own child.

```
┌────────────────────┐   spawn      ┌─────────────────────────────┐
│  GenericAgent / ga │ ───────────▶ │ node dist/bundle.js (Ink)    │
│  Python launcher   │              │  • App.tsx (transcript)      │
│  cli/launcher.py   │              │  • Welcome + StatusNotices   │
└────────────────────┘              │  • SlashOverlay              │
                                    │  • Dialogs / Pickers         │
                                    │  • StatusBar                 │
                                    └──────────────┬──────────────┘
                                                   │ spawn
                                                   ▼
                                    ┌─────────────────────────────┐
                                    │ python -m gateway            │
                                    │  • protocol.py (frames)      │
                                    │  • server.py (RPC dispatch)  │
                                    │  • event_sink → AgentLoop    │
                                    └──────────────────────────────┘
```

## Wire protocol

The full spec is in [`tasks/TUI_TS_PROTOCOL.md`](../tasks/TUI_TS_PROTOCOL.md).
At a glance:

- **Transport**: line-delimited JSON over stdio.
- **Frame types**: `request`, `response`, `event`.
- **RPC methods**: `chat.send`, `chat.cancel`, `commands.list`,
  `commands.dispatch`, `tools.list`, `runtime.status`, `session.new`,
  `session.list`, `session.resume`, `tasks.list`, `worktree.status`,
  `mcp.list`, `plugins.list`, `agents.list`, `hooks.list`,
  `integrations.list`, `integrations.status`, `files.search`,
  `tools.run`, `chat.approve`, and `gateway.shutdown`.
- **Event kinds** (forwarded from `RuntimeEvent.to_dict()`): `turn_started`,
  `content_delta`, `tool_call`, `tool_result`, `message_done`,
  `turn_finished`, `loop_stopped`, `error` — plus `gateway.ready` and
  `gateway.shutdown` from the gateway itself.
- **Cancellation**: a `chat.send` cancelled mid-flight returns a normal
  response with `status: "cancelled"`.

## Project layout

```
ga_engineered/
├── src/generic_agent_engineered/
│   ├── cli/launcher.py         # locates bundle.js, exec's node
│   ├── gateway/
│   │   ├── protocol.py         # frame codecs, error codes
│   │   ├── server.py           # RPC dispatch, event sink
│   │   └── __main__.py         # python -m generic_agent_engineered.gateway
│   └── _tui_dist/bundle.js     # built TS bundle (created by build_tui.sh)
├── ui-tui/
│   ├── src/
│   │   ├── entry.tsx           # node entry — boots App
│   │   ├── App.tsx             # transcript + input + overlays
│   │   ├── gatewayClient.ts    # spawn python, stream events
│   │   ├── schemas.ts          # zod mirrors of the wire types
│   │   ├── banner.ts           # legacy banner constants retained for tests
│   │   ├── components/
│   │   │   ├── welcome.tsx
│   │   │   ├── statusNotices.tsx
│   │   │   ├── rateLimitOptions.tsx
│   │   │   ├── slashOverlay.tsx
│   │   │   ├── virtualMessageList.tsx
│   │   │   ├── sessionBrowser.tsx
│   │   │   ├── mcpDialog.tsx / pluginDialog.tsx
│   │   │   └── statusBar.tsx
│   │   ├── hooks/useSpinner.ts
│   │   ├── state/
│   │   │   ├── transcriptStore.ts
│   │   │   └── commandFilter.ts
│   │   └── __tests__/          # vitest unit tests
│   ├── package.json            # ink ^6.8, react ^19.2, zod ^4
│   └── esbuild.config.mjs      # → dist/bundle.js
└── scripts/build_tui.sh        # builds ui-tui and stages bundle.js
```

## Running

After installing the wheel (or in the source checkout with the bundle
built), any of the following enter the TUI:

```bash
GenericAgent              # only works when the venv is on PATH
ga
gae                       # bare invocation
gae tui                   # explicit subcommand
gae chat                  # empty prompt — also drops to TUI
gae chat hello            # free-form text — also drops to TUI
```

In a source checkout where `uv sync` puts the scripts under
`.venv/bin/`, prefix with `uv run`:

```bash
uv run GenericAgent
uv run gae chat /status
```

`uv tool install .` installs the entries globally on your PATH if you
prefer the unprefixed form.

These are still **non-interactive** and bypass the TUI:

```bash
gae --version
gae doctor
gae status
gae commands
gae chat /status         # one-shot slash dispatch (CI-friendly)
gae task <iodir>         # legacy file-IO task runner
gae reflect <script>     # legacy reflect runner
gae bridge               # foreground browser bridge (see below)
```

### Browser bridge for `web_scan` / `web_execute_js`

Two of the agent's tools read live browser pages via the legacy
``TMWebDriver`` bridge (HTTP `/link` on port 18766, WebSocket on 18765,
plus a Chrome extension). Without the bridge running, those tools
return ``browser bridge unavailable``.

```bash
uv sync --extra bridge       # one-time: install bottle + ws server + bs4
uv run gae bridge            # foreground; Ctrl-C to stop
```

When the TS TUI starts the Python gateway, the gateway also tries a
best-effort auto-spawn of the same bridge. If bridge extras are missing, the
legacy bridge cannot be located, the port is already owned, or the Chrome
extension is not connected yet, browser tools still report the explicit
`browser bridge unavailable` error and `/bridge` prints the foreground command.

The Chrome extension is bundled at
`ga_engineered/assets/tmwd_cdp_bridge/`. Install it once via
`chrome://extensions` → "Load unpacked" → pick that folder. The
first run of `gae bridge` auto-generates the per-install
`config.js` (gitignored), so you no longer need to start legacy
GA first. The extension auto-connects to `ws://127.0.0.1:18765`
whenever the browser is running.

`GA_LEGACY_BRIDGE_DIR` overrides where `gae bridge` looks for the
legacy `TMWebDriver.py` (defaults to the workspace sibling
`GenericAgent/`). `GA_BRIDGE_EXTENSION_DIR` overrides where the
bundled extension lives. `--port N` overrides the WS port; HTTP is
`N+1`.

### Environment hooks

| Variable | Effect |
|---|---|
| `GA_TUI_BUNDLE` | Override the bundle path. Useful in development: point at `ui-tui/dist/bundle.js` and skip the `scripts/build_tui.sh` copy step. |
| `GA_NODE` | Override the `node` binary. Defaults to whichever `node` is on `PATH`. |
| `GA_LAUNCHER_NO_EXEC` | When set, the launcher uses `subprocess.call` instead of `os.execvp`. Mainly for tests. |
| `GA_GATEWAY_DEBUG` | Include Python tracebacks in `-32099` error frames. |
| `GA_GATEWAY_PYTHON` | Override the Python binary the TS frontend spawns. **Defaults to `python3`**, NOT to the same Python that launched the launcher — set this explicitly when running under `pyenv` / `uv` so the TS frontend uses the same interpreter that has the package installed. |
| `GA_GATEWAY_MODULE` | Override the module the TS frontend invokes (default `generic_agent_engineered.gateway`). |

## Building from source

```bash
cd ga_engineered
uv sync --extra dev
scripts/build_tui.sh        # → src/generic_agent_engineered/_tui_dist/bundle.js
uv run pytest               # 178 + 1 e2e
GenericAgent                # launches the TS TUI
```

The build script runs `npm install` (skipped if `node_modules` already
exists), `npm run type-check`, `npm test` (vitest), `npm run build`
(esbuild → `ui-tui/dist/bundle.js`), then copies the bundle into
`src/generic_agent_engineered/_tui_dist/` so the wheel includes it.

## Testing

| Suite | Command | Coverage |
|---|---|---|
| Python | `python3 -m unittest discover -s tests` / focused `uv run python tests/test_commands.py` | Command, config, runtime, tool, bridge, and TUI launcher coverage. In this local environment, full discovery is currently blocked by occupied bridge port `18766` and missing `pytest`; focused task suites are used where appropriate. |
| TypeScript | `cd ui-tui && npm test` | 25 files / 203 cases covering gateway client, transcript reducer, command filter, prompt input, dialogs, status notices, rate-limit options, tool summaries, and visual helpers. |

The e2e test is gated on `node` being on `PATH` and the bundle existing
in `_tui_dist/`; it is skipped (not failed) otherwise so the suite stays
green on CI runners without Node.

## Free-code Parity Map

M11 migrated the free-code TUI surfaces into `ga_engineered` as follows:

| Free-code area | `ga_engineered` implementation |
|---|---|
| Prompt input, footer, queued prompts, quick open, global search, model/theme/thinking controls | `App.tsx`, `components/promptInput/footer.tsx`, `quickOpenDialog.tsx`, `globalSearchDialog.tsx`, `modelPicker.tsx`, `themePicker.tsx`, `thinkingToggle.tsx`, `state/promptQueue.ts` |
| Transcript/message surface | `virtualMessageList.tsx`, `messageRow.tsx`, `messageSelector.tsx`, `historySearchOverlay.tsx`, `globalSearchDialog.tsx`, `state/transcriptStore.ts` |
| Tool rendering | `toolUseLoader.tsx`, `bashModeProgress.tsx`, `fileEditToolDiff.tsx`, `structuredDiff.tsx`, `toolSummary.ts`; shell/code-run results render as `Bash(...)` / `Python(...)` with free-code-style preview lines and `… +N lines (ctrl+o to expand)`, `ctrl+o` toggles detailed transcript mode, `ctrl+e` toggles show-all, and finished assistant rows keep `✻ Crunched for ...` timing. |
| Slash/local commands and settings | Python `commands/*`, `docs/COMMANDS.md`, `slashOverlay.tsx`; free-code command names are implemented or explicitly feature-gated. |
| Permissions and sandbox | `runtime/approvals.py`, `/permissions`, `/sandbox-toggle`, `approvalPrompt.tsx`, `permissionRequest.tsx`, `sandboxPermissionRequest.tsx` |
| Session/task/worktree panels | `sessionBrowser.tsx`, `backgroundTasksDialog.tsx`, `worktreeDialog.tsx`, gateway methods `session.*`, `tasks.list`, `worktree.status` |
| MCP/plugin/agent/hooks panels | `state/extension_views.py`, `/mcp`, `/plugin`, `/agents`, `/hooks`, `ExtensionList` dialogs. Hooks are read-only discovery; editor/execution lifecycle remains gated. |
| External integrations | `state/integration_views.py`, `/integrations`, `/ide`, `/desktop`, `/chrome`, `/voice`, `/remote`, `/mobile`, `/teleport`, `integrationStatusDialog.tsx` |
| Onboarding/status/rate-limit notices | `welcome.tsx`, `statusNotices.tsx`, `rateLimitOptions.tsx`, `/rate-limit-options`, `CHANGELOG.md` |

Unsupported write/connect flows are intentionally visible but fail closed with
`metadata.unavailable=true` until their backends exist.

## Transcript Mode

`ctrl+o` toggles the free-code-style detailed transcript view. In detailed
mode, collapsed tool results are expanded at render time without mutating the
stored transcript item, so Space in the message navigator can still toggle a
single tool independently. `ctrl+e` toggles show-all transcript rendering and
disables the normal tail windowing so older transcript rows remain visible.

## Why two languages?

The Python runtime is the source of truth for everything that touches the
LLM, tool execution, session state, auth, and policy. We do not want a
second copy of any of that in TypeScript — drift between two runtimes is
a debugging nightmare. By contrast, the rendering layer benefits from
React's component model and Ink's flex layout, which is hard to match in
Rich/prompt-toolkit. Splitting at the IPC boundary keeps each side
focused on what it's good at and lets us reuse `RuntimeEvent.to_dict()`
verbatim as the wire payload.
