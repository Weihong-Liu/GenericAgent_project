import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generic_agent_engineered.runtime.messages import ToolCall
from generic_agent_engineered.tools import (
    FilePatchTool,
    FileReadTool,
    FileWriteTool,
    WorkspacePolicy,
    expand_file_references,
)


class FileToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes.txt").write_text("alpha\nbeta\ngamma\ndelta\n", encoding="utf-8")
            tool = FileReadTool(root)

            result = await tool.run(
                ToolCall(
                    id="call_1",
                    name="file_read",
                    arguments={"path": "notes.txt", "start": 2, "count": 2},
                )
            )

            self.assertFalse(result.is_error)
            self.assertIn("2|beta", result.content)
            self.assertIn("3|gamma", result.content)
            self.assertNotIn("1|alpha", result.content)
            self.assertEqual(result.metadata["returned_lines"], 2)

    async def test_keyword_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes.txt").write_text(
                "intro\ncontext\nTarget marker\nafter\n",
                encoding="utf-8",
            )
            tool = FileReadTool(root)

            result = await tool.run(
                ToolCall(
                    id="call_1",
                    name="file_read",
                    arguments={"path": "notes.txt", "keyword": "target", "count": 3},
                )
            )

            self.assertFalse(result.is_error)
            self.assertIn("2|context", result.content)
            self.assertIn("3|Target marker", result.content)
            self.assertIn("4|after", result.content)

    async def test_large_file_read_truncates_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "big.txt").write_text("x" * 50, encoding="utf-8")
            tool = FileReadTool(root, max_line_chars=10)

            result = await tool.run(
                ToolCall(
                    id="call_1",
                    name="file_read",
                    arguments={"path": "big.txt", "count": 1},
                )
            )

            self.assertFalse(result.is_error)
            self.assertTrue(result.metadata["truncated"])
            self.assertIn("[TRUNCATED]", result.content)

    async def test_patch_unique_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "app.py"
            target.write_text("print('old')\n", encoding="utf-8")
            tool = FilePatchTool(root)

            result = await tool.run(
                ToolCall(
                    id="call_1",
                    name="file_patch",
                    arguments={
                        "path": "app.py",
                        "old_content": "print('old')",
                        "new_content": "print('new')",
                    },
                )
            )

            self.assertFalse(result.is_error)
            self.assertEqual(target.read_text(encoding="utf-8"), "print('new')\n")

    async def test_patch_rejects_non_unique_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "app.py"
            target.write_text("same\nsame\n", encoding="utf-8")
            tool = FilePatchTool(root)

            result = await tool.run(
                ToolCall(
                    id="call_1",
                    name="file_patch",
                    arguments={
                        "path": "app.py",
                        "old_content": "same",
                        "new_content": "changed",
                    },
                )
            )

            self.assertTrue(result.is_error)
            self.assertIn("matched 2 times", result.content)
            self.assertEqual(target.read_text(encoding="utf-8"), "same\nsame\n")

    async def test_path_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "workspace"
            root.mkdir()
            outside = Path(tmp) / "outside.txt"
            outside.write_text("secret", encoding="utf-8")
            tool = FileReadTool(root)

            result = await tool.run(
                ToolCall(
                    id="call_1",
                    name="file_read",
                    arguments={"path": "../outside.txt"},
                )
            )

            self.assertTrue(result.is_error)
            self.assertIn("escapes workspace root", result.content)

    async def test_file_write_modes_and_file_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "source.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
            tool = FileWriteTool(root)

            result = await tool.run(
                ToolCall(
                    id="call_1",
                    name="file_write",
                    arguments={
                        "path": "out.txt",
                        "content": "start\n{{file:source.txt:2:3}}",
                    },
                )
            )

            self.assertFalse(result.is_error)
            self.assertEqual(
                (root / "out.txt").read_text(encoding="utf-8"),
                "start\ntwo\nthree\n",
            )

    def test_expand_file_references_uses_workspace_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "source.txt").write_text("a\nb\nc\n", encoding="utf-8")

            expanded = expand_file_references(
                "before\n{{file:source.txt:2:2}}after",
                WorkspacePolicy(root),
            )

            self.assertEqual(expanded, "before\nb\nafter")


if __name__ == "__main__":
    unittest.main()
