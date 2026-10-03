from __future__ import annotations

import json
import unittest

from helpers import make_project, write
import config
import manifest
import pack
import state
from pbfill import fill
from sources import SourceUnavailable
from test_manifest import pb_ready_doc, valid_doc

CFG = config.DEFAULTS


class FakeJira:
    def __init__(self, summaries=None, error=None):
        self.summaries, self.error = summaries or {}, error

    def epic_summary(self, key):
        if self.error:
            raise SourceUnavailable(self.error)
        return self.summaries[key]


def summary(key, stories, done):
    return {"key": key, "exists": True, "stories": stories, "done": done,
            "story_keys": [], "url": f"https://acme.atlassian.net/browse/{key}"}


def project_at_phase_3(frozen=True):
    """Context pack done, readiness approved, packets fresh, manifest frozen with E1=IRIS-40 (unless frozen=False)."""
    p = make_project()
    write(p, "wow/context-pack/facts.md", "- C1: hecho de prueba [MEDIDO] (fuente: README.md)\n")
    write(p, "wow/context-pack/pending-owner.md", "- [x] North Star\n")
    write(p, ".spec-kit/discovery/architecture.md", "# Arquitectura\n")
    doc = pb_ready_doc()
    doc["plan"]["readiness"] = {"verdict": "approved", "rounds": 1}
    if frozen:
        doc = manifest.freeze(doc, {"E1": "IRIS-40"}, "2026-10-02T10:00:00Z")
    manifest.save(p, doc)
    h = manifest.manifest_hash(p)
    brief = pack.parse_brief("## Brief\n- Goal: x\n- Open questions: none\n")
    texts = {"prd": pack.render_prd(doc, brief, h), "rfc": pack.render_rfc(doc, brief, h),
             "epic-E1": pack.render_epic(doc, "E1", h)}
    for name, text in texts.items():
        write(p, f"wow/pb/{name}.md", fill(text))
    return p


def close_chats(p, names=("prd", "rfc", "epic-E1")):
    for name in names:
        write(p, f"wow/pb/chats/{name}.md", "llega al 100%")
        write(p, f"wow/pb/chats/{name}.audit.json", '{"verdict": "approved"}')


TASKS_DONE = "- [x] T010 WU-001 model\n  - jira: IRIS-41\n- [x] T011 WU-002 api\n  - jira: IRIS-41\n"


def add_feature(p, tasks=TASKS_DONE):
    write(p, "specs/001-curation/spec.md", "**Jira Epic:** IRIS-40\n")
    write(p, "specs/001-curation/plan.md", "# Plan\n")
    write(p, "specs/001-curation/tasks.md", tasks)
    write(p, "specs/001-curation/work-units.json", '{"work_units": [{"id": "WU-001"}, {"id": "WU-002"}]}')


class DraftEpicTest(unittest.TestCase):
    def test_draft_epic_gets_no_packet_or_product_brain_steps(self):
        p = project_at_phase_3()
        doc = manifest.load(p)
        draft = json.loads(json.dumps(doc["epics"][0]))
        draft.update({"id": "E2", "title": "Later", "status": "draft", "done_when": ["E2.C1: later"]})
        for n, task in enumerate(draft["tasks"], 1):
            task["id"], task["depends_on"] = f"2.{n}", []
        doc["epics"].append(draft)
        manifest.save(p, doc)
        h = manifest.manifest_hash(p)
        brief = pack.parse_brief("## Brief\n- Goal: x\n- Open questions: none\n")
        texts = {"prd": pack.render_prd(doc, brief, h), "rfc": pack.render_rfc(doc, brief, h),
                 "epic-E1": pack.render_epic(doc, "E1", h)}
        for name, text in texts.items():
            write(p, f"wow/pb/{name}.md", fill(text))
        result = state.compute_state(p, CFG)
        self.assertEqual(result["plan"]["phase"], 3)
        self.assertFalse([s for s in result["next_steps"] if "E2" in json.dumps(s)])
        e2 = next(e for e in result["epics"] if e["id"] == "E2")
        self.assertEqual((e2["phase"], e2["missing"]), ("draft", []))

    def test_plan_with_only_draft_epics_is_parked_without_packet_steps(self):
        p = project_at_phase_3()
        doc = manifest.load(p)
        doc["epics"][0]["status"] = "draft"
        manifest.save(p, doc)  # the hash changes, so prd and rfc would otherwise be stale
        result = state.compute_state(p, CFG)
        self.assertTrue(result["plan"]["parked"])
        self.assertEqual((result["plan"]["missing"], result["plan"]["stale_packets"]), ([], []))
        self.assertEqual(result["next_steps"], [])


class ExportedPacketsTest(unittest.TestCase):
    def test_after_export_only_unexported_epics_need_packets(self):
        p = project_at_phase_3()  # E1 exported as IRIS-40; its packets were written before this change
        doc = manifest.load(p)
        later = json.loads(json.dumps(doc["epics"][0]))
        later.update({"id": "E2", "title": "Later", "done_when": ["E2.C1: later"]})
        for n, task in enumerate(later["tasks"], 1):
            task["id"], task["depends_on"] = f"2.{n}", []
        doc["epics"].append(later)
        manifest.save(p, doc)  # the hash changes, as it does when freeze records a key
        result = state.compute_state(p, CFG)
        self.assertEqual(result["plan"]["stale_packets"], [])
        self.assertEqual(result["plan"]["missing"], ["generate the epic-E2 packet"])


class PlanPhasesTest(unittest.TestCase):
    def test_fresh_project_is_phase_0_with_context_step(self):
        result = state.compute_state(make_project(), CFG)
        self.assertEqual(result["plan"]["phase"], 0)
        self.assertEqual(result["next_steps"][0]["action"], "build the context pack")
        self.assertEqual(result["next_steps"][0]["where"], "harness")
        self.assertEqual(result["sources"]["jira"], "not_configured")

    def test_open_owner_items_are_blockers_and_planning_continues(self):
        p = make_project()
        write(p, "wow/context-pack/facts.md", "- C1: hecho de prueba [MEDIDO] (fuente: README.md)\n")
        write(p, "wow/context-pack/pending-owner.md", "- [ ] North Star\n- [ ] SLA\n")
        result = state.compute_state(p, CFG)
        self.assertEqual(result["plan"]["phase"], 0)
        self.assertEqual(result["blockers"], ["owner: 2 decision(s) open in wow/context-pack/pending-owner.md"])
        self.assertEqual(result["next_steps"][0]["command"], "wow-plan")

    def test_readiness_pending_is_phase_1(self):
        p = make_project()
        write(p, "wow/context-pack/facts.md", "- C1: hecho de prueba [MEDIDO] (fuente: README.md)\n")
        write(p, "wow/context-pack/pending-owner.md", "- [x] ok\n")
        manifest.save(p, dict(valid_doc(), plan=dict(valid_doc()["plan"], mode="greenfield")))
        result = state.compute_state(p, CFG)
        self.assertEqual(result["plan"]["phase"], 1)
        self.assertEqual(result["next_steps"][0]["command"], "wow review --set readiness --ref plan")

    def test_stale_packet_is_phase_2(self):
        p = project_at_phase_3(frozen=False)  # before export; an exported epic's packet is never re-asked
        write(p, "wow/pb/epic-E1.md", "<!-- wow: manifest-hash=ffffffffffffffff -->\n")
        result = state.compute_state(p, CFG)
        self.assertEqual(result["plan"]["phase"], 2)
        self.assertEqual(result["plan"]["stale_packets"], ["epic-E1"])
        self.assertEqual(result["epics"][0]["phase"], 2)
        self.assertEqual(result["next_steps"][0]["command"], "wow pack epic --id E1")

    def test_invalid_manifest_json_gives_fix_step(self):
        p = make_project()
        write(p, "wow/context-pack/facts.md", "- C1: hecho de prueba [MEDIDO] (fuente: README.md)\n")
        write(p, "wow/context-pack/pending-owner.md", "")
        write(p, "wow/plan/manifest.json", "{bad")
        result = state.compute_state(p, CFG)
        self.assertEqual(result["plan"]["phase"], 1)
        self.assertEqual(result["next_steps"][0]["command"], "wow manifest validate")


class EpicPhasesTest(unittest.TestCase):
    def test_phase_3_waits_for_prd_chat_first(self):
        result = state.compute_state(project_at_phase_3(), CFG, FakeJira({}))
        epic = result["epics"][0]
        self.assertEqual(epic["phase"], 3)
        self.assertEqual(result["next_steps"][0]["where"], "product-brain")
        self.assertIn("wow/pb/prd.md", result["next_steps"][0]["command"])

    def test_exported_epic_does_not_need_a_closing_phrase_in_its_chats(self):
        p = project_at_phase_3()  # E1 already exported as IRIS-40
        for name in ("prd", "rfc", "epic-E1"):
            write(p, f"wow/pb/chats/{name}.md", "¿Querés que procedamos con el repaso de validación final?")
            write(p, f"wow/pb/chats/{name}.audit.json", '{"verdict": "approved"}')
        result = state.compute_state(p, CFG, FakeJira({"IRIS-40": summary("IRIS-40", 2, 0)}))
        self.assertEqual(result["epics"][0]["phase"], 4)

    def test_phase_3_unaudited_chat(self):
        p = project_at_phase_3()
        close_chats(p)
        write(p, "wow/pb/chats/rfc.audit.json", '{"verdict": "changes_required"}')
        result = state.compute_state(p, CFG, FakeJira({}))
        self.assertEqual(result["next_steps"][0]["action"], "audit the RFC chat")

    def test_jira_unavailable_makes_epic_unknown(self):
        p = project_at_phase_3()
        close_chats(p)
        result = state.compute_state(p, CFG, FakeJira(error="jira: HTTP 401 on /rest/api/3/search/jql"))
        self.assertEqual(result["epics"][0]["phase"], "unknown")
        self.assertEqual(result["epics"][0]["reason"], "jira: HTTP 401 on /rest/api/3/search/jql")
        self.assertEqual(result["sources"]["jira"], "jira: HTTP 401 on /rest/api/3/search/jql")

    def test_jira_not_configured_makes_epic_unknown(self):
        p = project_at_phase_3()
        close_chats(p)
        self.assertEqual(state.compute_state(p, CFG, None)["epics"][0]["phase"], "unknown")

    def test_epic_packet_missing_only_jira_prefix_goes_to_product_brain(self):
        import re
        p = project_at_phase_3()
        path = p / "wow/pb/epic-E1.md"
        path.write_text(re.sub(r"\| Prefijo Jira \(jira_prefix\) \| [^|]* \|",
                               "| Prefijo Jira (jira_prefix) | {{jira_prefix}} |", path.read_text()))
        result = state.compute_state(p, CFG)
        self.assertEqual(result["plan"]["phase"], 3)
        self.assertNotIn("complete the epic-E1 packet", result["plan"]["missing"])

    def test_brownfield_discovery_comes_right_before_the_spec_kit_sync(self):
        p = project_at_phase_3()
        (p / ".spec-kit/discovery/architecture.md").unlink()
        close_chats(p)
        result = state.compute_state(p, CFG, FakeJira({"IRIS-40": summary("IRIS-40", 2, 0)}))
        self.assertNotIn("run Spec-Kit discovery on the existing code", result["plan"]["missing"])
        self.assertEqual(result["epics"][0]["phase"], 4)
        step = result["next_steps"][0]
        self.assertEqual((step["epic"], step["action"], step["where"], step["command"]),
                         ("E1", "run Spec-Kit discovery on the existing code", "cursor", "/spec-kit.discovery"))

    def test_phase_4_sync_step_uses_cursor(self):
        p = project_at_phase_3()
        close_chats(p)
        result = state.compute_state(p, CFG, FakeJira({"IRIS-40": summary("IRIS-40", 2, 0)}))
        epic = result["epics"][0]
        self.assertEqual(epic["phase"], 4)
        self.assertEqual(epic["jira_url"], "https://acme.atlassian.net/browse/IRIS-40")
        step = result["next_steps"][0]
        self.assertEqual((step["where"], step["model"], step["command"]),
                         ("cursor", "composer-2.5", "/spec-kit.sync --epic-key IRIS-40"))

    def test_phase_5_pending_work_unit_and_progress(self):
        p = project_at_phase_3()
        close_chats(p)
        add_feature(p, "- [x] T010 WU-001 model\n  - jira: IRIS-41\n- [ ] T011 WU-002 api\n  - jira: IRIS-41\n")
        result = state.compute_state(p, CFG, FakeJira({"IRIS-40": summary("IRIS-40", 2, 0)}))
        epic = result["epics"][0]
        self.assertEqual((epic["phase"], epic["progress"]), (5, "1/2"))
        self.assertEqual(result["next_steps"][0]["command"], "/spec-kit.implement WU-002")

    def test_phase_5_story_review_before_cursor(self):
        p = project_at_phase_3()
        close_chats(p)
        add_feature(p)
        result = state.compute_state(p, CFG, FakeJira({"IRIS-40": summary("IRIS-40", 2, 0)}))
        self.assertEqual(result["epics"][0]["phase"], 5)
        self.assertEqual(result["next_steps"][0]["command"], "wow review --set story --ref IRIS-41")

    def test_story_approved_by_a_human_after_hitl_closes_its_review(self):
        p = project_at_phase_3()
        close_chats(p)
        add_feature(p)
        write(p, "wow/reviews/IRIS-41.json", json.dumps({"final": "approved_by_human"}))
        result = state.compute_state(p, CFG, FakeJira({"IRIS-40": summary("IRIS-40", 2, 1)}))
        self.assertNotIn("wow review --set story --ref IRIS-41", [s["command"] for s in result["next_steps"]])
        self.assertEqual(result["epics"][0]["phase"], 6)

    def test_phase_6_and_done(self):
        p = project_at_phase_3()
        close_chats(p)
        add_feature(p)
        write(p, "wow/reviews/IRIS-41.json", json.dumps({"final": "approved"}))
        jira = FakeJira({"IRIS-40": summary("IRIS-40", 2, 1)})
        result = state.compute_state(p, CFG, jira)
        self.assertEqual(result["epics"][0]["phase"], 6)
        commands = [s["command"] for s in result["next_steps"]]
        self.assertIn("/spec-kit.sync-status specs/001-curation", commands)
        sync_step = next(s for s in result["next_steps"] if s["command"].startswith("/spec-kit.sync-status"))
        self.assertEqual(sync_step["where"], "cursor")  # the slash command is the one that reports telemetry
        self.assertIn("wow review --set epic --ref E1", commands)
        write(p, "wow/reviews/E1.json", json.dumps({"final": "approved"}))
        done = state.compute_state(p, CFG, FakeJira({"IRIS-40": summary("IRIS-40", 2, 2)}))
        self.assertEqual(done["epics"][0]["phase"], "done")

    def test_open_epic_in_jira_asks_for_wow_close(self):
        p = project_at_phase_3()
        close_chats(p)
        add_feature(p)
        write(p, "wow/reviews/IRIS-41.json", json.dumps({"final": "approved"}))
        write(p, "wow/reviews/E1.json", json.dumps({"final": "approved_by_human"}))
        open_epic = dict(summary("IRIS-40", 2, 2), epic_done=False)
        result = state.compute_state(p, CFG, FakeJira({"IRIS-40": open_epic}))
        self.assertEqual(result["epics"][0]["phase"], 6)
        self.assertEqual(result["next_steps"][0]["command"], "wow close --epic E1")
        closed = dict(open_epic, epic_done=True)
        self.assertEqual(state.compute_state(p, CFG, FakeJira({"IRIS-40": closed}))["epics"][0]["phase"], "done")

    def test_at_most_three_steps_and_cursor_last(self):
        p = make_project()
        result = state.compute_state(p, CFG)
        self.assertLessEqual(len(result["next_steps"]), 3)
        wheres = [s["where"] for s in result["next_steps"]]
        self.assertEqual(wheres, sorted(wheres, key=lambda w: w == "cursor"))


class ModeStepsTest(unittest.TestCase):
    def test_missing_mode_and_brownfield_discovery_steps(self):
        p = make_project()
        write(p, "wow/context-pack/facts.md", "- C1: hecho de prueba [MEDIDO] (fuente: README.md)\n")
        write(p, "wow/context-pack/pending-owner.md", "")
        manifest.save(p, valid_doc())
        result = state.compute_state(p, CFG)
        self.assertEqual(result["next_steps"][0]["action"], "set the plan mode")
        manifest.save(p, pb_ready_doc())
        missing = state.compute_state(p, CFG)["plan"]["missing"]
        self.assertNotIn("run Spec-Kit discovery on the existing code", missing)  # only before the Spec-Kit sync
        self.assertNotIn("set the plan mode", missing)
        write(p, ".spec-kit/discovery/architecture.md", "# Arquitectura\n")
        self.assertNotIn("run Spec-Kit discovery on the existing code",
                         state.compute_state(p, CFG)["plan"]["missing"])


class TemplateManifestTest(unittest.TestCase):
    def test_template_manifest_asks_to_complete_the_plan_before_readiness(self):
        p = make_project()
        write(p, "wow/context-pack/facts.md", "- C1: hecho [MEDIDO] (fuente: README.md)\n")
        write(p, "wow/context-pack/pending-owner.md", "")
        manifest.save(p, manifest.new_manifest("0001-x", "X", "2026-10-02", mode="brownfield"))
        write(p, ".spec-kit/discovery/architecture.md", "x")
        result = state.compute_state(p, CFG)
        self.assertEqual(result["next_steps"][0]["action"], "complete the plan")
        self.assertEqual(result["next_steps"][0]["command"], "wow-plan")
        self.assertNotIn("run the readiness review", result["plan"]["missing"])


if __name__ == "__main__":
    unittest.main()
