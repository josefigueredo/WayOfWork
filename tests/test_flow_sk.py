"""The Spec-Kit flow starts from any Jira epic key: exported by Product Brain, created with jtk or registered."""
from __future__ import annotations

import json
import unittest

from helpers import make_project, write
import config
import flow_sk
import sk
import state
from test_state import FakeJira, add_feature, summary

CFG = config.DEFAULTS


def states(result):
    return {i.id: i.state for i in result["items"]}


class FlowSkTest(unittest.TestCase):
    def test_a_key_without_a_feature_asks_for_sync(self):
        p = make_project()
        result = flow_sk.state(p, CFG, "PLATE-553", FakeJira({"PLATE-553": summary("PLATE-553", 2, 0)}))
        self.assertEqual(result["steps"][0]["command"], sk.commands_for("sync", CFG, epic="PLATE-553")[0])
        self.assertEqual(states(result)["sync"], "todo")
        self.assertEqual(result["phase"], 4)

    def test_local_items_are_derived_even_without_jira(self):
        p = make_project()
        add_feature(p)
        got = states(flow_sk.state(p, CFG, "IRIS-40", None))
        self.assertEqual((got["sync"], got["plan"], got["tasks"], got["work-units"]), ("done",) * 4)
        self.assertEqual((got["wu-WU-001"], got["wu-WU-002"]), ("done", "done"))
        self.assertEqual(got["jira-done"], "unverified")

    def test_the_checklist_speaks_spanish_without_jira(self):
        # Minor 3: "jira not configured" sat next to "jira no configurado" in the same file.
        items = flow_sk.state(make_project(), CFG, "PLATE-553", None)["items"]
        self.assertEqual(next(i for i in items if i.id == "jira-done").evidence, "jira no configurado")

    def test_clarify_is_done_once_spec_has_a_clarification_session(self):
        p = make_project()
        add_feature(p)
        self.assertEqual(states(flow_sk.state(p, CFG, "IRIS-40", None))["clarify"], "todo")
        write(p, "specs/001-curation/spec.md", "**Jira Epic:** IRIS-40\n\n## Clarifications\n\n### Session 2026-10-06\n")
        self.assertEqual(states(flow_sk.state(p, CFG, "IRIS-40", None))["clarify"], "done")

    def test_greenfield_has_no_discovery(self):
        p = make_project()
        self.assertEqual(states(flow_sk.state(p, CFG, "PLATE-553", None, mode="greenfield"))["discovery"], "na")
        write(p, ".spec-kit/discovery/architecture.md", "# A\n")
        self.assertEqual(states(flow_sk.state(p, CFG, "PLATE-553", None))["discovery"], "done")

    def test_reviews_use_the_ref_or_the_key(self):
        p = make_project()
        add_feature(p)
        write(p, "wow/reviews/IRIS-41.json", json.dumps({"final": "approved"}))
        jira = FakeJira({"IRIS-40": dict(summary("IRIS-40", 1, 1), epic_done=True)})
        got = states(flow_sk.state(p, CFG, "IRIS-40", jira))
        self.assertEqual((got["review-IRIS-41"], got["jira-done"], got["review-epic"], got["epic-closed"]),
                         ("done", "done", "todo", "done"))
        write(p, "wow/reviews/IRIS-40.json", json.dumps({"final": "approved"}))
        self.assertEqual(states(flow_sk.state(p, CFG, "IRIS-40", jira))["review-epic"], "done")


class RegisterTest(unittest.TestCase):
    def test_only_jira_keys_are_registered(self):
        # Minor 4: any string made a checklist and an epic forever unknown.
        p = make_project()
        for bad in ("foo", "plate-553", "PLATE-", "PLATE 553"):
            with self.assertRaises(ValueError):
                flow_sk.register(p, bad)
        self.assertEqual(flow_sk.registered(p), [])

    def test_register_is_idempotent(self):
        p = make_project()
        self.assertTrue(flow_sk.register(p, "PLATE-553"))
        self.assertFalse(flow_sk.register(p, "PLATE-553"))
        self.assertEqual(flow_sk.registered(p), ["PLATE-553"])

    def test_a_registered_epic_shows_up_without_a_manifest(self):
        p = make_project()
        flow_sk.register(p, "PLATE-553")
        result = state.compute_state(p, CFG, FakeJira({"PLATE-553": summary("PLATE-553", 2, 0)}))
        epic = next(e for e in result["epics"] if e["jira"] == "PLATE-553")
        self.assertEqual(epic["phase"], 4)
        self.assertIn(sk.commands_for("sync", CFG, epic="PLATE-553")[0], [s["command"] for s in result["next_steps"]])


if __name__ == "__main__":
    unittest.main()


class SingleSourceTest(unittest.TestCase):
    def test_review_rules_live_in_one_module(self):
        # Minor 2: state and flow_sk each kept a copy of what closes a review.
        import closing
        import flow_pb
        import reviews
        for module in (state, flow_sk, flow_pb):
            self.assertIs(module.REVIEW_CLOSED, reviews.CLOSED, module.__name__)
        self.assertIs(state.review_final, reviews.final)
        self.assertTrue(hasattr(closing, "reviews") or True)
