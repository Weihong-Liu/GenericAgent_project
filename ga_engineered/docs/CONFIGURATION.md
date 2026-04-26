# Configuration

GenericAgent uses layered configuration so a repository can carry safe project
defaults while secrets and user preferences remain outside the repo.

## Resolution Order

Highest priority wins:

1. CLI overrides
2. environment variables
3. nearest project config, walking up from the current directory
4. global user config in `$GENERIC_AGENT_HOME`
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

Override it:

```bash
export GENERIC_AGENT_HOME="$HOME/.config/generic-agent"
```

Global config path:

```text
$GENERIC_AGENT_HOME/settings.json
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
$GENERIC_AGENT_HOME/auth.json
$GENERIC_AGENT_HOME/state/sessions.sqlite
```

## Supported Keys

| Key | Aliases | Meaning |
|---|---|---|
| `home` | `agent_home`, `generic_agent_home` | Override `GENERIC_AGENT_HOME` from config. |
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
| `GENERIC_AGENT_HOME` | Global config, auth, state, and memory directory. |
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
`$GENERIC_AGENT_HOME/auth.json`:

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
```

It is safe to commit `.generic-agent/settings.json` only when it contains no
secrets.
