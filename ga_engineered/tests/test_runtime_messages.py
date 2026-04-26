import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generic_agent_engineered.runtime.events import RuntimeEvent
from generic_agent_engineered.runtime.messages import (
    ChatResponse,
    Message,
    ToolCall,
    ToolResult,
    deserialize_messages,
    pair_tool_results,
    serialize_messages,
)


class RuntimeMessageTests(unittest.TestCase):
    def test_message_serialization_round_trip(self):
        messages = [
            Message.system("system rules"),
            Message.user("run weather"),
            Message.assistant(
                "checking",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="weather",
                        arguments={"city": "Shanghai"},
                    )
                ],
            ),
            Message.tool(ToolResult(tool_use_id="call_1", content='{"temp": 24}')),
        ]

        payload = serialize_messages(messages)
        encoded = json.dumps(payload)
        restored = deserialize_messages(json.loads(encoded))

        self.assertEqual(restored, messages)
        self.assertNotIn("raw", payload[2])
        self.assertEqual(payload[3]["tool_result"]["tool_use_id"], "call_1")

    def test_tool_result_pairing(self):
        assistant = Message.assistant(
            tool_calls=[
                ToolCall(id="call_1", name="weather", arguments={}),
                ToolCall(id="call_2", name="time", arguments={}),
            ]
        )
        tool_messages = [
            Message.tool(ToolResult(tool_use_id="call_1", content="sunny")),
            Message.tool(ToolResult(tool_use_id="call_2", content="09:00")),
        ]

        paired = pair_tool_results(assistant, tool_messages)

        self.assertEqual(paired["call_1"].content, "sunny")
        self.assertEqual(paired["call_2"].content, "09:00")

    def test_tool_result_pairing_rejects_missing_or_unknown_results(self):
        assistant = Message.assistant(
            tool_calls=[ToolCall(id="call_1", name="weather", arguments={})]
        )

        with self.assertRaisesRegex(ValueError, "missing tool results"):
            pair_tool_results(assistant, [])
        with self.assertRaisesRegex(ValueError, "unmatched tool result"):
            pair_tool_results(
                assistant,
                [Message.tool(ToolResult(tool_use_id="missing", content="bad"))],
            )
        with self.assertRaisesRegex(ValueError, "duplicate tool result"):
            pair_tool_results(
                assistant,
                [
                    Message.tool(ToolResult(tool_use_id="call_1", content="first")),
                    Message.tool(ToolResult(tool_use_id="call_1", content="second")),
                ],
            )

    def test_invalid_role_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid message role"):
            Message.from_dict({"role": "developer", "content": "bad"})
        with self.assertRaisesRegex(TypeError, "tool_calls entries"):
            Message.from_dict(
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": ["not-an-object"],
                }
            )

    def test_role_specific_tool_shape_rejected(self):
        tool_call = ToolCall(id="call_1", name="weather", arguments={})
        with self.assertRaisesRegex(ValueError, "tool_calls"):
            Message(role="user", content="bad", tool_calls=[tool_call])
        with self.assertRaisesRegex(ValueError, "tool_result"):
            Message(role="tool", content="missing result")

    def test_runtime_event_serialization_round_trip(self):
        response = ChatResponse(
            content="done",
            tool_calls=(ToolCall(id="call_1", name="weather", arguments={}),),
        )
        event = RuntimeEvent.message_done(response)

        restored = RuntimeEvent.from_dict(event.to_dict())

        self.assertEqual(restored, event)

    def test_runtime_event_shape_validation(self):
        with self.assertRaisesRegex(ValueError, "require delta"):
            RuntimeEvent(kind="content_delta")
        with self.assertRaisesRegex(ValueError, "require tool_call"):
            RuntimeEvent(kind="tool_call")


if __name__ == "__main__":
    unittest.main()
