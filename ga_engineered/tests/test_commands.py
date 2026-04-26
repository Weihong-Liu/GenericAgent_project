import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generic_agent_engineered.commands import (
    COMMAND_REGISTRY,
    CommandContext,
    CommandRouter,
    available_commands,
    commands_by_category,
    resolve_command,
)
from generic_agent_engineered.config import RuntimeSettings
from generic_agent_engineered.engine import AgentRuntime
from generic_agent_engineered.runtime.messages import Message
from generic_agent_engineered.state import SessionStore
from generic_agent_engineered.tools import FunctionTool, ToolRegistry, ToolSchema, ToolSpec


def _context(home: Path, *, env: dict[str, str] | None = None) -> CommandContext:
    runtime = AgentRuntime(settings=RuntimeSettings(home=home))
    return CommandContext(runtime=runtime, environment=env or {})


class CommandRegistryTests(unittest.TestCase):
    def test_registry_has_core_commands(self):
        names = {command.name for command in COMMAND_REGISTRY}
        for expected in {"help", "status", "model", "login", "logout", "tools", "skills"}:
            self.assertIn(expected, names)
        for expected in {
            "diff",
            "export",
            "stats",
            "summary",
            "version",
            "keybindings",
            "statusline",
            "rate-limit-options",
            "output-style",
            "effort",
            "sessions",
            "tasks",
            "worktree",
            "mcp",
            "plugin",
            "agents",
            "hooks",
            "integrations",
            "ide",
            "desktop",
            "chrome",
            "voice",
            "remote",
            "mobile",
            "teleport",
            "bridge",
            "add-dir",
            "advisor",
            "context",
            "cost",
            "files",
            "insights",
            "plan",
            "privacy-settings",
            "release-notes",
            "terminal-setup",
            "ultrareview",
            "upgrade",
        }:
            self.assertIn(expected, names)

    def test_alias_resolution(self):
        self.assertEqual(resolve_command("/quit").name, "exit")
        self.assertEqual(resolve_command("?").name, "help")

    def test_grouping(self):
        grouped = commands_by_category()
        self.assertIn("Session", grouped)
        self.assertIn("Configuration", grouped)

    def test_login_exposes_openai_codex_subcommand(self):
        login = resolve_command("/login")
        self.assertIsNotNone(login)
        self.assertIn("openai-codex", login.subcommands)
        self.assertIn("openai-codex", login.args_hint)

    def test_available_commands_can_filter_cli_only(self):
        names = {command.name for command in available_commands(include_cli_only=False)}

        self.assertIn("model", names)
        self.assertNotIn("clear", names)
        self.assertNotIn("history", names)
        self.assertNotIn("exit", names)


class CommandRouterTests(unittest.TestCase):
    def test_unknown_command_returns_suggestion(self):
        result = CommandRouter().dispatch("/modle")

        self.assertTrue(result.is_error)
        self.assertIn("Did you mean /model?", result.content)
        self.assertEqual(result.metadata["suggestion"], "model")

    def test_info_handlers_are_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            context = _context(Path(tmp))
            router = CommandRouter()

            self.assertIn("/new", router.dispatch("/commands", context).content)
            self.assertIn(
                "GenericAgent Engineered Status",
                router.dispatch("/status", context).content,
            )
            self.assertIn("Usage estimate", router.dispatch("/usage", context).content)

    def test_session_handlers_manage_history_retry_undo_compact_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            context = _context(Path(tmp))
            router = CommandRouter()
            context.runtime.state.messages = [
                Message.system("preamble"),
                Message.user("u1"),
                Message.assistant("a1"),
                Message.user("u2"),
                Message.assistant("a2"),
                Message.user("u3"),
                Message.assistant("a3"),
                Message.user("u4"),
                Message.assistant("a4"),
            ]
            context.runtime.state.turn_count = 4

            self.assertIn("History", router.dispatch("/history", context).content)
            retry = router.dispatch("/retry", context)
            self.assertEqual(retry.metadata["retry_content"], "u4")

            compact = router.dispatch("/compact focus area", context)
            self.assertFalse(compact.is_error)
            self.assertTrue(compact.metadata["changed"])
            self.assertLess(len(context.runtime.state.messages), 9)

            undo = router.dispatch("/undo", context)
            self.assertFalse(undo.is_error)
            self.assertIn("Removed", undo.content)

            resume = router.dispatch("/resume session-42", context)
            self.assertEqual(resume.metadata["session_id"], "session-42")

            cleared = router.dispatch("/clear", context)
            self.assertEqual(cleared.content, "Session cleared")
            self.assertEqual(context.runtime.state.messages, [])

            new_session = router.dispatch("/new manual-id", context)
            self.assertEqual(new_session.metadata["session_id"], "manual-id")

    def test_config_handlers_cover_model_providers_config_env_logout(self):
        with tempfile.TemporaryDirectory() as tmp:
            context = _context(
                Path(tmp),
                env={
                    "OPENAI_API_KEY": "secret",
                    "HTTPS_PROXY": "http://127.0.0.1:6152",
                },
            )
            router = CommandRouter()

            model = router.dispatch("/model claude-test --provider anthropic", context)
            self.assertFalse(model.is_error)
            self.assertEqual(context.runtime.state.model, "claude-test")
            self.assertEqual(context.runtime.state.provider_id, "anthropic")

            providers = router.dispatch("/providers", context)
            self.assertIn("* anthropic", providers.content)

            config = router.dispatch("/config", context)
            self.assertIn('"active_provider": "anthropic"', config.content)

            env = router.dispatch("/env", context)
            self.assertIn("OPENAI_API_KEY=<set>", env.content)
            self.assertIn("HTTPS_PROXY=http://127.0.0.1:6152", env.content)

            logout = router.dispatch("/logout openai-codex", context)
            self.assertFalse(logout.is_error)
            self.assertIn("Logged out", logout.content)

    def test_headless_login_command_does_not_call_webbrowser(self):
        with tempfile.TemporaryDirectory() as tmp, patch("webbrowser.open") as open_browser:
            context = _context(Path(tmp))
            result = CommandRouter().dispatch(
                "/login openai-codex --headless --port 49152",
                context,
            )

        self.assertFalse(result.is_error)
        self.assertIn("Authorization URL:", result.content)
        self.assertTrue(result.metadata["headless"])
        open_browser.assert_not_called()

    def test_login_command_accepts_code_without_browser(self):
        with tempfile.TemporaryDirectory() as tmp, patch("webbrowser.open") as open_browser:
            context = _context(Path(tmp))
            result = CommandRouter().dispatch(
                "/login openai-codex --headless --code test-code",
                context,
            )

        self.assertFalse(result.is_error)
        self.assertTrue(result.metadata["code_received"])
        open_browser.assert_not_called()

    def test_tools_memory_skills_doctor_handlers_are_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            context = _context(home)
            router = CommandRouter()

            tools = router.dispatch("/tools", context)
            self.assertIn("file_read", tools.content)

            memory = router.dispatch("/memory show", context)
            self.assertIn("No memory directory", memory.content)

            skills = router.dispatch("/skills list", context)
            self.assertIn("No skills discovered", skills.content)

            doctor = router.dispatch("/doctor", context)
            self.assertFalse(doctor.is_error)
            self.assertIn("scaffold-ok", doctor.content)

    def test_local_parity_commands_are_executable_or_explicitly_gated(self):
        with tempfile.TemporaryDirectory() as tmp:
            context = _context(Path(tmp))
            router = CommandRouter()
            context.runtime.state.messages = [
                Message.user("hello"),
                Message.assistant("hello there"),
            ]
            context.runtime.state.turn_count = 1

            self.assertIn("GenericAgent Engineered", router.dispatch("/version", context).content)
            self.assertIn('"messages": 2', router.dispatch("/stats", context).content)
            self.assertIn("Conversation summary", router.dispatch("/summary", context).content)
            self.assertIn('"role": "user"', router.dispatch("/export", context).content)
            self.assertIn("--- user:previous", router.dispatch("/diff", context).content)
            self.assertIn("Ctrl-P quick open", router.dispatch("/keybindings", context).content)
            self.assertIn("Statusline is managed", router.dispatch("/statusline", context).content)
            self.assertIn(
                "Rate limit options",
                router.dispatch("/rate-limit-options", context).content,
            )
            self.assertIn("GA_VIM_MODE", router.dispatch("/vim", context).content)
            self.assertIn("uv run gae bridge", router.dispatch("/bridge", context).content)

            renamed = router.dispatch("/rename renamed-session", context)
            self.assertFalse(renamed.is_error)
            self.assertEqual(context.runtime.state.session_id, "renamed-session")

            gated = router.dispatch("/output-style compact", context)
            self.assertTrue(gated.is_error)
            self.assertTrue(gated.metadata["unavailable"])

            parity_gated = router.dispatch("/release-notes", context)
            self.assertTrue(parity_gated.is_error)
            self.assertTrue(parity_gated.metadata["unavailable"])

    def test_session_task_worktree_commands_surface_runtime_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            context = _context(home)
            router = CommandRouter()
            store = SessionStore.from_settings(context.runtime.settings)
            store.create_session("saved", title="Saved chat")
            store.append_message("saved", Message.user("hello"))

            sessions = router.dispatch("/sessions", context)
            self.assertFalse(sessions.is_error)
            self.assertIn("saved", sessions.content)
            self.assertIn("default", sessions.content)
            self.assertEqual(len(sessions.metadata["sessions"]), 2)

            tasks = router.dispatch("/tasks", context)
            self.assertFalse(tasks.is_error)
            self.assertIn("No background tasks", tasks.content)
            self.assertFalse(tasks.metadata["busy"])

            worktree = router.dispatch("/worktree", context)
            self.assertFalse(worktree.is_error)
            self.assertIn("is_git", worktree.metadata)

    def test_extension_commands_list_read_only_surfaces_and_gate_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            agents_dir = home / "agents"
            agents_dir.mkdir(parents=True, exist_ok=True)
            agent_file = agents_dir / "demo-agent.md"
            agent_file.write_text("# demo\n", encoding="utf-8")
            context = _context(home)
            router = CommandRouter()

            self.assertIn("MCP servers", router.dispatch("/mcp", context).content)
            self.assertIn("Plugins", router.dispatch("/plugin list", context).content)
            agents = router.dispatch("/agents list", context)
            self.assertFalse(agents.is_error)
            self.assertIn("demo-agent", agents.content)
            hooks = router.dispatch("/hooks list", context)
            self.assertFalse(hooks.is_error)
            self.assertIn("items", hooks.metadata)
            self.assertIn("read-only discovery", hooks.content)

            gated = router.dispatch("/plugin install example", context)
            self.assertTrue(gated.is_error)
            self.assertTrue(gated.metadata["unavailable"])

    def test_integration_commands_are_discoverable_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            context = _context(Path(tmp))
            router = CommandRouter()

            listed = router.dispatch("/integrations", context)
            self.assertFalse(listed.is_error)
            self.assertIn("External integrations", listed.content)
            names = {item["name"] for item in listed.metadata["integrations"]}
            for expected in {
                "ide",
                "desktop",
                "chrome",
                "voice",
                "remote",
                "mobile",
                "teleport",
            }:
                self.assertIn(expected, names)

            chrome = router.dispatch("/chrome status", context)
            self.assertFalse(chrome.is_error)
            self.assertIn("Chrome bridge", chrome.content)
            self.assertIn("integration", chrome.metadata)

            voice = router.dispatch("/voice on", context)
            self.assertTrue(voice.is_error)
            self.assertTrue(voice.metadata["unavailable"])
            self.assertEqual(voice.metadata["integration"]["name"], "voice")

    def test_permissions_and_sandbox_commands_manage_runtime_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            context = _context(Path(tmp))
            router = CommandRouter()

            listed = router.dispatch("/permissions", context)
            self.assertFalse(listed.is_error)
            self.assertIn("gated tools", listed.content)

            allowed = router.dispatch("/permissions allow shell", context)
            self.assertFalse(allowed.is_error)
            self.assertIn("shell", router.dispatch("/permissions list", context).content)

            revoked = router.dispatch("/permissions revoke shell", context)
            self.assertFalse(revoked.is_error)
            self.assertTrue(revoked.metadata["removed"])

            off = router.dispatch("/sandbox-toggle off", context)
            self.assertFalse(off.is_error)
            self.assertTrue(context.runtime.settings.yolo)

            on = router.dispatch("/sandbox-toggle on", context)
            self.assertFalse(on.is_error)
            self.assertFalse(context.runtime.settings.yolo)

    def test_tools_handler_can_toggle_live_registry(self):
        registry = ToolRegistry(
            [
                FunctionTool(
                    ToolSpec(ToolSchema("demo_tool", "demo")),
                    lambda _tool_call: "ok",
                )
            ]
        )
        context = CommandContext(tool_registry=registry)
        router = CommandRouter()

        disabled = router.dispatch("/tools disable demo_tool", context)
        self.assertFalse(disabled.is_error)
        self.assertFalse(registry.is_enabled("demo_tool"))

        listed = router.dispatch("/tools", context)
        self.assertIn("demo_tool", listed.content)
        self.assertIn("disabled", listed.content)

        enabled = router.dispatch("/tools enable demo_tool", context)
        self.assertFalse(enabled.is_error)
        self.assertTrue(registry.is_enabled("demo_tool"))

    def test_each_registered_command_has_a_default_handler(self):
        router = CommandRouter()
        missing = [
            command.name for command in COMMAND_REGISTRY if command.name not in router.handlers
        ]

        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
