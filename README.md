# GenericAgent Project

`GenericAgent_project` is the working umbrella repository for the GenericAgent
modernization effort.

The main implementation is [`ga_engineered/`](ga_engineered/), which is uploaded
directly in this repository as normal source code. The other directories are
kept as child repositories because they are either the legacy upstream or
external references used during the migration.

## Repository Layout

| Path | Role |
|---|---|
| [`ga_engineered/`](ga_engineered/) | Primary engineered GenericAgent runtime and TUI. This is the code to install, run, and develop. |
| [`GenericAgent/`](GenericAgent/) | Legacy GenericAgent repository used for behavior compatibility and migration references. |
| [`free-code/`](free-code/) | Reference repository for free-code/Claude-Code-style TUI behavior. |
| [`hermes-agent/`](hermes-agent/) | Reference repository for provider/auth/CLI/TUI patterns. |
| [`docs/`](docs/) | Parent-level architecture notes and generated architecture diagram. |
| [`AGENTS.md`](AGENTS.md) | Workspace-level agent instructions and development policy. |

## Quick Start

```bash
cd ga_engineered
uv sync --extra dev
SKIP_INSTALL=1 ./scripts/build_tui.sh
uv run GenericAgent
```

The engineered package exposes three equivalent entry points:

```bash
uv run GenericAgent
uv run ga
uv run gae
```

For global installation:

```bash
cd ga_engineered
SKIP_INSTALL=1 ./scripts/build_tui.sh
uv tool install --force .
GenericAgent
```

## Engineered Runtime Documentation

Start with [`ga_engineered/README.md`](ga_engineered/README.md), then use:

- [`ga_engineered/docs/INSTALLATION.md`](ga_engineered/docs/INSTALLATION.md)
- [`ga_engineered/docs/CONFIGURATION.md`](ga_engineered/docs/CONFIGURATION.md)
- [`ga_engineered/docs/DEPLOYMENT.md`](ga_engineered/docs/DEPLOYMENT.md)
- [`ga_engineered/docs/DEVELOPMENT.md`](ga_engineered/docs/DEVELOPMENT.md)
- [`ga_engineered/docs/TUI.md`](ga_engineered/docs/TUI.md)
- [`ga_engineered/docs/COMMANDS.md`](ga_engineered/docs/COMMANDS.md)

The most important configuration file is project-local
`.generic-agent/settings.json`; global state and credentials live under
`$GENERIC_AGENT_HOME` (default `~/.generic-agent`).

## Child Repository Policy

`GenericAgent`, `free-code`, and `hermes-agent` are tracked as child Git
repositories/submodules. They should remain separate so their upstream history
and remotes are not flattened into this parent repository.

`ga_engineered` is not treated as a remote child repository for the current
upload. It is committed directly into this parent repository so a clone of
`GenericAgent_project` contains the engineered implementation without an
additional submodule fetch.

## Verification

Common local verification:

```bash
cd ga_engineered
python3 -m json.tool tasks.json >/dev/null
python3 -m compileall -q src tests
cd ui-tui && npm run type-check && npm test
cd ..
SKIP_INSTALL=1 ./scripts/build_tui.sh
```

See [`ga_engineered/tasks/TASK_REPORT.md`](ga_engineered/tasks/TASK_REPORT.md)
for task-by-task verification notes and known local environment gaps.
