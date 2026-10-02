from __future__ import annotations

import unittest

from helpers import make_project, write
import links


class LinksTest(unittest.TestCase):
    def test_epic_and_plan_links(self):
        project = make_project()
        write(project, "specs/001-x/spec.md", "**Jira Epic:** IRIS-40\n")
        write(project, "specs/001-x/tasks.md", "- [ ] T1 a\n  - jira: IRIS-41\n")
        write(project, "wow/pb/epic-E1.md", "x")
        write(project, "wow/plan/PLAN.md", "x")
        state = {"plan": {"id": "p"}, "epics": [{"id": "E1", "jira": "IRIS-40", "jira_url": "https://j/IRIS-40"},
                                                {"id": "E2", "jira": None, "jira_url": None}]}
        prs = [{"number": 7, "title": "IRIS-41 x", "branch": "b"}, {"number": 9, "title": "other", "branch": "c"}]
        out = links.build_links(project, state, prs)
        e1 = out["epics"][0]["links"]
        self.assertEqual(e1["jira"], "https://j/IRIS-40")
        self.assertEqual([p["number"] for p in e1["prs"]], [7])
        self.assertEqual(e1["files"], ["specs/001-x/spec.md", "specs/001-x/tasks.md", "wow/pb/epic-E1.md"])
        self.assertEqual(out["epics"][1]["links"], {"jira": None, "prs": [], "files": []})
        self.assertEqual(out["plan"]["links"], {"files": ["wow/plan/PLAN.md"]})
        self.assertNotIn("links", state["plan"])


if __name__ == "__main__":
    unittest.main()
