import contextlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generic_agent_engineered.runtime.messages import Message, ToolCall, ToolResult
from generic_agent_engineered.state import SessionStore


class SessionStoreTests(unittest.TestCase):
    def test_create_session_initializes_wal_and_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp) / "sessions.sqlite")
            session = store.create_session(
                "session-1",
                title="First",
                provider_id="openai",
                model="gpt-5.4",
                metadata={"source": "test"},
            )

            self.assertEqual(session.id, "session-1")
            self.assertEqual(session.metadata["source"], "test")

            with contextlib.closing(store.connect()) as connection:
                journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
                tables = {
                    row["name"]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
                    ).fetchall()
                }

        self.assertEqual(journal_mode, "wal")
        self.assertIn("sessions", tables)
        self.assertIn("messages", tables)
        self.assertIn("messages_fts", tables)

    def test_append_and_load_messages_round_trip_runtime_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp) / "sessions.sqlite")
            store.create_session("session-1")
            first = Message(role="user", content="read the file", metadata={"turn": 1})
            second = Message.assistant(
                "calling tool",
                tool_calls=[ToolCall("call-1", "file_read", {"path": "README.md"})],
            )
            third = Message.tool(ToolResult("call-1", "file content", metadata={"ok": True}))

            stored_first = store.append_message("session-1", first)
            stored_second = store.append_message("session-1", second)
            stored_third = store.append_message("session-1", third)
            loaded = store.load_messages("session-1")

        self.assertEqual(
            [stored_first.sequence, stored_second.sequence, stored_third.sequence],
            [0, 1, 2],
        )
        self.assertEqual(
            [message.to_dict() for message in loaded],
            [first.to_dict(), second.to_dict(), third.to_dict()],
        )

    def test_search_messages_uses_fts_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp) / "sessions.sqlite")
            store.create_session("session-1")
            store.create_session("session-2")
            store.append_message("session-1", Message.user("alpha needle in session one"))
            store.append_message("session-2", Message.user("alpha needle in session two"))
            store.append_message("session-2", Message.assistant("unrelated"))

            all_results = store.search_messages("needle")
            scoped_results = store.search_messages("needle", session_id="session-2")

        self.assertEqual({result.session_id for result in all_results}, {"session-1", "session-2"})
        self.assertEqual([result.session_id for result in scoped_results], ["session-2"])
        self.assertEqual(scoped_results[0].role, "user")

    def test_branch_session_records_parent_and_can_copy_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp) / "sessions.sqlite")
            parent = store.create_session(
                "parent",
                title="Original",
                provider_id="anthropic",
                model="claude-test",
            )
            store.append_message(parent.id, Message.user("keep this context"))

            child = store.branch_session(
                parent.id,
                "child",
                metadata={"reason": "what-if"},
                copy_messages=True,
            )
            child_record = store.get_session("child")
            child_messages = store.load_messages("child")

        self.assertEqual(child.parent_session_id, "parent")
        self.assertIsNotNone(child_record)
        self.assertEqual(child_record.provider_id, "anthropic")
        self.assertEqual(child_record.model, "claude-test")
        self.assertEqual(child_record.metadata["reason"], "what-if")
        self.assertEqual([message.content for message in child_messages], ["keep this context"])

    def test_branch_unknown_parent_fails_clearly(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp) / "sessions.sqlite")

            with self.assertRaises(KeyError):
                store.branch_session("missing-parent")


if __name__ == "__main__":
    unittest.main()
