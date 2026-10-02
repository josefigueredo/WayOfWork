from __future__ import annotations

import unittest

from helpers import make_project, write
import config
import sk

TASKS = ("## Phase 1: Setup\n- [x] T001 scaffold\n"
         "## Phase 3: Story 1\n- [ ] T010 model\n  - jira: IRIS-41\n- [ ] T011 orphan without key\n")


class CommandsTest(unittest.TestCase):
    def test_sync_uses_generate_model(self):
        [line] = sk.commands_for("sync", config.DEFAULTS, epic="IRIS-40")
        self.assertEqual(line, "cursor-agent -p '/spec-kit.sync --epic-key IRIS-40' --model composer-2.5 "
                               "--trust --output-format json")

    def test_plan_points_to_draft_and_uses_reason_model(self):
        [line] = sk.commands_for("plan", config.DEFAULTS, feature="specs/001-curation")
        self.assertIn("wow/sk/001-curation/plan-draft.md", line)
        self.assertIn("--model claude-sonnet-5-5-high", line)

    def test_tasks_returns_two_lines(self):
        lines = sk.commands_for("tasks", config.DEFAULTS, feature="specs/001-curation")
        self.assertEqual(len(lines), 2)
        self.assertIn("/spec-kit.tasks.shape", lines[1])

    def test_missing_argument_and_unknown_step(self):
        with self.assertRaises(ValueError):
            sk.commands_for("sync", config.DEFAULTS)
        with self.assertRaises(ValueError):
            sk.commands_for("deploy", config.DEFAULTS, feature="x")


class StatusTest(unittest.TestCase):
    def test_orphans_only_in_sections_with_keys(self):
        self.assertEqual(sk.orphan_tasks(TASKS), 1)

    def test_status_counts_warnings_missing_and_orphans(self):
        project = make_project()
        write(project, ".spec-kit/import_report.md", "ok\n⚠ IRIS-43 has no acceptance criteria\nWarning: x\n")
        write(project, "specs/001-curation/spec.md", "**Jira Epic:** IRIS-40\n")
        write(project, "specs/001-curation/tasks.md", TASKS)
        write(project, "wow/sk/001-curation/plan-draft.md", "draft")
        result = sk.status(project)
        self.assertEqual(result["import_warnings"], 2)
        [feature] = result["features"]
        self.assertEqual(feature["orphan_tasks"], 1)
        self.assertEqual(feature["missing"], ["plan.md", "work-units.json", "wow/sk/001-curation/clarify-answers.md"])


if __name__ == "__main__":
    unittest.main()
