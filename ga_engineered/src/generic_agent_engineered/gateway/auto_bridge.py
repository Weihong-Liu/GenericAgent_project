"""Auto-spawn the legacy browser bridge for the gateway lifetime.

The browser bridge (TMWebDriver) is what ``web_scan`` and
``web_execute_js`` need to read live pages. Manually starting it is one
extra step every session, so the gateway tries to spin one up whenever
the user has the bridge extras installed and port 18766 is free.

Lifecycle:
- On gateway start, ``maybe_spawn_bridge()`` tries to launch
  ``python -m generic_agent_engineered.cli.bridge`` as a child
  subprocess. stdout / stdin are detached (the bridge prints
  diagnostic lines to stdout that would otherwise corrupt the
  JSON-RPC channel); stderr is passed through.
- On gateway shutdown, ``terminate_bridge`` kills the child cleanly.

Disable with ``GA_NO_AUTO_BRIDGE=1``.
"""

from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import sys
from importlib.util import find_spec

BRIDGE_HTTP_PORT = 18766
BRIDGE_WS_PORT = 18765
DISABLE_ENV = "GA_NO_AUTO_BRIDGE"


def maybe_spawn_bridge() -> subprocess.Popen[bytes] | None:
    """Spawn the bridge if it isn't already running and deps are present."""

    if _disabled():
        return None
    if _port_in_use(BRIDGE_HTTP_PORT) or _port_in_use(BRIDGE_WS_PORT):
        # Something — probably a manually-started bridge — owns the
        # ports already. Reusing it is the right behaviour; we don't
        # want to fight for the slot.
        return None
    if not _bridge_deps_available():
        return None
    if not _legacy_dir_visible():
        return None

    try:
        return subprocess.Popen(
            [sys.executable, "-m", "generic_agent_engineered.cli.bridge"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            # stderr is forwarded to whatever the gateway's stderr is so
            # the user can still see fatal bridge errors.
        )
    except OSError:
        return None


def terminate_bridge(proc: subprocess.Popen[bytes] | None) -> None:
    """Cleanly stop a bridge spawned by :func:`maybe_spawn_bridge`."""

    if proc is None:
        return
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=1)


def _disabled() -> bool:
    return os.environ.get(DISABLE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _port_in_use(port: int, *, host: str = "127.0.0.1") -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.2)
    try:
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


def _bridge_deps_available() -> bool:
    # Cheap import probe — find_spec doesn't actually load the modules.
    for name in ("bottle", "simple_websocket_server", "bs4", "requests"):
        if find_spec(name) is None:
            return False
    return True


def _legacy_dir_visible() -> bool:
    """``cli.bridge`` itself does the real lookup; this is just a fast pre-check."""

    from generic_agent_engineered.cli.bridge import _resolve_legacy_dir

    return _resolve_legacy_dir() is not None


__all__ = [
    "BRIDGE_HTTP_PORT",
    "BRIDGE_WS_PORT",
    "maybe_spawn_bridge",
    "terminate_bridge",
]
