import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generic_agent_engineered.runtime.compaction import (
    CompactionConfig,
    compact_history,
    compact_history_if_needed,
)
from generic_agent_engineered.runtime.messages import Message, ToolCall, ToolResult
from generic_agent_engineered.runtime.token_budget import TokenBudget, estimate_messages_tokens


class HistoryCompactionTests(unittest.TestCase):
    def test_old_tool_blocks_compressed(self):
        long_tool_content = "weather-data " * 120
        messages = [
            Message.system("system rules"),
            Message.user("check old weather"),
            Message.assistant(
                tool_calls=[
                    ToolCall(id="call_1", name="weather", arguments={"city": "Shanghai"})
                ]
            ),
            Message.tool(ToolResult(tool_use_id="call_1", content=long_tool_content)),
            Message.user("recent question"),
            Message.assistant("recent answer"),
        ]

        result = compact_history(
            messages,
            config=CompactionConfig(keep_recent_turns=1, max_summary_chars=900, max_item_chars=80),
            reason="unit_test",
        )

        self.assertTrue(result.changed)
        self.assertEqual(result.messages[0], messages[0])
        self.assertEqual(result.messages[-2:], tuple(messages[-2:]))
        self.assertIsNotNone(result.summary)
        summary_message = result.messages[1]
        self.assertEqual(summary_message.role, "system")
        self.assertTrue(summary_message.metadata["compaction"])
        self.assertIn("tool result call_1", summary_message.content)
        self.assertNotIn(long_tool_content, summary_message.content)
        self.assertLess(result.summary.compacted_tokens, result.summary.original_tokens)

    def test_recent_turns_preserved(self):
        messages = [
            Message.system("system rules"),
            Message.user("old user"),
            Message.assistant("old assistant"),
            Message.user("recent user 1"),
            Message.assistant("recent assistant 1"),
            Message.user("recent user 2"),
            Message.assistant("recent assistant 2"),
        ]

        result = compact_history(
            messages,
            config=CompactionConfig(keep_recent_turns=2, max_summary_chars=600),
        )

        self.assertTrue(result.changed)
        self.assertEqual(result.messages[0], messages[0])
        self.assertEqual(result.messages[2:], tuple(messages[3:]))

    def test_budget_threshold_triggers(self):
        messages = [
            Message.system("system rules"),
            Message.user("old context " * 80),
            Message.assistant("old answer " * 80),
            Message.user("recent user"),
            Message.assistant("recent assistant"),
        ]
        low_budget = TokenBudget(max_tokens=120, trigger_ratio=0.5)
        high_budget = TokenBudget(max_tokens=4000)

        compacted = compact_history_if_needed(
            messages,
            budget=low_budget,
            config=CompactionConfig(keep_recent_turns=1, max_summary_chars=600),
        )
        unchanged = compact_history_if_needed(
            messages,
            budget=high_budget,
            config=CompactionConfig(keep_recent_turns=1, max_summary_chars=600),
        )

        self.assertTrue(compacted.changed)
        self.assertTrue(compacted.budget_report.over_budget)
        self.assertLess(
            estimate_messages_tokens(compacted.messages),
            estimate_messages_tokens(messages),
        )
        self.assertFalse(unchanged.changed)
        self.assertEqual(unchanged.messages, tuple(messages))


if __name__ == "__main__":
    unittest.main()
