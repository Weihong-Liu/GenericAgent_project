import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generic_agent_engineered.memory import (
    MemoryEntry,
    MemoryIndex,
    MemoryService,
    MemoryWriteRequest,
    classify_memory_path,
    load_legacy_memory,
)
from generic_agent_engineered.skills import SkillCrystallizer, StructuredTaskSummary


class MemoryIndexTests(unittest.TestCase):
    def test_classifies_memory_layers(self):
        self.assertEqual(classify_memory_path(Path("memory/global_mem_insight.txt")), "L1")
        self.assertEqual(classify_memory_path(Path("memory/global_mem.txt")), "L2")
        self.assertEqual(classify_memory_path(Path("memory/github_contribution_sop.md")), "L3")
        self.assertEqual(classify_memory_path(Path("memory/L4_raw_sessions/raw.md")), "L4")

    def test_loads_legacy_generic_agent_memory_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "GenericAgent"
            memory_root = root / "memory"
            (memory_root / "L4_raw_sessions").mkdir(parents=True)
            (memory_root / "global_mem_insight.txt").write_text("# L1 Index\n", encoding="utf-8")
            (memory_root / "global_mem.txt").write_text("# L2 Facts\n", encoding="utf-8")
            (memory_root / "tmwebdriver_sop.md").write_text(
                "# TMWebDriver SOP\nUse CDP for upload automation.\n",
                encoding="utf-8",
            )
            (memory_root / "L4_raw_sessions" / "session.md").write_text(
                "raw session transcript",
                encoding="utf-8",
            )

            index = load_legacy_memory(root)

        self.assertEqual(index.layer_counts(), {"L1": 1, "L2": 1, "L3": 1, "L4": 1})
        results = index.search("TMWebDriver CDP", layer="L3")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "TMWebDriver SOP")

    def test_loads_l1_template_when_legacy_index_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "GenericAgent"
            (root / "assets").mkdir(parents=True)
            (root / "memory").mkdir(parents=True)
            (root / "assets" / "global_mem_insight_template.txt").write_text(
                "# [Global Memory Insight]\n",
                encoding="utf-8",
            )

            index = load_legacy_memory(root)
            index_from_memory_dir = load_legacy_memory(root / "memory")

        self.assertEqual(index.layer_counts()["L1"], 1)
        self.assertEqual(
            index.by_layer("L1")[0].relative_path,
            "assets/global_mem_insight_template.txt",
        )
        self.assertEqual(index_from_memory_dir.layer_counts()["L1"], 1)
        self.assertEqual(
            index_from_memory_dir.by_layer("L1")[0].relative_path,
            "assets/global_mem_insight_template.txt",
        )


class MemoryServiceTests(unittest.TestCase):
    def test_reviewed_write_gate_requires_approval_and_reviewer(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = MemoryService(Path(tmp) / "memory")
            request = MemoryWriteRequest(
                layer="L3",
                title="Browser Upload SOP",
                content="Use CDP file input assignment.",
                tags=("browser", "sop"),
            )

            with self.assertRaises(PermissionError):
                service.write_reviewed_entry(request)

            result = service.write_reviewed_entry(
                MemoryWriteRequest(
                    layer="L3",
                    title="Browser Upload SOP",
                    content="Use CDP file input assignment.",
                    tags=("browser", "sop"),
                    approved=True,
                    reviewer="alice",
                    source="unit-test",
                )
            )
            written_content = result.path.read_text(encoding="utf-8")

            self.assertTrue(result.created)
            self.assertEqual(result.entry.metadata["reviewer"], "alice")
            self.assertEqual(result.entry.metadata["source"], "unit-test")
            self.assertEqual(result.entry.relative_path, "browser-upload.md")
            self.assertIn("# Browser Upload SOP", written_content)

    def test_reviewed_l2_write_appends_to_global_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_root = Path(tmp) / "memory"
            service = MemoryService(memory_root)
            request = MemoryWriteRequest(
                layer="L2",
                title="Provider routing",
                content="Prefer registry lookup over hard-coded branches.",
                approved=True,
                reviewer="alice",
            )

            service.write_reviewed_entry(request)
            service.write_reviewed_entry(request)

            content = (memory_root / "global_mem.txt").read_text(encoding="utf-8")

        self.assertEqual(content.count("## Provider routing"), 2)


class SkillCrystallizerTests(unittest.TestCase):
    def test_successful_task_generates_sop_draft(self):
        summary = StructuredTaskSummary(
            title="Browser upload",
            objective="Upload a local file through browser automation.",
            outcome="The CDP-backed file assignment was verified.",
            successful=True,
            steps=("Locate the input element", "Assign the file through CDP"),
            tools=("browser.query_selector", "browser.set_input_files"),
            pitfalls=("Do not rely on visible upload buttons alone",),
            verification=("The uploaded filename appears in the page",),
            artifacts=("tasks/upload-sop.md",),
            tags=("browser",),
        )

        draft = SkillCrystallizer().generate_sop_draft(summary)
        request = draft.to_memory_request(approved=True, reviewer="alice")

        self.assertEqual(draft.title, "Browser upload SOP")
        self.assertEqual(draft.slug, "browser-upload")
        self.assertIn("## Steps", draft.content)
        self.assertIn("- browser.set_input_files", draft.content)
        self.assertEqual(request.layer, "L3")
        self.assertTrue(request.approved)

    def test_unsuccessful_task_cannot_generate_sop_draft(self):
        summary = StructuredTaskSummary(
            title="Failed migration",
            objective="Migrate a memory entry.",
            outcome="The run failed.",
            successful=False,
        )

        with self.assertRaises(ValueError):
            SkillCrystallizer().generate_sop_draft(summary)

    def test_detects_duplicate_skill_from_title_and_similarity(self):
        title_duplicate = MemoryEntry(
            layer="L3",
            title="Browser upload SOP",
            content="# Browser upload SOP\nUse CDP file input assignment.",
            relative_path="browser-upload.md",
        )
        similar_existing = MemoryEntry(
            layer="L3",
            title="Shell permissions",
            content="# Shell permissions SOP\nCheck sandbox before running shell commands.",
            relative_path="shell-permissions.md",
        )
        index = MemoryIndex([title_duplicate, similar_existing])
        crystallizer = SkillCrystallizer()
        draft = crystallizer.generate_sop_draft(
            StructuredTaskSummary(
                title="Browser upload",
                objective="Upload files through browser automation.",
                outcome="CDP assignment worked.",
                successful=True,
            )
        )

        duplicate = crystallizer.find_duplicate(draft, index)

        self.assertIsNotNone(duplicate)
        assert duplicate is not None
        self.assertEqual(duplicate.reason, "title")
        self.assertEqual(duplicate.entry.relative_path, "browser-upload.md")

        similarity_draft = crystallizer.generate_sop_draft(
            StructuredTaskSummary(
                title="Shell permission checks",
                objective="Check sandbox before running shell commands.",
                outcome="The command was allowed.",
                successful=True,
                steps=("Check sandbox before running shell commands",),
            )
        )
        similarity_duplicate = SkillCrystallizer(duplicate_threshold=0.25).find_duplicate(
            similarity_draft,
            index,
        )

        self.assertIsNotNone(similarity_duplicate)
        assert similarity_duplicate is not None
        self.assertEqual(similarity_duplicate.reason, "similarity")


if __name__ == "__main__":
    unittest.main()
