import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generic_agent_engineered.chat import ChatTurnService
from generic_agent_engineered.config import RuntimeSettings
from generic_agent_engineered.engine import AgentRuntime
from generic_agent_engineered.runtime.events import RuntimeEvent
from generic_agent_engineered.runtime.messages import ChatResponse, ToolCall
from generic_agent_engineered.tools import FunctionTool, ToolRegistry, ToolSchema, ToolSpec


class FakeProvider:
    def __init__(self, content: str) -> None:
        self.content = content
        self.seen_prompts: list[str] = []
        self.seen_tools: list[list[str]] = []

    async def stream_chat(self, messages, tools=None):
        self.seen_prompts = [message.content for message in messages if message.role == "user"]
        self.seen_tools.append([tool["name"] for tool in tools or []])
        yield RuntimeEvent.message_done(ChatResponse(content=self.content))


class ToolCallingProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.seen_tools: list[list[str]] = []

    async def stream_chat(self, messages, tools=None):
        self.calls += 1
        self.seen_tools.append([tool["name"] for tool in tools or []])
        if self.calls == 1:
            yield RuntimeEvent.message_done(
                ChatResponse(
                    tool_calls=(
                        ToolCall(
                            id="tool-1",
                            name="echo_tool",
                            arguments={"value": "天气"},
                        ),
                    )
                )
            )
            return
        yield RuntimeEvent.message_done(ChatResponse(content="工具已调用。"))


def _echo_tool() -> FunctionTool:
    return FunctionTool(
        spec=ToolSpec(
            schema=ToolSchema(
                name="echo_tool",
                description="Echo test input.",
                parameters={
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                },
            )
        ),
        handler=lambda call: f"echo={call.arguments['value']}",
    )


class ChatTurnServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_turn_updates_runtime_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = AgentRuntime(RuntimeSettings(home=Path(tmp)))
            provider = FakeProvider("你好，我是 GenericAgent。")
            service = ChatTurnService(runtime, provider=provider)

            result = await service.run_turn("你好")

        self.assertFalse(result.is_error)
        self.assertEqual(result.content, "你好，我是 GenericAgent。")
        self.assertEqual(runtime.state.turn_count, 1)
        self.assertEqual(runtime.state.messages[0].role, "user")
        self.assertEqual(runtime.state.messages[1].role, "assistant")
        self.assertEqual(provider.seen_prompts, ["你好"])

    async def test_run_turn_sends_default_tool_schemas_to_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = AgentRuntime(RuntimeSettings(home=Path(tmp)))
            provider = FakeProvider("ok")
            service = ChatTurnService(runtime, provider=provider)

            await service.run_turn("打开浏览器搜索天气")

        names = set(provider.seen_tools[0])
        self.assertIn("web_open", names)
        self.assertIn("web_scan", names)
        self.assertIn("web_execute_js", names)

    async def test_run_turn_executes_tool_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = AgentRuntime(RuntimeSettings(home=Path(tmp)))
            provider = ToolCallingProvider()
            registry = ToolRegistry([_echo_tool()])
            service = ChatTurnService(runtime, provider=provider, tool_registry=registry)

            result = await service.run_turn("用工具")

        self.assertFalse(result.is_error)
        self.assertEqual(result.content, "工具已调用。")
        self.assertEqual(provider.calls, 2)
        self.assertEqual(provider.seen_tools, [["echo_tool"], ["echo_tool"]])
        self.assertTrue(any(event.kind == "tool_result" for event in result.events))

    async def test_missing_api_key_returns_auth_error_without_mutating_history(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            runtime = AgentRuntime(RuntimeSettings(home=Path(tmp)))
            service = ChatTurnService(runtime)

            result = await service.run_turn("hello")

        self.assertTrue(result.is_error)
        self.assertEqual(result.error_type, "ProviderAuthError")
        self.assertIn("OPENAI_API_KEY", result.content)
        self.assertEqual(runtime.state.turn_count, 0)
        self.assertEqual(runtime.state.messages, [])


if __name__ == "__main__":
    unittest.main()
