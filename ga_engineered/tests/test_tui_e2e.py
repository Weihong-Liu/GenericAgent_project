"""End-to-end gateway smoke test.

Spawns the Python gateway directly and feeds it enough stdin to
round-trip a single ``runtime.status`` request, then a
``gateway.shutdown``. This exercises the wire protocol and the
``GatewayServer`` lifecycle end-to-end, but does **not** drive the
launcher → node → gatewayClient chain — that requires a TTY (Ink
refuses to render without one) and is left to manual smoke testing.

The skip guards on ``node`` + ``BUNDLE`` are kept for forward
compatibility with a future TS-side e2e: they ensure this test only
runs in environments where the full chain *could* be tested.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "src" / "generic_agent_engineered" / "_tui_dist" / "bundle.js"
GATEWAY_MODULE = "generic_agent_engineered.gateway"


def _has_node() -> bool:
    return shutil.which("node") is not None


@unittest.skipUnless(_has_node(), "requires `node` on PATH")
@unittest.skipUnless(BUNDLE.is_file(), f"requires staged TUI bundle at {BUNDLE}")
class TuiE2ETests(unittest.TestCase):
    """Drive the gateway directly to prove the Python ↔ TS handshake works."""

    def test_gateway_round_trip(self) -> None:
        """``python -m gateway`` accepts JSON-RPC and emits ready+response."""

        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src") + (
            os.pathsep + env["PYTHONPATH"] if "PYTHONPATH" in env else ""
        )

        # Send runtime.status then gateway.shutdown; expect four frames
        # back: gateway.ready event, runtime.status response,
        # gateway.shutdown response, gateway.shutdown event.
        stdin_payload = (
            json.dumps({"type": "request", "id": 1, "method": "runtime.status", "params": {}})
            + "\n"
            + json.dumps({"type": "request", "id": 2, "method": "gateway.shutdown", "params": {}})
            + "\n"
        )

        proc = subprocess.run(
            [sys.executable, "-m", GATEWAY_MODULE],
            input=stdin_payload,
            capture_output=True,
            timeout=10,
            env=env,
            text=True,
        )

        self.assertEqual(proc.returncode, 0, msg=f"stderr: {proc.stderr}")

        frames = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
        kinds = [(f.get("type"), f.get("kind"), f.get("id")) for f in frames]

        # Required frames in order:
        self.assertIn(("event", "gateway.ready", None), kinds)
        self.assertIn(("response", None, 1), kinds)
        self.assertIn(("response", None, 2), kinds)
        self.assertIn(("event", "gateway.shutdown", None), kinds)

        status_response = next(
            f for f in frames if f.get("id") == 1 and f.get("type") == "response"
        )
        self.assertEqual(status_response["result"]["protocol_version"], "1.0")


if __name__ == "__main__":
    unittest.main()
