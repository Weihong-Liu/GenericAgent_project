# Configuration

GenericAgent uses layered configuration so a repository can carry safe project
defaults while secrets and user preferences remain outside the repo.

## Resolution Order

Highest priority wins:

1. CLI overrides
2. environment variables
3. nearest project config, walking up from the current directory
4. global user config in the GenericAgent config directory
5. built-in defaults

Defaults:

- provider: `openai`
- model: `gpt-5.4`
- language: `zh`
- home: `~/.generic-agent`
- yolo: `false`
- verbose: `false`

## Project Config

Preferred path:

```text
.generic-agent/settings.json
```

Legacy project config paths are still read as fallbacks:

- `.generic-agent.json`
- `.generic-agent.yaml`
- `.generic-agent.yml`

Recommended project config:

```json
{
  "provider": "openai",
  "model": "gpt-5.4",
  "language": "zh",
  "verbose": false,
  "yolo": false,
  "env": {
    "HTTPS_PROXY": "http://127.0.0.1:7890"
  }
}
```

The loader also accepts these wrapper sections:

```json
{
  "runtime": {
    "provider": "openai",
    "model": "gpt-5.4"
  }
}
```

Supported wrapper keys are `runtime`, `generic_agent`, `generic-agent`, and
`settings`. Top-level keys are also accepted.

## Global Config

Default global directory:

```text
~/.generic-agent
```

Override it with the free-code-style config directory env var:

```bash
export GENERIC_AGENT_CONFIG_DIR="$HOME/.config/generic-agent"
```

`GA_CONFIG_DIR` is the short alias. `GENERIC_AGENT_HOME` remains supported for
older scripts. `CLAUDE_CONFIG_DIR` is accepted only as a compatibility fallback
when no GenericAgent-specific config dir variable is set, so shells copied from
free-code/Claude Code setups such as `export CLAUDE_CONFIG_DIR=.claude_config_glm`
still work during migration.

Global config path:

```text
$GENERIC_AGENT_CONFIG_DIR/settings.json
```

Example global config:

```json
{
  "provider": "openai-codex",
  "model": "gpt-5.5",
  "language": "zh",
  "env": {
    "GA_GATEWAY_PYTHON": "/Users/me/project/ga_engineered/.venv/bin/python"
  }
}
```

State and auth are stored under the same home:

```text
$GENERIC_AGENT_CONFIG_DIR/auth.json
$GENERIC_AGENT_CONFIG_DIR/state/sessions.sqlite
```

## Global Home Layout

At runtime GenericAgent initializes a free-code-inspired home layout under
`~/.generic-agent` or the configured directory. The active baseline files are:

```text
config.json
history.jsonl
settings.json
stats-cache.json
```

Standard directories:

```text
agents
backups
cache
debug
downloads
file-history
ide
paste-cache
plans
plugins
projects
session-env
sessions
shell-snapshots
skills
state
statsig
tasks
teams
telemetry
todos
transcripts
```

`settings.json.bak` and `settings.json.orig` are reserved backup paths and are
not created unless a migration or recovery flow needs them.

## Supported Keys

| Key | Aliases | Meaning |
|---|---|---|
| `home` | `agent_home`, `generic_agent_home`, `config_dir`, `generic_agent_config_dir` | Override the GenericAgent config directory from config. |
| `provider` | `default_provider` | Default provider id. |
| `model` | `default_model` | Default model name. |
| `language` | `lang` | Preferred runtime language. |
| `verbose` | | Enable verbose diagnostics. |
| `yolo` | `auto_approve` | Allow approval-bypassing tool mode where supported. |
| `proxy` | `https_proxy`, `http_proxy`, `all_proxy` | Proxy URL. |
| `env` | `environment` | Environment variables merged into runtime settings. |

Boolean values accept `true/false`, `1/0`, `yes/no`, and `on/off`.

## Environment Variables

Core runtime:

| Variable | Effect |
|---|---|
| `GENERIC_AGENT_CONFIG_DIR` | Preferred global config, auth, state, cache, session, and memory directory. |
| `GA_CONFIG_DIR` | Short alias for `GENERIC_AGENT_CONFIG_DIR`. |
| `GENERIC_AGENT_HOME` | Backward-compatible alias for the global config directory. |
| `CLAUDE_CONFIG_DIR` | free-code/Claude Code compatibility fallback, used only when no GenericAgent-specific config dir var is set. |
| `GA_PROVIDER` | Default provider id. |
| `GA_MODEL` | Default model. |
| `GA_LANG` | Preferred language. |
| `GA_VERBOSE` | Verbose diagnostics. |
| `GA_YOLO` | Approval-bypass mode where supported. |
| `GA_CONFIG_JSON` / `GENERIC_AGENT_CONFIG_JSON` | JSON config object injected from shell/CI. |
| `HTTPS_PROXY`, `HTTP_PROXY`, `ALL_PROXY` | Proxy settings. Lowercase variants also work. |

Provider credentials:

| Provider | Credential variables |
|---|---|
| OpenAI | `OPENAI_API_KEY`, optional `OPENAI_BASE_URL` |
| Anthropic | `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN`, optional `ANTHROPIC_BASE_URL` |
| Kimi / Moonshot | `KIMI_API_KEY` or `MOONSHOT_API_KEY`, optional `KIMI_BASE_URL` |
| DashScope / Qwen | `DASHSCOPE_API_KEY`, optional `DASHSCOPE_BASE_URL` |
| MiniMax | `MINIMAX_API_KEY`, optional `MINIMAX_BASE_URL` |
| Custom OpenAI-compatible | `GA_CUSTOM_API_KEY` or `OPENAI_API_KEY`, `GA_CUSTOM_BASE_URL` |

TUI and gateway:

| Variable | Effect |
|---|---|
| `GA_TUI_BUNDLE` | Override JS bundle path. |
| `GA_NODE` | Override Node executable. |
| `GA_GATEWAY_PYTHON` | Python executable used by the TS frontend to spawn the gateway. |
| `GA_GATEWAY_MODULE` | Gateway module, default `generic_agent_engineered.gateway`. |
| `GA_GATEWAY_DEBUG` | Include tracebacks in gateway error frames. |
| `GA_LAUNCHER_NO_EXEC` | Use subprocess instead of `execvp`; mainly for tests. |

Browser bridge:

| Variable | Effect |
|---|---|
| `GA_LEGACY_BRIDGE_DIR` | Directory containing legacy `TMWebDriver.py`; defaults to sibling `GenericAgent/`. |
| `GA_BRIDGE_EXTENSION_DIR` | Override bundled Chrome extension directory. |

## Provider Examples

OpenAI:

```json
{
  "provider": "openai",
  "model": "gpt-5.4",
  "env": {
    "OPENAI_API_KEY": "sk-..."
  }
}
```

OpenAI-compatible local proxy:

```json
{
  "provider": "custom",
  "model": "local-model",
  "env": {
    "GA_CUSTOM_BASE_URL": "http://127.0.0.1:8000/v1",
    "GA_CUSTOM_API_KEY": "local"
  }
}
```

Kimi:

```json
{
  "provider": "kimi",
  "model": "kimi-k2-0905-preview",
  "env": {
    "KIMI_API_KEY": "..."
  }
}
```

DashScope:

```json
{
  "provider": "dashscope",
  "model": "qwen3-coder-plus",
  "env": {
    "DASHSCOPE_API_KEY": "..."
  }
}
```

## Auth Commands

API-key providers read environment variables. Codex OAuth stores credentials in
`$GENERIC_AGENT_CONFIG_DIR/auth.json`:

```bash
uv run gae chat "/login openai-codex --headless"
uv run gae chat "/logout openai-codex"
```

The headless flow prints an authorization URL and accepts a later callback/code
without launching a browser.

## Suggested `.gitignore`

Do not commit secrets or generated state:

```gitignore
.generic-agent/auth.json
.generic-agent/state/
.generic-agent/memory/
.generic-agent/settings.local.json
.generic-agent/history.jsonl
.generic-agent/stats-cache.json
.generic-agent/transcripts/
.generic-agent/cache/
```

It is safe to commit `.generic-agent/settings.json` only when it contains no
secrets.
