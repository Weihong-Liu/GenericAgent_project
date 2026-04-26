"""``gae bridge`` — start the browser bridge that ``web_scan`` / ``web_execute_js`` need.

The bridge is the legacy ``GenericAgent/TMWebDriver.py`` server: it
listens for the Chrome extension on a WebSocket and exposes an HTTP
``/link`` endpoint at ``http://127.0.0.1:18766/link`` that the engineered
``cdp_bridge`` client posts to. Without it, every browser tool returns
``browser bridge unavailable``.

This wrapper:

1. Ensures the bundled Chrome extension at
   ``ga_engineered/assets/tmwd_cdp_bridge/`` has its per-install
   ``config.js`` (generated on first run, gitignored).
2. Locates the legacy ``TMWebDriver.py`` (workspace sibling, env var
   override).
3. Imports it, instantiates the driver (which spawns a daemon
   WebSocket thread on 18765 and a daemon HTTP thread on 18766).
4. Blocks on a foreground signal loop so the daemon threads keep
   running until the user hits Ctrl-C.

Run ``uv sync --extra bridge`` first to install the legacy deps
(``bottle``, ``simple-websocket-server``, ``beautifulsoup4``,
``requests``). Install the Chrome extension once via
``chrome://extensions`` → "Load unpacked" → pick the path printed at
startup. The legacy ``GenericAgent/assets/tmwd_cdp_bridge/`` copy is
no longer required.
"""

from __future__ import annotations

import os
import random
import signal
import sys
import threading
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 18765  # HTTP /link runs on PORT + 1 = 18766.

LEGACY_ENV = "GA_LEGACY_BRIDGE_DIR"
LEGACY_FILENAME = "TMWebDriver.py"

EXTENSION_ENV = "GA_BRIDGE_EXTENSION_DIR"
EXTENSION_SUBPATH = ("assets", "tmwd_cdp_bridge")


def main(argv: list[str] | None = None) -> int:
    """Start the bridge in the foreground until Ctrl-C."""

    args = list(argv if argv is not None else [])
    host = os.environ.get("GA_BRIDGE_HOST", DEFAULT_HOST)
    port = _resolve_port(args)

    extension_dir = _resolve_extension_dir()
    config_note = _ensure_config_js(extension_dir)

    legacy_dir = _resolve_legacy_dir()
    if legacy_dir is None:
        return _missing_legacy_error()

    sys.path.insert(0, str(legacy_dir))
    try:
        from TMWebDriver import TMWebDriver  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        sys.stderr.write(
            f"GenericAgent: cannot import the legacy TMWebDriver bridge: {exc}\n"
            "  Install the bridge extras first: uv sync --extra bridge\n"
            "  (the bridge needs bottle, simple-websocket-server, "
            "beautifulsoup4, requests)\n",
        )
        return 1

    sys.stderr.write(
        f"GenericAgent bridge: ws://{host}:{port} + http://{host}:{port + 1}/link\n"
        f"  Chrome extension: {extension_dir}\n"
        + (f"  {config_note}\n" if config_note else "")
        + "  Press Ctrl-C to stop.\n",
    )

    TMWebDriver(host=host, port=port)

    # The legacy driver runs the WebSocket server and the HTTP server in
    # daemon threads, so its own ``__main__`` block exits immediately and
    # the threads die. Block here on a signal so the user has a real
    # foreground process to Ctrl-C.
    stop = threading.Event()

    def _on_signal(signum, _frame) -> None:  # type: ignore[no-untyped-def]
        sys.stderr.write("\nGenericAgent bridge: shutting down\n")
        stop.set()

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)
    stop.wait()
    return 0


def _resolve_extension_dir() -> Path:
    """Return the directory of the bundled CDP bridge Chrome extension.

    Defaults to ``ga_engineered/assets/tmwd_cdp_bridge/`` (the copy that
    ships with this package). ``$GA_BRIDGE_EXTENSION_DIR`` overrides
    when the user has placed the extension elsewhere.
    """

    override = os.environ.get(EXTENSION_ENV)
    if override:
        return Path(override).expanduser().resolve()
    package_root = Path(__file__).resolve().parents[3]
    return (package_root.joinpath(*EXTENSION_SUBPATH)).resolve()


def _ensure_config_js(extension_dir: Path) -> str | None:
    """Create the per-install ``config.js`` if it does not exist.

    The extension's ``manifest.json`` lists ``config.js`` as a content
    script, but the file is gitignored — Chrome refuses to load the
    manifest until it exists. The file only needs to define a unique
    ``TID`` constant that ``content.js`` uses to tag injected DOM
    nodes (matching the legacy ``agentmain.py`` first-run logic).

    Returns a one-line note when the file was just created, or None if
    it already existed (or could not be created).
    """

    cfg = extension_dir / "config.js"
    if cfg.exists():
        return None
    try:
        extension_dir.mkdir(parents=True, exist_ok=True)
        tid_hex = hex(random.randint(0, 99999999))[2:8]
        cfg.write_text(f"const TID = '__ljq_{tid_hex}';", encoding="utf-8")
    except OSError as exc:
        sys.stderr.write(
            f"GenericAgent bridge: cannot write {cfg}: {exc}\n"
            "  Chrome will refuse to load the extension until config.js exists.\n"
        )
        return None
    return f"Generated {cfg.name} (TID=__ljq_{tid_hex})"


def _resolve_port(argv: list[str]) -> int:
    if argv and argv[0].isdigit():
        return int(argv[0])
    return int(os.environ.get("GA_BRIDGE_PORT", DEFAULT_PORT))


def _resolve_legacy_dir() -> Path | None:
    """Return the directory containing ``TMWebDriver.py`` or None.

    Search order:
      1. ``$GA_LEGACY_BRIDGE_DIR`` (explicit override).
      2. ``$CWD/../GenericAgent`` (typical monorepo layout).
      3. The Python package directory's parent / ``GenericAgent``.
    """

    override = os.environ.get(LEGACY_ENV)
    if override:
        candidate = Path(override).expanduser().resolve()
        if (candidate / LEGACY_FILENAME).is_file():
            return candidate
        return None

    cwd_parent = Path.cwd().parent / "GenericAgent"
    if (cwd_parent / LEGACY_FILENAME).is_file():
        return cwd_parent.resolve()

    package_root = Path(__file__).resolve().parents[3]
    workspace_sibling = package_root.parent / "GenericAgent"
    if (workspace_sibling / LEGACY_FILENAME).is_file():
        return workspace_sibling.resolve()
    return None


def _missing_legacy_error() -> int:
    sys.stderr.write(
        "GenericAgent: cannot find the legacy TMWebDriver bridge.\n"
        f"  Looked for {LEGACY_FILENAME} next to ga_engineered/ and via\n"
        f"  ${LEGACY_ENV}. Either check out the legacy GenericAgent\n"
        "  package next to ga_engineered/, or set\n"
        f"  {LEGACY_ENV}=/path/to/legacy/dir.\n",
    )
    return 1


__all__ = ["main"]


if __name__ == "__main__":
    # ``python -m generic_agent_engineered.cli.bridge`` (used by the
    # gateway's auto-spawn path) needs an explicit runner — ``def main``
    # alone is invisible to the ``-m`` invocation.
    sys.exit(main(sys.argv[1:]))
