"""Configuration and auth slash command handlers."""

from __future__ import annotations

import json
import os
import urllib.parse
from collections.abc import Mapping
from typing import Any

from generic_agent_engineered.auth.openai_oauth import PROVIDER_ID, OpenAICodexOAuthClient
from generic_agent_engineered.auth.store import AuthStore
from generic_agent_engineered.config import CONFIG_DIR_ENV_NAMES, PROXY_ENV_NAMES

from .base import CommandContext, CommandHandler, CommandResult, ParsedCommand

SECRET_NAME_PARTS = ("KEY", "TOKEN", "SECRET", "AUTH")


def handle_model(context: CommandContext, parsed: ParsedCommand) -> CommandResult:
    try:
        model, provider = _parse_model_args(parsed.argv)
        context.runtime.switch_model(model, provider)
    except (KeyError, ValueError) as exc:
        return CommandResult(str(exc), is_error=True)

    provider_spec = context.runtime.current_provider()
    return CommandResult(
        f"Active model: {context.runtime.state.model} ({provider_spec.id})",
        metadata={"model": context.runtime.state.model, "provider": provider_spec.id},
    )


def handle_providers(context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    current = context.runtime.state.provider_id
    lines = ["Providers"]
    for spec in context.runtime.providers.list():
        marker = "*" if spec.id == current else " "
        aliases = f" aliases={', '.join(spec.aliases)}" if spec.aliases else ""
        env_vars = f" env={', '.join(spec.api_key_env_vars)}" if spec.api_key_env_vars else ""
        lines.append(
            f"{marker} {spec.id:<14} {spec.transport:<18} auth={spec.auth_kind}{aliases}{env_vars}"
        )
    return CommandResult("\n".join(lines), metadata={"current": current})


def handle_login(context: CommandContext, parsed: ParsedCommand) -> CommandResult:
    try:
        args = _parse_login_args(parsed.argv)
    except ValueError as exc:
        return CommandResult(str(exc), is_error=True)

    if args["provider"] != PROVIDER_ID:
        return CommandResult(
            f"/login currently supports {PROVIDER_ID}; got {args['provider']}",
            is_error=True,
        )

    code = _authorization_code(args)
    if code:
        return CommandResult(
            "Authorization code received. Token exchange is intentionally explicit and mocked in "
            "tests until live OAuth callback wiring is enabled.",
            metadata={"provider": PROVIDER_ID, "code_received": True},
        )

    client = OpenAICodexOAuthClient()
    session = client.create_login_session(int(args["port"]))
    if bool(args["headless"]):
        return CommandResult(
            "\n".join(
                [
                    "OpenAI Codex headless login",
                    f"Authorization URL: {session.authorization_url}",
                    f"Redirect URI: {session.redirect_uri}",
                    "Paste the final callback URL with --callback or the code with --code.",
                ]
            ),
            metadata={
                "provider": PROVIDER_ID,
                "headless": True,
                "authorization_url": session.authorization_url,
                "redirect_uri": session.redirect_uri,
            },
        )

    import webbrowser

    opened = webbrowser.open(session.authorization_url)
    return CommandResult(
        "\n".join(
            [
                "OpenAI Codex browser login",
                f"Authorization URL: {session.authorization_url}",
                f"Redirect URI: {session.redirect_uri}",
                f"Browser opened: {str(opened).lower()}",
            ]
        ),
        metadata={
            "provider": PROVIDER_ID,
            "headless": False,
            "authorization_url": session.authorization_url,
            "redirect_uri": session.redirect_uri,
            "browser_opened": opened,
        },
    )


def handle_logout(context: CommandContext, parsed: ParsedCommand) -> CommandResult:
    provider = parsed.argv[0] if parsed.argv else PROVIDER_ID
    AuthStore(context.runtime.settings.auth_path).delete(provider)
    return CommandResult(f"Logged out: {provider}", metadata={"provider": provider})


def handle_config(context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    settings = context.runtime.settings
    payload = {
        "home": str(settings.home),
        "state_dir": str(settings.state_dir),
        "auth_path": str(settings.auth_path),
        "default_provider": settings.default_provider,
        "default_model": settings.default_model,
        "active_provider": context.runtime.state.provider_id,
        "active_model": context.runtime.state.model,
        "language": settings.language,
        "verbose": settings.verbose,
        "yolo": settings.yolo,
        "proxy": settings.proxy or "",
        "environment_keys": sorted(settings.environment),
    }
    return CommandResult(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def handle_env(context: CommandContext, _parsed: ParsedCommand) -> CommandResult:
    env = _effective_environment(context)
    names = _environment_names(context)
    lines = ["Environment"]
    for name in names:
        value = env.get(name)
        rendered = "<unset>" if value is None else _render_env_value(name, value)
        lines.append(f"  {name}={rendered}")
    return CommandResult("\n".join(lines), metadata={"names": names})


def _parse_model_args(argv: tuple[str, ...]) -> tuple[str, str | None]:
    model = ""
    provider = None
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--provider":
            if index + 1 >= len(argv):
                raise ValueError("--provider requires a value")
            provider = argv[index + 1]
            index += 2
            continue
        if arg.startswith("--provider="):
            provider = arg.split("=", 1)[1]
            index += 1
            continue
        if arg.startswith("-"):
            raise ValueError(f"unknown /model option: {arg}")
        if model:
            raise ValueError(f"unexpected extra model argument: {arg}")
        model = arg
        index += 1
    return model, provider


def _parse_login_args(argv: tuple[str, ...]) -> dict[str, Any]:
    args: dict[str, Any] = {
        "provider": PROVIDER_ID,
        "headless": False,
        "port": 1455,
        "callback": "",
        "code": "",
    }
    index = 0
    provider_set = False
    while index < len(argv):
        arg = argv[index]
        if arg == "--headless":
            args["headless"] = True
            index += 1
            continue
        if arg == "--port":
            if index + 1 >= len(argv):
                raise ValueError("--port requires a value")
            args["port"] = _positive_port(argv[index + 1])
            index += 2
            continue
        if arg.startswith("--port="):
            args["port"] = _positive_port(arg.split("=", 1)[1])
            index += 1
            continue
        if arg == "--callback":
            if index + 1 >= len(argv):
                raise ValueError("--callback requires a value")
            args["callback"] = argv[index + 1]
            index += 2
            continue
        if arg.startswith("--callback="):
            args["callback"] = arg.split("=", 1)[1]
            index += 1
            continue
        if arg == "--code":
            if index + 1 >= len(argv):
                raise ValueError("--code requires a value")
            args["code"] = argv[index + 1]
            index += 2
            continue
        if arg.startswith("--code="):
            args["code"] = arg.split("=", 1)[1]
            index += 1
            continue
        if arg.startswith("-"):
            raise ValueError(f"unknown /login option: {arg}")
        if provider_set:
            raise ValueError(f"unexpected extra login argument: {arg}")
        args["provider"] = arg
        provider_set = True
        index += 1
    return args


def _authorization_code(args: Mapping[str, Any]) -> str:
    code = str(args.get("code") or "").strip()
    if code:
        return code
    callback = str(args.get("callback") or "").strip()
    if not callback:
        return ""
    query = urllib.parse.parse_qs(urllib.parse.urlparse(callback).query)
    raw_code = query.get("code", [""])[0]
    return raw_code.strip()


def _positive_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise ValueError("--port must be an integer") from exc
    if not 0 < port <= 65535:
        raise ValueError("--port must be between 1 and 65535")
    return port


def _effective_environment(context: CommandContext) -> dict[str, str]:
    env = dict(os.environ)
    env.update(context.runtime.settings.environment)
    if context.environment is not None:
        env.update(context.environment)
    return env


def _environment_names(context: CommandContext) -> list[str]:
    names = {
        *CONFIG_DIR_ENV_NAMES,
        "GA_CONFIG_JSON",
        "GENERIC_AGENT_CONFIG_JSON",
        "GA_PROVIDER",
        "GA_MODEL",
        "GA_LANG",
        "GA_VERBOSE",
        "GA_YOLO",
        *PROXY_ENV_NAMES,
        *context.runtime.settings.environment,
    }
    for spec in context.runtime.providers.list():
        names.update(spec.api_key_env_vars)
        if spec.base_url_env_var:
            names.add(spec.base_url_env_var)
    return sorted(names)


def _render_env_value(name: str, value: str) -> str:
    if any(part in name.upper() for part in SECRET_NAME_PARTS):
        return "<set>" if value else "<empty>"
    return value or "<empty>"


CONFIG_HANDLERS: dict[str, CommandHandler] = {
    "model": handle_model,
    "providers": handle_providers,
    "login": handle_login,
    "logout": handle_logout,
    "config": handle_config,
    "env": handle_env,
}
