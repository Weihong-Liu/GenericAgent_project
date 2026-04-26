# Release Checklist

Release target: `0.1.0`

## Scope

- [x] New engineered Python project lives in [`ga_engineered`](../README.md).
- [x] Architecture is documented in [`ARCHITECTURE.md`](ARCHITECTURE.md).
- [x] Legacy GenericAgent migration is documented in [`MIGRATION.md`](MIGRATION.md).
- [x] Task plan and completion state are tracked in [`tasks.json`](../tasks.json).
- [x] Delivery evidence is tracked in [`TASK_REPORT.md`](../tasks/TASK_REPORT.md).
- [x] User-facing release notes are tracked in [`CHANGELOG.md`](../CHANGELOG.md).

## Required Gates

- [x] `python3 -m json.tool tasks.json`
- [x] `python3 -m compileall -q src tests`
- [x] `python3 -m unittest discover -s tests`
- [x] `UV_CACHE_DIR=/tmp/ga-engineered-uv-cache uv run --no-sync pytest`
- [x] `UV_CACHE_DIR=/tmp/ga-engineered-uv-cache uv run --no-sync ruff check .`
- [x] `UV_CACHE_DIR=/tmp/ga-engineered-uv-cache uv run --no-sync mypy src`
- [x] `PYTHONPATH=src python3 -m generic_agent_engineered.cli --version`
- [x] `PYTHONPATH=src python3 -m generic_agent_engineered.cli doctor`
- [x] `PYTHONPATH=src python3 -m generic_agent_engineered.cli status`
- [x] `PYTHONPATH=src python3 -m generic_agent_engineered.cli --plain --no-animations chat /status`
- [x] `PYTHONPATH=src python3 -m generic_agent_engineered.cli task /tmp/ga-engineered-task-smoke --input /status`
- [x] `UV_CACHE_DIR=/tmp/ga-engineered-uv-cache uv run --no-sync gae --version`
- [x] `test -f tasks/TASK_REPORT.md`
- [x] `test ! -e TASK_REPORT.md`
- [x] `git diff --check`

## Remaining Risks

- Live provider calls are not executed in local tests; provider clients are
  verified through fake transports.
- Live OpenAI OAuth exchange is not executed in local tests; PKCE, callback, and
  refresh seams are covered with mocked transport.
- Live browser sessions are not executed in local tests; bridge behavior is
  covered with fake TMWebDriver/CDP adapters.
- Interactive provider-backed REPL execution is still a post-release integration
  task; command routing and compatibility fixtures are covered.
- The current sandbox cannot run plain `uv run` without attempting package
  resolution; release validation uses `uv run --no-sync`.

## Release Decision

- [x] All planned `P0` and `P1` tasks are complete in [`tasks.json`](../tasks.json).
- [x] Release notes and delivery report exist.
- [x] Known non-live-test gaps are explicitly listed.
- [x] Commit messages use the Lore Commit Protocol.
