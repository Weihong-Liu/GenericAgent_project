import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generic_agent_engineered.compat import (
    LEGACY_TOOL_MIGRATIONS,
    legacy_tool_names,
    run_reflect_once,
    run_task_io,
)
from generic_agent_engineered.runtime.agent_loop import AgentLoop, AgentLoopConfig
from generic_agent_engineered.runtime.events import RuntimeEvent
from generic_agent_engineered.runtime.messages import ChatResponse, Message, ToolCall
from generic_agent_engineered.tools import CodeRunTool, FileReadTool, ToolRegistry


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.seen_messages = []

    async def stream_chat(self, messages, tools=None):
        self.seen_messages.append(list(messages))
        response = self.responses.pop(0)
        if response.content:
            yield RuntimeEvent.content_delta(response.content)
        for tool_call in response.tool_calls:
            yield RuntimeEvent.from_tool_call(tool_call)
        yield RuntimeEvent.message_done(response)


def _registry(workspace: Path) -> ToolRegistry:
    return ToolRegistry([FileReadTool(workspace), CodeRunTool(workspace)])


class LegacyAgentBehaviorTests(unittest.IsolatedAsyncioTestCase):
    async def test_compat_fixture_no_tool_final_response(self):
        provider = FakeProvider([ChatResponse(content="legacy final response")])
        loop = AgentLoop(provider, config=AgentLoopConfig(max_turns=3))

        result = await loop.run([Message.user("hello from old REPL")])

        self.assertTrue(result.completed)
        self.assertEqual(result.final_message.content, "legacy final response")
        self.assertEqual([message.role for message in result.messages], ["user", "assistant"])

    async def test_compat_fixture_file_read_tool_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "fixture.txt").write_text("alpha\nneedle\nomega\n", encoding="utf-8")
            tool_call = ToolCall(
                id="call_read",
                name="file_read",
                arguments={"path": "fixture.txt", "keyword": "needle", "show_linenos": False},
            )
            provider = FakeProvider(
                [
                    ChatResponse(tool_calls=(tool_call,)),
                    ChatResponse(content="read complete"),
                ]
            )
            registry = _registry(workspace)
            loop = AgentLoop(
                provider,
                tool_executor=registry,
                tools=registry.schemas(),
                config=AgentLoopConfig(max_turns=3),
            )

            result = await loop.run([Message.user("read fixture.txt")])

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.final_message.content, "read complete")
        self.assertEqual(result.messages[2].role, "tool")
        self.assertIn("needle", result.messages[2].content)
        self.assertEqual(provider.seen_messages[1][2].tool_result.tool_use_id, "call_read")

    async def test_compat_fixture_code_run_tool_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            tool_call = ToolCall(
                id="call_code",
                name="code_run",
                arguments={"script": "print('legacy code ok')"},
            )
            provider = FakeProvider(
                [
                    ChatResponse(tool_calls=(tool_call,)),
                    ChatResponse(content="code complete"),
                ]
            )
            registry = _registry(workspace)
            loop = AgentLoop(
                provider,
                tool_executor=registry,
                tools=registry.schemas(),
                config=AgentLoopConfig(max_turns=3),
            )

            result = await loop.run([Message.user("run code")])

        self.assertEqual(result.status, "completed")
        self.assertIn("legacy code ok", result.messages[2].content)
        self.assertFalse(result.messages[2].tool_result.is_error)


class LegacyMigrationCoverageTests(unittest.TestCase):
    def test_legacy_tool_mapping_covers_generic_agent_schema(self):
        schema_path = (
            Path(__file__).resolve().parents[3] / "GenericAgent" / "assets" / "tools_schema.json"
        )
        if not schema_path.exists():
            self.skipTest("legacy GenericAgent tools_schema.json is not available")

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        legacy_names = {tool["function"]["name"] for tool in schema}

        self.assertEqual(legacy_names, set(legacy_tool_names()))
        for migration in LEGACY_TOOL_MIGRATIONS.values():
            self.assertIn(migration.status, {"implemented", "planned", "deprecated"})
            self.assertTrue(migration.replacement)

    def test_legacy_task_io_compatibility_writes_round_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_task_io(
                Path(tmp) / "task",
                input_text="legacy prompt",
                handler=lambda prompt: f"handled: {prompt}",
            )

            output = result.output_path.read_text(encoding="utf-8")

        self.assertEqual(result.prompt, "legacy prompt")
        self.assertEqual(result.output, "handled: legacy prompt")
        self.assertIn("[ROUND END]", output)

    def test_legacy_reflect_once_runs_check_and_on_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            done_path = root / "done.txt"
            script = root / "reflect_script.py"
            script.write_text(
                "\n".join(
                    [
                        f"DONE_PATH = {str(done_path)!r}",
                        "def check():",
                        "    return 'reflect prompt'",
                        "def on_done(result):",
                        "    with open(DONE_PATH, 'w', encoding='utf-8') as handle:",
                        "        handle.write(result)",
                    ]
                ),
                encoding="utf-8",
            )

            result = run_reflect_once(
                script,
                handler=lambda prompt: f"handled: {prompt}",
                log_dir=root / "logs",
            )

            self.assertTrue(result.triggered)
            self.assertEqual(result.prompt, "reflect prompt")
            self.assertEqual(done_path.read_text(encoding="utf-8"), "handled: reflect prompt")
            assert result.log_path is not None
            self.assertIn(
                "handled: reflect prompt",
                result.log_path.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
