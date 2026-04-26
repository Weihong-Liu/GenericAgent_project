"""CLI bootstrap for GenericAgent Engineered.

The interactive TUI lives in the TypeScript / Ink frontend at
``ui-tui/``. ``GenericAgent`` and ``ga`` (and ``gae`` with no subcommand)
spawn that bundle through :mod:`generic_agent_engineered.cli.launcher`.
The Python ``cli`` only owns the non-interactive subcommands:
``doctor``, ``status``, ``commands``, ``task``, ``reflect``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from generic_agent_engineered import __version__


def main(argv: list[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if args_list == ["--version"]:
        print(__version__)
        return 0

    # Intercept ``tui`` before argparse so any flags after it (e.g. a
    # future ``--profile prod``) flow through to the TS bundle without
    # the top-level parser rejecting them as unknown.
    if args_list and args_list[0] == "tui":
        return _run_tui(args_list[1:])

    parser = _build_parser()
    args = parser.parse_args(args_list)

    if args.version:
        print(__version__)
        return 0
    if args.command is None:
        # Bare ``GenericAgent`` / ``ga`` / ``gae`` invocation drops straight
        # into the TS TUI.
        return _run_tui([])
    if args.command == "doctor":
        from .doctor import run_doctor

        return run_doctor()
    if args.command == "status":
        from .status import render_status

        print(render_status())
        return 0
    if args.command == "commands":
        _print_commands()
        return 0
    if args.command == "chat":
        prompt = " ".join(args.prompt).strip()
        if prompt.startswith("/"):
            from generic_agent_engineered.commands import CommandContext, CommandRouter

            command_result = CommandRouter().dispatch(prompt, CommandContext())
            print(command_result.content)
            return 1 if command_result.is_error else 0
        # Anything else (empty prompt or free-form message) launches the TUI.
        return _run_tui([])
    if args.command == "task":
        from generic_agent_engineered.compat import run_task_io

        task_result = run_task_io(Path(args.iodir), input_text=args.input)
        print(task_result.output)
        return 0
    if args.command == "reflect":
        from generic_agent_engineered.compat import run_reflect_once

        reflect_result = run_reflect_once(Path(args.script))
        if reflect_result.triggered:
            print(reflect_result.output)
        else:
            print("No reflect task triggered.")
        return 0
    if args.command == "bridge":
        from .bridge import main as bridge_main

        return bridge_main([] if args.port is None else [str(args.port)])

    parser.print_help()
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gae")
    parser.add_argument("--version", action="store_true")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("doctor")
    sub.add_parser("status")
    sub.add_parser("commands")
    # ``tui`` is intercepted in ``main`` before argparse so its flags can
    # forward through to the TS bundle. We still register the parser here
    # so ``-h`` / ``--help`` listings show the subcommand.
    sub.add_parser("tui", help="Launch the interactive terminal UI")
    chat = sub.add_parser("chat")
    chat.add_argument("prompt", nargs="*")
    task = sub.add_parser("task")
    task.add_argument("iodir")
    task.add_argument("--input")
    reflect = sub.add_parser("reflect")
    reflect.add_argument("script")
    reflect.add_argument("--once", action="store_true", help="Run one check() cycle")
    bridge = sub.add_parser(
        "bridge",
        help=(
            "Start the browser bridge for web_scan/web_execute_js. "
            "Requires the bridge extras and the Chrome extension."
        ),
    )
    bridge.add_argument(
        "--port",
        type=int,
        default=None,
        help="WebSocket port (default 18765); HTTP /link runs on PORT+1.",
    )
    return parser


def _print_commands() -> None:
    from generic_agent_engineered.commands import commands_by_category

    for category, commands in commands_by_category().items():
        print(f"\n{category}")
        for command in commands:
            alias = (
                f" aliases: {', '.join('/' + alias for alias in command.aliases)}"
                if command.aliases
                else ""
            )
            hint = f" {command.args_hint}" if command.args_hint else ""
            print(f"  /{command.name}{hint} - {command.description}{alias}")


def _run_tui(forwarded_argv: list[str]) -> int:
    from .launcher import main as launcher_main

    return launcher_main(forwarded_argv)


__all__ = ["main"]
