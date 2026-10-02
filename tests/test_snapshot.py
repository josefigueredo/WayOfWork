from __future__ import annotations

import unittest

from helpers import make_project, write
import config
import schema
import snapshot
import state


def fake_state(progress="3/4"):
    return {"schema_version": 1,
            "plan": {"id": "0001-x", "phase": 3, "stale_packets": [], "missing": []},
            "epics": [{"id": "E1", "title": "t", "jira": "IRIS-40", "jira_url": None, "phase": 5,
                       "reason": None, "progress": progress, "missing": ["implement WU-004"]},
                      {"id": "E2", "title": "u", "jira": None, "jira_url": None, "phase": "unknown",
                       "reason": "jira not configured", "progress": None, "missing": []}],
            "blockers": [], "next_steps": [], "steps_total": 1, "sources": {"jira": "ok"}}


class SnapshotTest(unittest.TestCase):
    def test_history_point_sums_known_progress(self):
        point = snapshot.history_point(fake_state(), "2026-10-02T10:00:00Z")
        self.assertEqual(point, {"ts": "2026-10-02T10:00:00Z", "plan_phase": 3,
                                 "phases": {"E1": 5, "E2": "unknown"}, "tasks_done": 3, "tasks_total": 4})

    def test_build_appends_history_and_keeps_usage(self):
        import usage as usage_mod
        record = {k: None for k in usage_mod.RECORD_KEYS}
        record.update({"ts": "t", "vendor": "cursor", "model": "x", "scope": "task", "source": "cursor-run"})
        previous = {"history": [{"ts": "a", "plan_phase": 2, "phases": {}, "tasks_done": 0, "tasks_total": 0}],
                    "usage": [record]}
        snap = snapshot.build(fake_state(), previous, "2026-10-02T10:00:00Z")
        self.assertEqual(len(snap["history"]), 2)
        self.assertEqual(snap["usage"], [record])
        self.assertEqual(schema.validate(snap, schema.load_schema("progress")), [])

    def test_real_state_snapshot_validates_and_round_trips(self):
        project = make_project()
        snap = snapshot.build(state.compute_state(project, config.DEFAULTS), None, "2026-10-02T10:00:00Z")
        self.assertEqual(schema.validate(snap, schema.load_schema("progress")), [])
        path = snapshot.write(project, snap)
        self.assertEqual(snapshot.load_previous(project)["generated_at"], "2026-10-02T10:00:00Z")
        self.assertTrue(path.read_text(encoding="utf-8").endswith("\n"))

    def test_load_previous_ignores_invalid_file(self):
        project = make_project()
        write(project, "wow/progress.json", "{bad")
        self.assertIsNone(snapshot.load_previous(project))


class UsageInSnapshotTest(unittest.TestCase):
    def test_usage_param_replaces_previous(self):
        import usage as usage_mod
        record = {k: None for k in usage_mod.RECORD_KEYS}
        record.update({"ts": "t", "vendor": "cursor", "model": "composer-2.5", "scope": "task", "source": "cursor-run"})
        previous = {"history": [], "usage": [{"stale": True}]}
        snap = snapshot.build(fake_state(), previous, "2026-10-02T10:00:00Z", usage=[record])
        self.assertEqual(snap["usage"], [record])
        self.assertEqual(schema.validate(snap, schema.load_schema("progress")), [])

    def test_schema_rejects_incomplete_usage_record(self):
        snap = snapshot.build(fake_state(), None, "2026-10-02T10:00:00Z", usage=[{"vendor": "x"}])
        self.assertTrue(schema.validate(snap, schema.load_schema("progress")))


if __name__ == "__main__":
    unittest.main()
