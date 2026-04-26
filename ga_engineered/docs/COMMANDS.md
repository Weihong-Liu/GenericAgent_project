# Slash Commands

`ga_engineered` exposes slash commands through the Python command router and
the TypeScript TUI slash overlay.

## Core Local Commands

- `/commands`, `/help` - list command metadata.
- `/status`, `/usage`, `/stats`, `/summary`, `/version` - inspect runtime
  state, usage estimates, and package version.
- `/new`, `/clear`, `/history`, `/retry`, `/undo`, `/compact`, `/resume`,
  `/rename`, `/sessions`, `/tasks`, `/worktree` - manage or inspect the
  current session, background work, and git worktree.
- `/export` - print the conversation history as JSON.
- `/diff` - show a unified diff between the last two conversation messages.
- `/model`, `/providers`, `/config`, `/env`, `/login`, `/logout` - inspect or
  change provider configuration.
- `/tools`, `/skills`, `/memory`, `/doctor` - inspect local tool, skill,
  memory, and environment state.
- `/mcp`, `/plugin`, `/agents`, `/hooks` - inspect local extension
  configuration and definitions. Write/edit subcommands are explicitly
  unavailable until their backend flows exist.
- `/integrations`, `/ide`, `/desktop`, `/chrome`, `/voice`, `/remote`,
  `/mobile`, `/teleport` - inspect external integration status. Unsupported
  action subcommands fail closed with `unavailable` metadata.
- `/bridge` - show the browser bridge command and auto-spawn note for
  `web_scan` / `web_execute_js`.
- `/permissions`, `/sandbox-toggle` - inspect persistent tool approvals
  and switch the current runtime between approval-required and yolo modes.
- `/keybindings`, `/statusline`, `/vim`, `/theme`, `/rate-limit-options` -
  TUI-facing controls, status information, and quota recovery guidance.

## Feature-Gated Commands

These commands are registered for free-code parity and appear in the slash
overlay, but return an explicit unavailable result until backend support is
implemented:

- `/branch`
- `/rewind`
- `/copy`
- `/output-style`
- `/effort`
- `/add-dir`, `/advisor`, `/assistant`, `/btw`, `/color`, `/context`, `/cost`,
  `/extra-usage`, `/fast`, `/feedback`, `/files`, `/heapdump`, `/insights`,
  `/init`, `/install-github-app`, `/install-slack-app`, `/onboarding`, `/passes`,
  `/plan`, `/pr_comments`, `/privacy-settings`, `/release-notes`,
  `/reload-plugins`, `/remote-env`, `/remote-setup`, `/reset-limits`,
  `/review`, `/security-review`, `/session`, `/share`, `/stickers`, `/tag`,
  `/terminal-setup`, `/thinkback`, `/thinkback-play`, `/ultrareview`, `/upgrade`

The TUI marks these commands as `unavailable` in the slash overlay instead of
silently hiding them.

## Hooks Parity

`/hooks list` and the TUI hooks dialog currently provide read-only discovery
of local hook files. Free-code's full hooks editor and hook execution lifecycle
are not wired into the GenericAgent runtime yet; write/edit subcommands fail
closed with `metadata.unavailable=true`.
