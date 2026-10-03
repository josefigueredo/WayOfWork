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


class BackfillTest(unittest.TestCase):
    def test_tasks_md_commits_become_history_points(self):
        import os
        import subprocess
        repo = make_project()

        def git(*args, date=None):
            env = dict(os.environ, GIT_AUTHOR_DATE=date or "", GIT_COMMITTER_DATE=date or "")
            subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
                           check=True, capture_output=True, text=True, env=env)

        git("init", "-q", "-b", "main")
        write(repo, "specs/001-x/spec.md", "**Jira Epic:** [IRIS-40](https://x/browse/IRIS-40)\n")
        write(repo, "specs/001-x/tasks.md", "- [x] T001 a\n- [ ] T002 b\n- [ ] T003 c\n")
        git("add", "-A")
        git("commit", "-q", "-m", "tasks", date="2026-10-02T20:00:00+00:00")
        write(repo, "specs/001-x/tasks.md", "- [x] T001 a\n- [x] T002 b\n- [x] T003 c\n")
        git("commit", "-q", "-am", "done", date="2026-10-02T21:00:00+00:00")
        points = snapshot.backfill_points(repo, {"IRIS-40": "E1"})
        self.assertEqual([(p["ts"], p["tasks_done"], p["tasks_total"], p["epics"], p["source"]) for p in points],
                         [("2026-10-02T20:00:00Z", 1, 3, {"E1": {"done": 1, "total": 3}}, "git"),
                          ("2026-10-02T21:00:00Z", 3, 3, {"E1": {"done": 3, "total": 3}}, "git")])
        existing = [{"ts": "2026-10-03T03:00:00Z", "plan_phase": 3, "phases": {}, "tasks_done": 3, "tasks_total": 3}]
        merged = snapshot.merge_history(existing, points + points)  # idempotent: rerunning adds nothing twice
        self.assertEqual([p["ts"] for p in merged], ["2026-10-02T20:00:00Z", "2026-10-02T21:00:00Z", "2026-10-03T03:00:00Z"])
        self.assertEqual(snapshot.backfill_points(make_project(), {"IRIS-40": "E1"}), [])  # not a git repo


class SnapshotTest(unittest.TestCase):
    def test_history_point_sums_known_progress(self):
        point = snapshot.history_point(fake_state(), "2026-10-02T10:00:00Z")
        self.assertEqual(point, {"ts": "2026-10-02T10:00:00Z", "plan_phase": 3,
                                 "phases": {"E1": 5, "E2": "unknown"}, "tasks_done": 3, "tasks_total": 4,
                                 "epics": {"E1": {"done": 3, "total": 4}}})

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
