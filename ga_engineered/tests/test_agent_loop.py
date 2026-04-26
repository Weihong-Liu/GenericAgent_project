import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generic_agent_engineered.runtime.agent_loop import (
    AgentLoop,
    AgentLoopConfig,
    FunctionToolExecutor,
)
from generic_agent_engineered.runtime.compaction import CompactionConfig
from generic_agent_engineered.runtime.events import RuntimeEvent
from generic_agent_engineered.runtime.messages import ChatResponse, Message, ToolCall, ToolResult
from generic_agent_engineered.runtime.token_budget import TokenBudget


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.seen_messages = []

    async def stream_chat(self, messages, tools=None):
        self.calls += 1
        self.seen_messages.append(list(messages))
        response = self.responses.pop(0)
        if response.content:
            yield RuntimeEvent.content_delta(response.content)
        for tool_call in response.tool_calls:
            yield RuntimeEvent.from_tool_call(tool_call)
        yield RuntimeEvent.message_done(response)


class AgentLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_text_response_completes(self):
        provider = FakeProvider([ChatResponse(content="done")])
        loop = AgentLoop(provider)

        result = await loop.run([Message.user("hello")])

        self.assertTrue(result.completed)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.final_message.content, "done")
        self.assertEqual([message.role for message in result.messages], ["user", "assistant"])
        self.assertIn("turn_started", [event.kind for event in result.events])
        self.assertIn("turn_finished", [event.kind for event in result.events])

    async def test_single_tool_call_then_final_response(self):
        tool_call = ToolCall(
            id="call_1",
            name="weather",
            arguments={"city": "Shanghai"},
        )
        provider = FakeProvider(
            [
                ChatResponse(tool_calls=(tool_call,)),
                ChatResponse(content="sunny"),
            ]
        )
        executor = FunctionToolExecutor(
            {"weather": lambda call: ToolResult(tool_use_id=call.id, content="24C")}
        )
        loop = AgentLoop(provider, tool_executor=executor)

        result = await loop.run([Message.user("weather")])

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.final_message.content, "sunny")
        self.assertEqual(
            [message.role for message in result.messages],
            ["user", "assistant", "tool", "assistant"],
        )
        self.assertEqual(result.messages[2].tool_result.tool_use_id, "call_1")
        self.assertEqual(provider.seen_messages[1][2].content, "24C")
        self.assertIn("tool_result", [event.kind for event in result.events])

    async def test_max_turns_exceeded_sets_retry_reason(self):
        tool_call = ToolCall(id="call_1", name="weather", arguments={})
        provider = FakeProvider([ChatResponse(tool_calls=(tool_call,))])
        loop = AgentLoop(
            provider,
            tool_executor=FunctionToolExecutor({"weather": lambda call: "ok"}),
            config=AgentLoopConfig(max_turns=1),
        )

        result = await loop.run([Message.user("loop")])

        self.assertEqual(result.status, "max_turns_exceeded")
        self.assertEqual(result.retry_reason, "max_turns_exceeded")
        self.assertIsNone(result.final_message)
        self.assertEqual(result.turns, 1)
        self.assertEqual(result.events[-1].kind, "loop_stopped")

    async def test_stop_signal_exits_before_provider_call(self):
        provider = FakeProvider([ChatResponse(content="should not run")])
        loop = AgentLoop(provider, stop_signal=lambda: True)

        result = await loop.run([Message.user("stop")])

        self.assertEqual(result.status, "stopped")
        self.assertEqual(result.retry_reason, "stop_signal")
        self.assertEqual(provider.calls, 0)
        self.assertEqual(result.messages, (Message.user("stop"),))

    async def test_token_budget_compacts_before_provider_call(self):
        provider = FakeProvider([ChatResponse(content="done")])
        loop = AgentLoop(
            provider,
            config=AgentLoopConfig(
                token_budget=TokenBudget(max_tokens=120, trigger_ratio=0.5),
                compaction=CompactionConfig(keep_recent_turns=1, max_summary_chars=600),
            ),
        )
        messages = [
            Message.system("system rules"),
            Message.user("old context " * 80),
            Message.assistant("old answer " * 80),
            Message.user("recent request"),
        ]

        result = await loop.run(messages)

        self.assertEqual(result.status, "completed")
        self.assertEqual(provider.seen_messages[0][0], messages[0])
        self.assertTrue(provider.seen_messages[0][1].metadata["compaction"])
        self.assertEqual(provider.seen_messages[0][-1], messages[-1])


if __name__ == "__main__":
    unittest.main()
