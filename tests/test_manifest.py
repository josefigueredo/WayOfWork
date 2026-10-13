from __future__ import annotations

import json
import unittest

from helpers import make_project, write
import manifest


def valid_doc() -> dict:
    return {
        "schema_version": 1,
        "plan": {"id": "0001-iris-v2", "title": "IRIS v2", "created": "2026-10-01",
                 "readiness": {"verdict": None, "rounds": 0},
                 "export": {"frozen": False, "at": None, "epics": {}}},
        "epics": [
            {"id": "E1", "title": "Curation", "done_when": ["E1.C1: analysts can curate"],
             "tasks": [
                 {"id": "1.1", "title": "Model", "acceptance": ["AC1: schema exists"], "depends_on": [],
                  "subtasks": ["write schema"], "estimate": 3, "priority": "high", "labels": ["backend"]},
                 {"id": "1.2", "title": "API", "acceptance": ["AC1: endpoint returns 200"], "depends_on": ["1.1"],
                  "subtasks": [], "estimate": 2, "priority": "medium", "labels": ["backend"]},
             ]},
        ],
    }


class ValidateTest(unittest.TestCase):
    def test_valid_doc(self):
        self.assertEqual(manifest.validate(valid_doc()), [])

    def test_schema_error_short_circuits(self):
        doc = valid_doc()
        doc["plan"]["readiness"]["rounds"] = 4
        self.assertEqual(manifest.validate(doc), ["$.plan.readiness.rounds: 4 is greater than maximum 3"])

    def test_duplicate_task_id_and_missing_dependency(self):
        doc = valid_doc()
        doc["epics"][0]["tasks"][1]["id"] = "1.1"
        doc["epics"][0]["tasks"][1]["depends_on"] = ["9.9"]
        errors = manifest.validate(doc)
        self.assertIn("duplicate task id '1.1'", errors)
        self.assertIn("task 1.1 depends on unknown task '9.9'", errors)

    def test_dependency_cycle(self):
        doc = valid_doc()
        doc["epics"][0]["tasks"][0]["depends_on"] = ["1.2"]
        self.assertIn("dependency cycle involving task '1.1'", manifest.validate(doc))

    def test_done_when_must_match_epic_and_ac_ids_unique(self):
        doc = valid_doc()
        doc["epics"][0]["done_when"] = ["E2.C1: wrong epic"]
        doc["epics"][0]["tasks"][0]["acceptance"] = ["AC1: a", "AC1: b"]
        errors = manifest.validate(doc)
        self.assertIn("epic E1: done_when 'E2.C1' does not belong to E1", errors)
        self.assertIn("task 1.1: duplicate acceptance id 'AC1'", errors)


class LintTest(unittest.TestCase):
    def test_lint_flags_missing_planning_fields(self):
        doc = valid_doc()
        task = doc["epics"][0]["tasks"][0]
        task.update({"acceptance": [], "estimate": None, "priority": None, "labels": []})
        doc["epics"][0]["done_when"] = []
        self.assertEqual(manifest.lint(doc), [
            "E1/1.1: no acceptance criteria",
            "E1/1.1: no estimate (story points)",
            "E1/1.1: no priority",
            "E1/1.1: no labels",
            "E1: no done_when",
        ])


class LoadSaveFreezeTest(unittest.TestCase):
    def test_load_missing_raises(self):
        with self.assertRaises(manifest.ManifestError):
            manifest.load(make_project())

    def test_load_invalid_json_reports_position(self):
        project = make_project()
        write(project, "wow/plan/manifest.json", '{"plan": ,}')
        with self.assertRaises(manifest.ManifestError) as ctx:
            manifest.load(project)
        self.assertIn("line 1 column", str(ctx.exception))

    def test_load_accepts_bom(self):
        project = make_project()
        (project / "wow/plan").mkdir(parents=True)
        (project / "wow/plan/manifest.json").write_bytes(b"\xef\xbb\xbf" + json.dumps(valid_doc()).encode())
        self.assertEqual(manifest.load(project)["plan"]["id"], "0001-iris-v2")

    def test_save_roundtrip_and_hash_changes(self):
        project = make_project()
        manifest.save(project, valid_doc())
        first = manifest.manifest_hash(project)
        self.assertEqual(len(first), 16)
        doc = manifest.load(project)
        doc["plan"]["title"] = "IRIS v2 b"
        manifest.save(project, doc)
        self.assertNotEqual(first, manifest.manifest_hash(project))
        self.assertTrue((project / manifest.MANIFEST_REL).read_text(encoding="utf-8").endswith("\n"))

    def test_parse_epic_keys(self):
        self.assertEqual(manifest.parse_epic_keys("E1=IRIS-40, E2=IRIS-41"), {"E1": "IRIS-40", "E2": "IRIS-41"})
        with self.assertRaises(ValueError):
            manifest.parse_epic_keys("E1:IRIS-40")

    def test_freeze_adds_keys_and_keeps_existing(self):
        doc = manifest.freeze(valid_doc(), {"E1": "IRIS-40"}, "2026-10-02T10:00:00Z")
        self.assertEqual(doc["plan"]["export"], {"frozen": True, "at": "2026-10-02T10:00:00Z", "epics": {"E1": "IRIS-40"}})
        again = manifest.freeze(doc, {}, "2026-10-03T10:00:00Z")
        self.assertEqual(again["plan"]["export"]["at"], "2026-10-02T10:00:00Z")

    def test_freeze_refuses_changing_a_recorded_key_without_reopen(self):
        doc = manifest.freeze(valid_doc(), {"E1": "IRIS-40"}, "2026-10-02T10:00:00Z")
        with self.assertRaises(manifest.FrozenError):
            manifest.freeze(doc, {"E1": "IRIS-99"}, "2026-10-03T10:00:00Z")
        same = manifest.freeze(doc, {"E1": "IRIS-40"}, "2026-10-03T10:00:00Z")
        self.assertEqual(same["plan"]["export"]["epics"], {"E1": "IRIS-40"})
        reopened = manifest.freeze(doc, {"E1": "IRIS-99"}, "2026-10-03T10:00:00Z", reopen_reason="wrong key")
        self.assertEqual(reopened["plan"]["export"]["epics"], {"E1": "IRIS-99"})

    def test_freeze_rejects_unknown_epic(self):
        with self.assertRaises(ValueError):
            manifest.freeze(valid_doc(), {"E9": "IRIS-1"}, "2026-10-02T10:00:00Z")

    def test_ensure_writable(self):
        frozen = manifest.freeze(valid_doc(), {"E1": "IRIS-40"}, "2026-10-02T10:00:00Z")
        manifest.ensure_writable(valid_doc(), None)
        manifest.ensure_writable(frozen, "owner changed scope")
        with self.assertRaises(manifest.FrozenError) as ctx:
            manifest.ensure_writable(frozen, None)
        self.assertIn("/spec-kit.amend", str(ctx.exception))

    def test_frozen_error_names_the_manual_scope_change_path(self):
        # Product Brain has no Artifact Engine in its code: the PRD, RFC/epic and Jira are updated by hand.
        frozen = manifest.freeze(valid_doc(), {"E1": "IRIS-40"}, "2026-10-02T10:00:00Z")
        with self.assertRaises(manifest.FrozenError) as ctx:
            manifest.ensure_writable(frozen, None)
        message = str(ctx.exception)
        self.assertNotIn("Artifact Engine", message)
        for step in ("PRD", "RFC", "Jira", "/spec-kit.amend", "--reopen"):
            self.assertIn(step, message)

    def test_new_manifest_validates_but_lints_with_findings(self):
        doc = manifest.new_manifest("0002-demo", "Demo", "2026-10-01")
        self.assertEqual(manifest.validate(doc), [])
        self.assertTrue(manifest.lint(doc))


def pb_ready_doc() -> dict:
    doc = valid_doc()
    doc["plan"]["mode"] = "brownfield"
    doc["epics"][0]["product"] = {
        "objective": "Curar casos", "problem": "Hoy se cura a mano", "strategic_objective": "Eficiencia",
        "expected_impact": "Menos tiempo de curación", "out_of_scope": "Migrar históricos",
        "insights": ["Los analistas curan 40 casos por día [MEDIDO]"], "assumptions": ["Hay analistas disponibles"],
        "dependencies": ["Equipo de plataforma"], "related_documents": ["PRD de la iniciativa"],
        "start_date": "2026-10-05", "end_date_estimated": "2026-12-18", "quarter": "Q4/2026",
        "criticality": "Alta", "priority": "Alta", "big_move": False, "owner": "Owner de producto",
        "vertical": "Plataforma", "technical_context": "Python sobre AWS Lambda", "notes": "Sin notas adicionales"}
    for task in doc["epics"][0]["tasks"]:
        task["component"] = "BE"
        task["acceptance"] = [f"{a.split(':')[0]}: Dado un caso Cuando el analista lo cura Entonces queda auditado"
                              for a in task["acceptance"]]
        task["story"] = {"user_story_text": "Como analista quiero curar casos para cerrar el ciclo",
                         "context_and_need": "Hoy se cura a mano [MEDIDO]", "scope": "Curación simple",
                         "out_of_scope": "Curación masiva", "technical_info": "Endpoint del BFF",
                         "assumptions": ["Caso existente"], "business_rules": ["Solo analistas"],
                         "edge_cases": ["Caso ya curado"], "assets": ["Contrato del BFF"]}
    return doc


class PbExtensionTest(unittest.TestCase):
    def test_extended_doc_validates_and_old_doc_still_validates(self):
        self.assertEqual(manifest.validate(pb_ready_doc()), [])
        self.assertEqual(manifest.validate(valid_doc()), [])

    def test_schema_rejects_bad_component_date_and_mode(self):
        doc = pb_ready_doc()
        doc["epics"][0]["tasks"][0]["component"] = "Backend"
        doc["epics"][0]["product"]["start_date"] = "pronto"
        doc["plan"]["mode"] = "legacy"
        errors = manifest.validate(doc)
        self.assertTrue(any("component" in e for e in errors), errors)
        self.assertTrue(any("start_date" in e for e in errors), errors)
        self.assertTrue(any("mode" in e for e in errors), errors)

    def test_epic_status_is_active_or_draft(self):
        doc = pb_ready_doc()
        doc["epics"][0]["status"] = "draft"
        self.assertEqual(manifest.validate(doc), [])
        doc["epics"][0]["status"] = "paused"
        self.assertTrue(any("status" in e for e in manifest.validate(doc)))

    def test_subtasks_accept_objects(self):
        doc = pb_ready_doc()
        doc["epics"][0]["tasks"][0]["subtasks"] = ["write schema", {"title": "[BE] tabla", "purpose": "guardar",
                                                                     "how_to": "DynamoDB", "component": "BE"}]
        self.assertEqual(manifest.validate(doc), [])

    def test_pb_lint(self):
        self.assertEqual(manifest.pb_lint(pb_ready_doc()), [])
        doc = valid_doc()
        doc["epics"][0]["tasks"][0]["estimate"] = 4
        doc["epics"][0]["tasks"][1]["estimate"] = 13
        self.assertEqual(manifest.pb_lint(doc), [
            "plan: no mode; set plan.mode to greenfield or brownfield (wow plan init --mode)",
            "E1/1.1: estimate 4 is not Fibonacci (1, 2, 3, 5, 8, 13)",
            "E1/1.1: no component (FE, BE, BO, QA, DEVOPS, INFRA, BFF, AI)",
            "E1/1.1: no user story text (Como … quiero … para …)",
            "E1/1.1: AC1 is not Gherkin (Dado … Cuando … Entonces …)",
            "E1/1.2: estimate 13 is above 8; Product Brain suggests splitting the story",
            "E1/1.2: no component (FE, BE, BO, QA, DEVOPS, INFRA, BFF, AI)",
            "E1/1.2: no user story text (Como … quiero … para …)",
            "E1/1.2: AC1 is not Gherkin (Dado … Cuando … Entonces …)",
        ])


if __name__ == "__main__":
    unittest.main()
