from __future__ import annotations

import unittest

from helpers import make_project, write
from sources import speckit

TASKS = (
    "## Phase 1: Setup\n"
    "- [x] T001 scaffold\n"
    "## Phase 3: Story 1\n"
    "- [x] T010 WU-001 model\n"
    "  - jira: IRIS-41\n"
    "- [ ] T011 WU-002 api\n"
    "\t- jira: IRIS-41\n"
    "- [x] T012 WU-003 ui\n"
    "  - jira: IRIS-42\n"
)


class ParseTasksTest(unittest.TestCase):
    def test_counts_and_story_mapping(self):
        parsed = speckit.parse_tasks(TASKS)
        self.assertEqual((parsed["total"], parsed["done"]), (4, 3))
        self.assertEqual(parsed["stories"], {"IRIS-41": {"total": 2, "done": 1}, "IRIS-42": {"total": 1, "done": 1}})

    def test_crlf_and_tabs(self):
        parsed = speckit.parse_tasks(TASKS.replace("\n", "\r\n"))
        self.assertEqual((parsed["total"], parsed["done"]), (4, 3))
        self.assertEqual(parsed["stories"]["IRIS-41"], {"total": 2, "done": 1})


class FeaturesTest(unittest.TestCase):
    def test_feature_with_epic_and_pending_wu(self):
        project = make_project()
        write(project, "specs/001-curation/spec.md", "# Spec\n**Jira Epic:** [IRIS-40](https://x/browse/IRIS-40)\n")
        write(project, "specs/001-curation/plan.md", "# Plan\n")
        write(project, "specs/001-curation/tasks.md", TASKS)
        write(project, "specs/001-curation/work-units.json",
              '{"work_units": [{"id": "WU-001"}, {"id": "WU-002"}, {"id": "WU-003"}]}')
        [feature] = speckit.features(project)
        self.assertEqual(feature["dir"], "specs/001-curation")
        self.assertEqual(feature["epic_key"], "IRIS-40")
        self.assertTrue(feature["has_plan"] and feature["has_tasks"] and feature["has_work_units"])
        self.assertEqual(feature["pending_work_units"], ["WU-002"])

    def test_work_units_fallback_and_no_epic(self):
        project = make_project()
        write(project, "specs/002-x/spec.md", "# Spec without epic\n")
        write(project, ".spec-kit/work-units.json", '[{"id": "WU-009"}]')
        [feature] = speckit.features(project)
        self.assertIsNone(feature["epic_key"])
        self.assertTrue(feature["has_work_units"])
        self.assertEqual(feature["pending_work_units"], ["WU-009"])

    def test_no_specs_dir(self):
        self.assertEqual(speckit.features(make_project()), [])

    def test_invalid_work_units_json(self):
        project = make_project()
        path = write(project, "w.json", "{bad")
        self.assertEqual(speckit.work_unit_ids(path), [])


if __name__ == "__main__":
    unittest.main()
