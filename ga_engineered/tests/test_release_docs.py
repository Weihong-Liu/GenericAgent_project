import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


class ReleaseDocsTests(unittest.TestCase):
    def test_release_task_is_complete_and_deliverables_exist(self):
        payload = json.loads((ROOT / "tasks.json").read_text(encoding="utf-8"))
        tasks = {task["id"]: task for task in payload["tasks"]}
        milestones = {milestone["id"]: milestone for milestone in payload["milestones"]}

        self.assertEqual(tasks["GAE-022"]["status"], "done")
        completed_milestones = {
            milestone_id
            for milestone_id, milestone in milestones.items()
            if milestone["status"] == "done"
        }
        self.assertTrue(
            all(
                task["status"] == "done"
                for task in tasks.values()
                if task["milestone"] in completed_milestones
            )
        )

        for relative in tasks["GAE-022"]["deliverables"]:
            self.assertTrue((ROOT / relative).exists(), relative)

    def test_tui_redesign_plan_is_tracked(self):
        payload = json.loads((ROOT / "tasks.json").read_text(encoding="utf-8"))
        tasks = {task["id"]: task for task in payload["tasks"]}
        milestones = {milestone["id"]: milestone for milestone in payload["milestones"]}

        self.assertEqual(tasks["GAE-023"]["status"], "done")
        self.assertTrue(tasks["GAE-024"]["status"].startswith("superseded"))
        self.assertEqual(milestones["M7"]["status"], "superseded")
        self.assertEqual(milestones["M8"]["status"], "superseded")
        self.assertIn(milestones["M9"]["status"], {"in_progress", "done"})
        self.assertEqual(tasks["GAE-031"]["milestone"], "M9")
        self.assertTrue((ROOT / "tasks" / "TUI_REDESIGN_PLAN.md").exists())
        self.assertTrue((ROOT / "tasks" / "TUI_TS_PROTOCOL.md").exists())

    def test_release_checklist_links_are_valid(self):
        checklist = ROOT / "docs" / "RELEASE_CHECKLIST.md"
        content = checklist.read_text(encoding="utf-8")

        self.assertIn("## Required Gates", content)
        self.assertIn("## Remaining Risks", content)
        self.assertIn("python3 -m unittest discover -s tests", content)
        self.assertIn("uv run --no-sync pytest", content)

        for target in LINK_RE.findall(content):
            if target.startswith(("http://", "https://", "#")):
                continue
            path = (checklist.parent / target.split("#", 1)[0]).resolve()
            self.assertTrue(path.exists(), target)

    def test_changelog_and_task_report_cover_release(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        report = (ROOT / "tasks" / "TASK_REPORT.md").read_text(encoding="utf-8")

        self.assertIn("## 0.1.0", changelog)
        self.assertIn("GAE-022", report)
        self.assertIn("Remaining Risks", (ROOT / "docs" / "RELEASE_CHECKLIST.md").read_text())


if __name__ == "__main__":
    unittest.main()
