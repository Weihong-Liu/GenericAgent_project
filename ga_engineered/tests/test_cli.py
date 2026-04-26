import contextlib
import io
import os
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generic_agent_engineered import __version__
from generic_agent_engineered.cli import main
from generic_agent_engineered.cli.status import RuntimeStatus, render_status


def _run_cli(argv: list[str]) -> tuple[int, str]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        exit_code = main(argv)
    return exit_code, buffer.getvalue()


class CliTests(unittest.TestCase):
    def test_cli_version_fast_path(self):
        exit_code, output = _run_cli(["--version"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(output.strip(), __version__)

    def test_cli_doctor_returns_zero_on_scaffold(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"GENERIC_AGENT_HOME": tmp},
        ):
            exit_code, output = _run_cli(["doctor"])

        self.assertEqual(exit_code, 0)
        self.assertIn("GenericAgent Engineered", output)
        self.assertIn("provider", output)
        self.assertIn("auth", output)
        self.assertIn("state", output)
        self.assertIn("tools", output)
        self.assertIn("scaffold-ok", output)

    def test_cli_status_command_outputs_runtime_context(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.chdir(tmp), patch.dict(
            os.environ,
            {"GENERIC_AGENT_HOME": tmp},
        ):
            exit_code, output = _run_cli(["status"])

        self.assertEqual(exit_code, 0)
        self.assertIn("GenericAgent Engineered Status", output)
        self.assertIn("session      default", output)
        self.assertIn("provider     openai", output)
        self.assertIn("model        gpt-5.4", output)
        self.assertIn(tmp, output)

    def test_status_formatting(self):
        status = RuntimeStatus(
            session_id="session-1",
            turn_count=3,
            provider="openai",
            transport="openai_responses",
            model="gpt-5.4",
            home=Path("/tmp/ga-home"),
            state_dir=Path("/tmp/ga-home/state"),
            auth_path=Path("/tmp/ga-home/auth.json"),
            language="zh",
            yolo=False,
        )

        output = render_status(status)

        self.assertIn("session      session-1", output)
        self.assertIn("turns        3", output)
        self.assertIn("yolo         false", output)

    def test_cli_chat_dispatches_slash_command(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"GENERIC_AGENT_HOME": tmp},
        ):
            exit_code, output = _run_cli(["chat", "/status"])

        self.assertEqual(exit_code, 0)
        self.assertIn("GenericAgent Engineered Status", output)

    def test_cli_tools_command_lists_browser_open_tool(self):
        exit_code, output = _run_cli(["chat", "/tools"])

        self.assertEqual(exit_code, 0)
        self.assertIn("web_open", output)
        self.assertIn("web_scan", output)

    def test_cli_task_compat_mode_writes_legacy_output_file(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"GENERIC_AGENT_HOME": tmp},
        ):
            task_dir = Path(tmp) / "task"
            exit_code, output = _run_cli(["task", str(task_dir), "--input", "/status"])

            written = (task_dir / "output.txt").read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn("GenericAgent Engineered Status", output)
        self.assertIn("[ROUND END]", written)

    def test_cli_reflect_compat_mode_runs_one_check_cycle(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"GENERIC_AGENT_HOME": tmp},
        ):
            script = Path(tmp) / "reflect_script.py"
            script.write_text("def check():\n    return '/status'\n", encoding="utf-8")

            exit_code, output = _run_cli(["reflect", str(script), "--once"])

        self.assertEqual(exit_code, 0)
        self.assertIn("GenericAgent Engineered Status", output)


class LauncherRoutingTests(unittest.TestCase):
    """Bare invocations and ``tui``/``chat`` (no slash) all go through the launcher."""

    def test_no_argv_routes_to_launcher(self):
        with patch(
            "generic_agent_engineered.cli.launcher.main", return_value=0
        ) as launcher:
            exit_code, output = _run_cli([])

        self.assertEqual(exit_code, 0)
        self.assertEqual(output, "")
        launcher.assert_called_once_with([])

    def test_tui_subcommand_routes_to_launcher(self):
        with patch(
            "generic_agent_engineered.cli.launcher.main", return_value=0
        ) as launcher:
            exit_code, output = _run_cli(["tui"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(output, "")
        launcher.assert_called_once_with([])

    def test_tui_subcommand_forwards_extra_args(self):
        with patch(
            "generic_agent_engineered.cli.launcher.main", return_value=0
        ) as launcher:
            exit_code, _ = _run_cli(["tui", "--example", "foo"])

        self.assertEqual(exit_code, 0)
        launcher.assert_called_once_with(["--example", "foo"])

    def test_chat_without_prompt_routes_to_launcher(self):
        with patch(
            "generic_agent_engineered.cli.launcher.main", return_value=0
        ) as launcher:
            exit_code, output = _run_cli(["chat"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(output, "")
        launcher.assert_called_once_with([])

    def test_chat_with_free_text_routes_to_launcher(self):
        with patch(
            "generic_agent_engineered.cli.launcher.main", return_value=0
        ) as launcher:
            exit_code, output = _run_cli(["chat", "hello"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(output, "")
        launcher.assert_called_once_with([])


class LauncherInternalsTests(unittest.TestCase):
    """The launcher itself: bundle resolution and the missing-binary error path."""

    def test_explicit_bundle_override_via_env(self):
        from generic_agent_engineered.cli.launcher import main as launcher_main

        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle.js"
            bundle.write_text("// stub\n", encoding="utf-8")

            # ``GA_LAUNCHER_NO_EXEC`` keeps the launcher in
            # ``subprocess.call`` mode so the test process is not
            # replaced by exec.
            with (
                patch.dict(
                    os.environ,
                    {
                        "GA_TUI_BUNDLE": str(bundle),
                        "GA_NODE": "/usr/bin/true",
                        "GA_LAUNCHER_NO_EXEC": "1",
                    },
                ),
                patch("subprocess.call", return_value=0) as call,
            ):
                rc = launcher_main(["--example"])

            self.assertEqual(rc, 0)
            args, _ = call.call_args
            invocation = args[0]
            self.assertEqual(invocation[0], "/usr/bin/true")
            # ``Path.resolve`` may canonicalise /var → /private/var on macOS.
            self.assertEqual(Path(invocation[1]).resolve(), bundle.resolve())
            self.assertEqual(invocation[2:], ["--example"])

    def test_missing_node_returns_127(self):
        from generic_agent_engineered.cli.launcher import main as launcher_main

        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle.js"
            bundle.write_text("// stub\n", encoding="utf-8")

            with (
                patch.dict(
                    os.environ,
                    {
                        "GA_TUI_BUNDLE": str(bundle),
                        "GA_NODE": "",
                        "GA_LAUNCHER_NO_EXEC": "1",
                    },
                    clear=False,
                ),
                patch("shutil.which", return_value=None),
                patch("sys.stderr"),
            ):
                rc = launcher_main([])

            self.assertEqual(rc, 127)

    def test_missing_bundle_returns_1(self):
        from generic_agent_engineered.cli.launcher import main as launcher_main

        # Point GA_TUI_BUNDLE at a path that does not exist.
        with patch.dict(
            os.environ,
            {"GA_TUI_BUNDLE": "/no/such/bundle.js", "GA_LAUNCHER_NO_EXEC": "1"},
        ), patch("sys.stderr"):
            rc = launcher_main([])

        self.assertEqual(rc, 1)


class BridgeCommandTests(unittest.TestCase):
    """``gae bridge`` locates the legacy TMWebDriver and runs a foreground loop."""

    def test_missing_legacy_returns_1(self):
        from generic_agent_engineered.cli.bridge import main as bridge_main

        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"GA_LEGACY_BRIDGE_DIR": tmp}
        ), patch("sys.stderr"):
            rc = bridge_main([])

        self.assertEqual(rc, 1)

    def test_explicit_legacy_dir_imports_module(self):
        """A workspace with a fake TMWebDriver.py is enough to bootstrap."""
        from generic_agent_engineered.cli.bridge import main as bridge_main

        with tempfile.TemporaryDirectory() as tmp:
            stub = Path(tmp) / "TMWebDriver.py"
            stub.write_text(
                "class TMWebDriver:\n"
                "    def __init__(self, *, host, port):\n"
                "        self.host = host\n"
                "        self.port = port\n",
                encoding="utf-8",
            )

            # Use a threading.Event we can set immediately so the wait
            # returns without an actual signal interrupt.
            with patch.dict(
                os.environ,
                {"GA_LEGACY_BRIDGE_DIR": tmp, "GA_BRIDGE_HOST": "127.0.0.1"},
            ), patch("sys.stderr"), patch(
                "threading.Event"
            ) as event_class, patch("signal.signal"):
                instance = unittest.mock.MagicMock()
                instance.wait.return_value = True
                event_class.return_value = instance

                rc = bridge_main([])

            self.assertEqual(rc, 0)
            instance.wait.assert_called_once()

    def test_exec_mode_calls_os_execvp_with_command(self):
        """The default path execs node and never returns to Python."""
        from generic_agent_engineered.cli.launcher import main as launcher_main

        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle.js"
            bundle.write_text("// stub\n", encoding="utf-8")

            with (
                patch.dict(
                    os.environ,
                    {"GA_TUI_BUNDLE": str(bundle), "GA_NODE": "/usr/bin/true"},
                    # Ensure NO_EXEC is unset for this test.
                    clear=False,
                ),
                patch("os.execvp", side_effect=SystemExit(0)) as execvp,
            ):
                os.environ.pop("GA_LAUNCHER_NO_EXEC", None)
                with self.assertRaises(SystemExit):
                    launcher_main(["alpha", "beta"])

            args, _ = execvp.call_args
            self.assertEqual(args[0], "/usr/bin/true")
            self.assertEqual(args[1][0], "/usr/bin/true")
            self.assertEqual(Path(args[1][1]).resolve(), bundle.resolve())
            self.assertEqual(args[1][2:], ["alpha", "beta"])


if __name__ == "__main__":
    unittest.main()
