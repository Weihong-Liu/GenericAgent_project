"""Launcher that spawns the bundled TypeScript / Ink frontend.

The TS bundle ships inside the wheel at
``generic_agent_engineered/_tui_dist/bundle.js``. ``GenericAgent``, ``ga``,
and ``gae`` (with no subcommand) all route through this launcher so the
user always lands in the new TUI; non-TUI subcommands like ``doctor`` /
``status`` / ``task`` / ``reflect`` are still handled by ``cli/__init__.py``.
"""

from __future__ import annotations

import importlib.resources as resources
import os
import shutil
import subprocess
import sys
from pathlib import Path

BUNDLE_PACKAGE = "generic_agent_engineered._tui_dist"
BUNDLE_FILENAME = "bundle.js"


def main(argv: list[str] | None = None) -> int:
    """Locate the bundled TS frontend and run it via ``node``.

    By default the launcher uses ``os.execvp`` so the running Python
    process is *replaced* by node — Ctrl-C, SIGTERM, ``ps``, and other
    signal/process-tree behaviour then belong to node directly without
    a Python proxy. Set ``GA_LAUNCHER_NO_EXEC=1`` to fall back to
    ``subprocess.call`` (useful for tests that need to read node's exit
    code from inside the same Python process).

    Environment overrides:

    - ``GA_TUI_BUNDLE``: absolute path to a bundle.js to run instead of
      the packaged one. Lets ``npm run dev`` iterate without rebuilding.
    - ``GA_NODE``: ``node`` binary to invoke. Defaults to whichever
      ``node`` is on ``PATH``.
    """

    args = list(argv if argv is not None else sys.argv[1:])

    bundle = _resolve_bundle()
    if bundle is None:
        return _bundle_missing_error()

    node = os.environ.get("GA_NODE") or shutil.which("node")
    if not node:
        sys.stderr.write(
            "GenericAgent: cannot find a 'node' binary on PATH. Install Node.js "
            ">= 20 and retry, or set GA_NODE to an explicit binary.\n",
        )
        return 127

    cmd = [node, str(bundle), *args]
    if os.environ.get("GA_LAUNCHER_NO_EXEC"):
        try:
            return subprocess.call(cmd)
        except KeyboardInterrupt:
            return 130

    # ``execvp`` replaces this Python process. It does not return on
    # success; on failure we fall through to subprocess as a defensive
    # fallback so the user always gets *some* output rather than a
    # silent OS error.
    try:
        os.execvp(node, cmd)
    except OSError as exc:
        sys.stderr.write(f"GenericAgent: exec of node failed: {exc}\n")
        try:
            return subprocess.call(cmd)
        except KeyboardInterrupt:
            return 130
    return 0  # pragma: no cover - execvp is unreachable on success


def _resolve_bundle() -> Path | None:
    override = os.environ.get("GA_TUI_BUNDLE")
    if override:
        candidate = Path(override).expanduser().resolve()
        return candidate if candidate.is_file() else None

    try:
        ref = resources.files(BUNDLE_PACKAGE).joinpath(BUNDLE_FILENAME)
    except (ModuleNotFoundError, FileNotFoundError):
        return None
    if not ref.is_file():
        return None
    # The setuptools wheel ships ``bundle.js`` as a regular file (see
    # ``[tool.setuptools.package-data]`` in pyproject.toml), so the
    # resource path is always a real on-disk path. If we ever switch to
    # a zipped distribution, this needs ``importlib.resources.as_file``
    # held open across the ``execvp`` — currently out of scope.
    return Path(str(ref))


def _bundle_missing_error() -> int:
    sys.stderr.write(
        "GenericAgent: the TUI bundle was not found.\n"
        "  Looked for: "
        f"{BUNDLE_PACKAGE}/{BUNDLE_FILENAME} on the import path.\n"
        "  If you are running from a source checkout, build it with "
        "'(cd ui-tui && npm install && npm run build)' "
        "and copy ui-tui/dist/bundle.js into "
        "src/generic_agent_engineered/_tui_dist/, "
        "or point GA_TUI_BUNDLE at the file.\n",
    )
    return 1


__all__ = ["main"]
