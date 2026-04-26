"""Auto-bridge spawning logic — tests cover the decision tree without
actually spawning the legacy TMWebDriver."""

from __future__ import annotations

import os
import socket
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from generic_agent_engineered.gateway import auto_bridge


@contextmanager
def _free_port_on(port: int):
    """Bind+release ``port`` so the test does not collide with anything else."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", port))
    sock.listen(1)
    try:
        yield port
    finally:
        sock.close()


class AutoBridgeTests(unittest.TestCase):
    def test_disabled_via_env(self):
        with patch.dict(os.environ, {"GA_NO_AUTO_BRIDGE": "1"}):
            self.assertIsNone(auto_bridge.maybe_spawn_bridge())

    def test_skips_when_port_already_taken(self):
        with _free_port_on(auto_bridge.BRIDGE_HTTP_PORT), patch.dict(
            os.environ, {"GA_NO_AUTO_BRIDGE": ""}
        ):
            self.assertIsNone(auto_bridge.maybe_spawn_bridge())

    def test_skips_when_deps_missing(self):
        # Pretend bottle isn't importable.
        with patch.dict(os.environ, {"GA_NO_AUTO_BRIDGE": ""}), patch(
            "generic_agent_engineered.gateway.auto_bridge.find_spec",
            return_value=None,
        ):
            self.assertIsNone(auto_bridge.maybe_spawn_bridge())

    def test_skips_when_legacy_dir_missing(self):
        with patch.dict(os.environ, {"GA_NO_AUTO_BRIDGE": ""}), patch(
            "generic_agent_engineered.gateway.auto_bridge._port_in_use",
            return_value=False,
        ), patch(
            "generic_agent_engineered.gateway.auto_bridge._bridge_deps_available",
            return_value=True,
        ), patch(
            "generic_agent_engineered.gateway.auto_bridge._legacy_dir_visible",
            return_value=False,
        ):
            self.assertIsNone(auto_bridge.maybe_spawn_bridge())

    def test_terminate_bridge_handles_none(self):
        # Should silently no-op.
        auto_bridge.terminate_bridge(None)

    def test_terminate_bridge_no_op_on_dead_process(self):
        class FakeDeadProc:
            def poll(self):
                return 0

            def terminate(self):
                raise AssertionError("should not be called for an already-dead proc")

        auto_bridge.terminate_bridge(FakeDeadProc())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
