"""Every write WoW makes to Jira is kept in harness/jira-writes.jsonl.

When the same Jira token is shared by several tools and by hand, Jira's changelog cannot tell them apart: in the IRIS
pilot every story got an assignee at 23:38 and nothing could say who did it. A log of WoW's own successful writes
at least lets a change be ruled in or out as WoW's.
"""
from __future__ import annotations

import json
import unittest
import urllib.error

from helpers import make_project
import jiralog
from sources import SourceUnavailable
from sources.jira import JiraClient
from test_jira import CREDS, FakeResponse


class ClientJournalTest(unittest.TestCase):
    def test_a_successful_update_is_journaled_and_a_rejected_one_is_not(self):
        seen = []
        client = JiraClient(CREDS, opener=lambda request, timeout: FakeResponse({}), journal=seen.append)
        client.update("IRIS-41", {"priority": {"name": "High"}, "labels": ["ci"]})
        self.assertEqual(seen, [{"action": "update", "key": "IRIS-41",
                                 "fields": {"priority": {"name": "High"}, "labels": ["ci"]}}])

        def rejecting(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 400, "Bad Request", {}, None)

        seen.clear()
        with self.assertRaises(SourceUnavailable):
            JiraClient(CREDS, opener=rejecting, journal=seen.append).update("IRIS-41", {"labels": []})
        self.assertEqual(seen, [])

    def test_a_done_transition_is_journaled(self):
        seen = []

        def opener(request, timeout):
            if request.get_method() == "GET":
                return FakeResponse({"transitions": [{"id": "31", "to": {"name": "Done",
                                                                           "statusCategory": {"key": "done"}}}]})
            return FakeResponse({})

        JiraClient(CREDS, opener=opener, journal=seen.append).close("IRIS-42")
        self.assertEqual(seen, [{"action": "transition", "key": "IRIS-42", "to": "Done"}])

    def test_reads_are_never_journaled(self):
        seen = []
        client = JiraClient(CREDS, opener=lambda r, timeout: FakeResponse({"issues": []}), journal=seen.append)
        client._search("project = IRIS")
        self.assertEqual(seen, [])


class JournalFileTest(unittest.TestCase):
    def test_entries_append_with_time_tool_and_command(self):
        project = make_project()
        write = jiralog.journal(project, "jira fix-fields", now=lambda: "2026-10-05T12:00:00Z")
        write({"action": "update", "key": "IRIS-41", "fields": {"labels": ["ci"]}})
        write({"action": "transition", "key": "IRIS-42", "to": "Done"})
        lines = (project / "harness" / "jira-writes.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(line) for line in lines], [
            {"ts": "2026-10-05T12:00:00Z", "tool": "wow", "command": "jira fix-fields", "action": "update",
             "key": "IRIS-41", "fields": {"labels": ["ci"]}},
            {"ts": "2026-10-05T12:00:00Z", "tool": "wow", "command": "jira fix-fields", "action": "transition",
             "key": "IRIS-42", "to": "Done"}])

    def test_a_journal_that_cannot_write_never_breaks_the_command(self):
        project = make_project()
        (project / "harness").write_text("not a directory", encoding="utf-8")
        jiralog.journal(project, "close")({"action": "transition", "key": "IRIS-42", "to": "Done"})


class CliWiringTest(unittest.TestCase):
    def test_the_commands_that_write_to_jira_journal_into_the_project(self):
        import os
        from unittest import mock
        import cli
        project = make_project()
        env = {"IC_JIRA_BASE_URL": "https://acme.atlassian.net", "IC_JIRA_USER_EMAIL": "dev@acme.io",
               "IC_JIRA_API_TOKEN": "tok-SECRET-1"}
        with mock.patch.dict(os.environ, env):
            client = cli._jira_for(project, command="close --epic E1")
        client._journal({"action": "transition", "key": "IRIS-42", "to": "Done"})
        [line] = (project / "harness" / "jira-writes.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(json.loads(line)["command"], "close --epic E1")


if __name__ == "__main__":
    unittest.main()
