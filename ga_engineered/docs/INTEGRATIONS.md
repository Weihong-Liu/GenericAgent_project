# External Integrations

`ga_engineered` keeps free-code's external integration command surface
discoverable, but it does not claim a workflow is usable until the backend is
actually wired. Each integration returns a status, detail, and next action.

## Commands

- `/integrations` - list all known integration states.
- `/ide` - report IDE selection/open-in-editor bridge status.
- `/desktop` - report desktop companion app status.
- `/chrome` - report Chrome bridge extension, legacy bridge, and port status.
- `/voice` - report voice input/STT status.
- `/remote` - report remote session status.
- `/mobile` - report mobile handoff status.
- `/teleport` - report repository teleport status.

Only read-only `status`, `show`, `list`, and `ls` subcommands are accepted for
individual integrations. Action subcommands such as `/voice on` or `/remote
connect` return an error with `metadata.unavailable = true` so the TUI cannot
show a misleading success state.

## Chrome Bridge

The Chrome bridge is the only integration with a concrete local readiness
check today:

- `extension=present` means the bundled Chrome extension manifest exists under
  `assets/tmwd_cdp_bridge/`.
- `legacy_bridge=present` means `TMWebDriver.py` was found next to
  `ga_engineered` or via `GA_LEGACY_BRIDGE_DIR`.
- `http_port=listening` means something is serving the bridge HTTP endpoint on
  `127.0.0.1:18766`.

When the extension and legacy bridge are present but the port is closed, the
reported action is to run `gae bridge` or launch the TUI gateway with bridge
extras installed. The gateway also attempts a best-effort auto-spawn unless
`GA_NO_AUTO_BRIDGE=1` is set.

## Unsupported Integrations

IDE, desktop, voice, remote, mobile, and teleport commands are intentionally
status-only. They remain visible for parity and operator awareness, but their
action flows are fail-closed until real backends are implemented.
