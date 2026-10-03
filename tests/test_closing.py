"""wow close: what neither Product Brain nor Spec-Kit closes (subtasks and the epic), after the human approval."""
from __future__ import annotations

import json
import os
import unittest
from unittest import mock

from helpers import make_project, run_cli, write
import closing
import manifest
from sources import SourceUnavailable
from sources.jira import JiraClient
from test_jira import CREDS, FakeResponse
from test_manifest import valid_doc

SPEC = "# Spec\n**Jira Epic:** [IRIS-40](https://acme.atlassian.net/browse/IRIS-40)\n"
TASKS_DONE = "- [x] T001 [US1] model\n  - jira: IRIS-41\n- [x] T002 [US1] api\n  - jira: IRIS-41\n"


def _project(tasks: str = TASKS_DONE, review: str = "approved_by_human"):
    project = make_project()
    doc = valid_doc()
    doc["plan"]["export"]["epics"] = {"E1": "IRIS-40"}
    manifest.save(project, doc)
    write(project, "specs/001-x/spec.md", SPEC)
    write(project, "specs/001-x/tasks.md", tasks)
    if review:
        write(project, "wow/reviews/E1.json", json.dumps({"ref": "E1", "final": review, "rounds": []}))
    return project


class FakeJira:
    def __init__(self, issues):
        self.issues = issues
        self.closed = []

    def open_issues(self, epic_key):
        return self.issues

    def close(self, key):
        self.closed.append(key)
        return "Done"


ISSUES = [{"key": "IRIS-40", "level": "epic", "done": False},
          {"key": "IRIS-41", "level": "story", "done": True},
          {"key": "IRIS-42", "level": "subtask", "done": False},
          {"key": "IRIS-43", "level": "subtask", "done": True}]


class PlanTest(unittest.TestCase):
    def test_plan_lists_open_issues_subtasks_first_and_epic_last(self):
        result = closing.plan(_project(), "E1", FakeJira(ISSUES))
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["to_close"], ["IRIS-42", "IRIS-40"])

    def test_pending_tasks_and_missing_approval_block(self):
        result = closing.plan(_project(review="approved"), "E1", FakeJira(ISSUES))
        self.assertEqual(result["blockers"], [])  # a reviewer approval also closes the review
        result = closing.plan(_project(tasks="- [x] T001 a\n- [ ] T002 b\n", review=""), "E1", FakeJira(ISSUES))
        self.assertTrue(any("1/2" in b for b in result["blockers"]), result)
        self.assertTrue(any("wow review" in b for b in result["blockers"]), result)

    def test_unexported_epic_blocks(self):
        project = _project()
        doc = manifest.load(project)
        doc["plan"]["export"]["epics"] = {}
        manifest.save(project, doc)
        self.assertTrue(any("not exported" in b for b in closing.plan(project, "E1", FakeJira(ISSUES))["blockers"]))

    def test_apply_closes_in_order_and_stops_on_failure(self):
        jira = FakeJira(ISSUES)
        self.assertEqual(closing.apply(closing.plan(_project(), "E1", jira), jira), [])
        self.assertEqual(jira.closed, ["IRIS-42", "IRIS-40"])

        class Failing(FakeJira):
            def close(self, key):
                raise SourceUnavailable(f"jira: no done transition for {key}")
        failing = Failing(ISSUES)
        errors = closing.apply(closing.plan(_project(), "E1", failing), failing)
        self.assertEqual(errors, ["jira: no done transition for IRIS-42"])


class JiraClientTest(unittest.TestCase):
    def test_open_issues_reads_epic_stories_and_subtasks(self):
        def status(key, category):
            return {"key": key, "fields": {"status": {"statusCategory": {"key": category}}}}

        def opener(request, timeout):
            jql = json.loads(request.data.decode())["jql"]
            pages = {"key = IRIS-40": [status("IRIS-40", "indeterminate")],
                     "parent = IRIS-40": [status("IRIS-41", "done")],
                     "parent in (IRIS-41)": [status("IRIS-42", "new")]}
            return FakeResponse({"issues": pages[jql]})

        issues = JiraClient(CREDS, opener=opener).open_issues("IRIS-40")
        self.assertEqual(issues, [{"key": "IRIS-40", "level": "epic", "done": False},
                                  {"key": "IRIS-41", "level": "story", "done": True},
                                  {"key": "IRIS-42", "level": "subtask", "done": False}])

    def test_close_uses_the_transition_into_the_done_category(self):
        sent = []

        def opener(request, timeout):
            if request.get_method() == "GET":
                return FakeResponse({"transitions": [
                    {"id": "11", "to": {"name": "In Progress", "statusCategory": {"key": "indeterminate"}}},
                    {"id": "31", "to": {"name": "Done", "statusCategory": {"key": "done"}}}]})
            sent.append((request.full_url, json.loads(request.data.decode())))
            return FakeResponse({})

        self.assertEqual(JiraClient(CREDS, opener=opener).close("IRIS-42"), "Done")
        self.assertEqual(sent, [("https://acme.atlassian.net/rest/api/3/issue/IRIS-42/transitions",
                                 {"transition": {"id": "31"}})])

    def test_close_without_done_transition_is_unavailable(self):
        def opener(request, timeout):
            return FakeResponse({"transitions": []})
        with self.assertRaises(SourceUnavailable):
            JiraClient(CREDS, opener=opener).close("IRIS-42")


class CloseCommandTest(unittest.TestCase):
    def test_without_credentials_exits_2(self):
        project = _project()
        clean = {k: v for k, v in os.environ.items() if not k.startswith(("IC_JIRA_", "JIRA_"))}
        with mock.patch.dict(os.environ, clean, clear=True):
            code, _, err = run_cli(["close", "--epic", "E1", "--project", str(project)])
        self.assertEqual(code, 2)
        self.assertIn("Jira", err)


if __name__ == "__main__":
    unittest.main()
