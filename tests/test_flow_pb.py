"""The Product Brain flow as a checklist: every tick comes from the same sources wow state reads."""
from __future__ import annotations

import json
import unittest

from helpers import make_project, write
import config
import flow_pb
import manifest
from test_state import FakeJira, close_chats, project_at_phase_3, summary

CFG = config.DEFAULTS


def states(items):
    return {i.id: i.state for i in items}


def stories(p):
    return len(manifest.load(p)["epics"][0]["tasks"])


class FlowPbTest(unittest.TestCase):
    def test_empty_project_asks_for_context_and_plan(self):
        self.assertEqual(states(flow_pb.items(make_project(), CFG, None)),
                         {"context": "todo", "owner": "todo", "manifest": "todo"})

    def test_a_ready_plan_ticks_context_readiness_and_packets(self):
        got = states(flow_pb.items(project_at_phase_3(), CFG, None))
        for item in ("context", "owner", "manifest", "readiness", "packet-prd", "packet-rfc", "packet-E1"):
            self.assertEqual(got[item], "done", item)
        self.assertEqual(got["chat-prd"], "todo")

    def test_closed_and_audited_chats_are_done(self):
        p = project_at_phase_3()
        close_chats(p)
        got = states(flow_pb.items(p, CFG, None))
        self.assertEqual([got[c] for c in ("chat-prd", "chat-rfc", "chat-E1")], ["done"] * 3)

    def test_exported_epic_with_all_stories_and_fixed_fields_is_done(self):
        p = project_at_phase_3()
        write(p, "harness/jira-writes.jsonl", json.dumps({"tool": "wow", "command": "jira fix-fields", "action": "update",
                                                          "key": "IRIS-41", "fields": {}}) + "\nnot json\n")
        jira = FakeJira({"IRIS-40": dict(summary("IRIS-40", stories(p), 0), story_keys=["IRIS-41"])})
        got = states(flow_pb.items(p, CFG, jira))
        self.assertEqual((got["export-E1"], got["stories-E1"], got["fix-fields-E1"]), ("done", "done", "done"))

    def test_missing_stories_and_unfixed_fields_stay_todo(self):
        p = project_at_phase_3()
        write(p, "harness/jira-writes.jsonl", json.dumps({"command": "close --epic E9", "key": "X-1"}) + "\n")
        jira = FakeJira({"IRIS-40": dict(summary("IRIS-40", stories(p) - 1, 0), story_keys=["IRIS-41"])})
        got = states(flow_pb.items(p, CFG, jira))
        self.assertEqual((got["stories-E1"], got["fix-fields-E1"]), ("todo", "todo"))

    def test_without_any_write_log_the_repair_is_unverified_not_pending(self):
        # The log exists since 2026-10-05 (fa51a3a); IRIS's fix-fields --apply ran the night before and left none.
        p = project_at_phase_3()
        jira = FakeJira({"IRIS-40": dict(summary("IRIS-40", stories(p), 0), story_keys=["IRIS-41"])})
        item = next(i for i in flow_pb.items(p, CFG, jira) if i.id == "fix-fields-E1")
        self.assertEqual(item.state, "unverified")
        self.assertIn("wow jira fix-fields --epic E1", item.evidence)

    def test_a_measured_clean_dry_run_ticks_the_repair(self):
        p = project_at_phase_3()
        write(p, "harness/jira-fields-checks.json",
              json.dumps({"IRIS-40": {"epic": "E1", "fixable": 0, "at": "2026-10-06T17:30:00Z"}}))
        jira = FakeJira({"IRIS-40": dict(summary("IRIS-40", stories(p), 0), story_keys=["IRIS-41"])})
        item = next(i for i in flow_pb.items(p, CFG, jira) if i.id == "fix-fields-E1")
        self.assertEqual((item.state, item.evidence), ("done", "simulación sin pendientes, 2026-10-06T17:30:00Z"))

    def test_a_dry_run_with_stories_to_fix_keeps_it_pending(self):
        p = project_at_phase_3()
        write(p, "harness/jira-fields-checks.json", json.dumps({"IRIS-40": {"epic": "E1", "fixable": 2, "at": "T"}}))
        jira = FakeJira({"IRIS-40": dict(summary("IRIS-40", stories(p), 0), story_keys=["IRIS-41"])})
        item = next(i for i in flow_pb.items(p, CFG, jira) if i.id == "fix-fields-E1")
        self.assertEqual((item.state, item.evidence), ("todo", "2 historias por corregir (simulación de T)"))

    def test_an_unexported_epic_has_no_jira_items_yet(self):
        got = states(flow_pb.items(project_at_phase_3(frozen=False), CFG, None))
        self.assertEqual(got["export-E1"], "todo")
        self.assertNotIn("stories-E1", got)

    def test_without_jira_the_jira_items_are_unverified_not_failed(self):
        got = states(flow_pb.items(project_at_phase_3(), CFG, None))
        self.assertEqual((got["stories-E1"], got["fix-fields-E1"]), ("unverified", "unverified"))

    def test_jira_down_is_unverified_too(self):
        got = states(flow_pb.items(project_at_phase_3(), CFG, FakeJira(error="jira: timeout")))
        self.assertEqual(got["stories-E1"], "unverified")


if __name__ == "__main__":
    unittest.main()
