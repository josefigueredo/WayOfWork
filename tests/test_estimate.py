"""wow estimate: calibrated on past epics, every number says whether it was measured or assumed."""
from __future__ import annotations

import datetime as dt
import json
import unittest

from helpers import make_project, run_cli, write
import config
import estimate
import manifest
from test_manifest import pb_ready_doc


def _history_project():
    """A finished epic shaped like the PRISM pilot: 117 min of implementation, 17.5 h estimated, 7 SP."""
    project = make_project()
    doc = pb_ready_doc()
    doc["epics"][0]["tasks"][0]["estimate"] = 5
    doc["epics"][0]["tasks"][1]["estimate"] = 2
    manifest.save(project, doc)
    write(project, ".spec-kit/history/changelog.jsonl",
          '{"ts": "2026-10-02T19:02:35Z", "event": "feature.specified", "feature_id": "001-x"}\n'
          '{"ts": "2026-10-02T20:59:35Z", "event": "feature.implemented", "feature_id": "001-x"}\n')
    write(project, ".spec-kit/work-units.json", json.dumps({"work_units": [
        {"id": "WU-001", "estimated_hours": 10.5, "subtasks": []},
        {"id": "WU-002", "estimated_hours": 7, "subtasks": []}]}))
    for ref, rounds in (("IRIS-41", 3), ("IRIS-42", 1)):
        write(project, f"wow/reviews/{ref}.json", json.dumps(
            {"ref": ref, "anchor_set": "story", "final": "approved", "rounds": [{"n": n} for n in range(rounds)]}))
    write(project, "wow/reviews/E1.json", json.dumps(
        {"ref": "E1", "anchor_set": "epic", "final": "approved", "rounds": [{"n": 1}, {"n": 2}]}))
    write(project, "harness/reviews/20261002T214000Z-IRIS-41-r1.json", json.dumps({"duration_ms": 180000}))
    write(project, "harness/reviews/20261002T214300Z-IRIS-41-r2.json", json.dumps({"duration_ms": 60000}))
    return project


def _current_project(sp=(3, 5)):
    project = make_project()
    doc = pb_ready_doc()
    doc["epics"][0]["tasks"][0]["estimate"] = sp[0]
    doc["epics"][0]["tasks"][1]["estimate"] = sp[1]
    doc["epics"][0]["product"]["start_date"] = "2026-10-05"
    manifest.save(project, doc)
    return project


class HistoryTest(unittest.TestCase):
    def test_metrics_read_from_a_finished_epic(self):
        m = estimate.history_metrics(_history_project())
        self.assertEqual((m["impl_minutes"], m["est_hours"], m["story_points"]), (117.0, 17.5, 7))
        self.assertEqual((m["story_rounds"], m["epic_rounds"], m["round_minutes"]), ([3, 1], [2], [3.0, 1.0]))


class EstimateTest(unittest.TestCase):
    def test_without_work_units_scales_by_story_points_and_labels_the_source(self):
        result = estimate.estimate(_current_project(), [_history_project()], config.DEFAULTS,
                                   today=dt.date(2026, 10, 4))
        impl = next(c for c in result["components"] if c["name"] == "implementation")
        self.assertEqual((round(impl["minutes"]), impl["source"]), (134, "measured"))  # 8 SP x 117/7
        review = next(c for c in result["components"] if c["name"] == "independent reviews")
        self.assertEqual((round(review["minutes"]), review["source"]), (12, "measured"))  # (2x2 + 1x2) rounds x 2 min
        pb = next(c for c in result["components"] if c["name"] == "Product Brain")
        self.assertEqual(pb["source"], "assumed")
        self.assertLess(result["low_minutes"], result["minutes"])
        self.assertLess(result["minutes"], result["high_minutes"])
        self.assertEqual(result["start"], "2026-10-05")
        self.assertTrue(result["end_likely"] <= result["end_high"])

    def test_work_unit_hours_take_over_once_spec_kit_shaped_the_work(self):
        project = _current_project()
        write(project, ".spec-kit/work-units.json", json.dumps({"work_units": [
            {"id": "WU-001", "estimated_hours": 7, "subtasks": []}]}))
        result = estimate.estimate(project, [_history_project()], config.DEFAULTS, today=dt.date(2026, 10, 4))
        impl = next(c for c in result["components"] if c["name"] == "implementation")
        self.assertEqual(round(impl["minutes"]), 47)  # 7 h x 117/17.5
        self.assertIn("work-unit", impl["basis"])

    def test_no_history_means_every_number_is_assumed(self):
        result = estimate.estimate(_current_project(), [], config.DEFAULTS, today=dt.date(2026, 10, 4))
        self.assertTrue(all(c["source"] == "assumed" for c in result["components"]))

    def test_end_date_skips_weekends(self):
        self.assertEqual(estimate.add_working_days(dt.date(2026, 10, 9), 1), dt.date(2026, 10, 12))  # Fri + 1 = Mon


class ModelSuggestionTest(unittest.TestCase):
    def test_big_or_delicate_work_goes_to_the_reasoning_model(self):
        models = config.DEFAULTS["models"]
        cases = [
            ({"estimate": 2, "component": "BE", "labels": []}, models["cursor_generate"]),
            ({"estimate": 5, "component": "BE", "labels": []}, models["cursor_reason"]),
            ({"estimate": 1, "component": "INFRA", "labels": []}, models["cursor_reason"]),
            ({"estimate": 1, "component": "FE", "labels": ["security"]}, models["cursor_reason"]),
            ({"estimate": 8, "component": "BE", "labels": [], "model": "my-model"}, "my-model"),
            ({"id": "WU-005", "estimated_hours": 4.5}, models["cursor_reason"]),
            ({"id": "WU-001", "estimated_hours": 1.5}, models["cursor_generate"]),
        ]
        for item, expected in cases:
            model, why = estimate.suggest_model(item, config.DEFAULTS)
            self.assertEqual(model, expected, item)
            self.assertTrue(why)

    def test_manifest_accepts_an_explicit_model(self):
        doc = pb_ready_doc()
        doc["epics"][0]["tasks"][0]["model"] = "claude-sonnet-5-5-high"
        self.assertEqual(manifest.validate(doc), [])


class CliTest(unittest.TestCase):
    def test_estimate_prints_sources_models_and_dates(self):
        project = _current_project()
        code, out, _ = run_cli(["estimate", "--history", str(_history_project()), "--project", str(project)])
        self.assertEqual(code, 0)
        for needle in ("implementation", "measured", "assumed", "end:", "model"):
            self.assertIn(needle, out)
        self.assertEqual(run_cli(["estimate", "--project", str(make_project())])[0], 2)  # no manifest


if __name__ == "__main__":
    unittest.main()
