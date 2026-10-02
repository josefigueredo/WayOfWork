from __future__ import annotations

import unittest

from helpers import make_project, write
import config
import manifest
import pack
import pbcompletion
import state
from pbfill import fill
from sources import repo
from test_manifest import pb_ready_doc, valid_doc

BRIEF = """# Plan
## Brief
- Goal: Curar casos en IRIS v2
- Decisions: D1 una sola máquina de estados · D2 BFF como frontera
- Constraints: costo del juez ≤ USD 100
- Non-goals: migrar datos históricos · curación masiva
- Open questions: ¿Se incorpora la etapa de plan?
"""
H = "0123456789abcdef"


class BriefTest(unittest.TestCase):
    def test_parse_brief(self):
        brief = pack.parse_brief(BRIEF)
        self.assertEqual((brief["Goal"], brief["Open questions"]), ("Curar casos en IRIS v2", "¿Se incorpora la etapa de plan?"))


class PrdRfcTest(unittest.TestCase):
    def test_prd_follows_pb_template_and_keeps_unknowns_as_placeholders(self):
        text = pack.render_prd(pb_ready_doc(), pack.parse_brief(BRIEF), H, pending=["North Star"])
        self.assertEqual(repo.HASH_RE.search(text).group(1), H)
        self.assertIn("template=pb-9b19a89", text)
        self.assertIn("## Vision y Estrategia", text)
        self.assertIn("| Tipo de Iniciativa | Evolución de sistema existente |", text)
        self.assertIn("| 1 | E1: Curation | E1.C1: analysts can curate |", text)
        self.assertIn("| 1 | migrar datos históricos | {{out_scope_1_reason}} | {{out_scope_1_when}} |", text)
        self.assertIn("| 2 | curación masiva |", text)
        self.assertIn("| 1 | ¿Se incorpora la etapa de plan? | Owner de producto | Abierta |", text)
        self.assertIn("| 2 | North Star | Owner de producto | Abierta |", text)
        self.assertIn("{{why_now}}", text)
        self.assertNotIn("{{in_scope_2_name}}", text)
        result = pbcompletion.predict("prd", text)
        self.assertLess(result["percentage"], 100)
        self.assertEqual(pbcompletion.predict("prd", fill(text))["percentage"], 100)

    def test_rfc_greenfield_coexistence_and_milestones(self):
        doc = pb_ready_doc()
        doc["plan"]["mode"] = "greenfield"
        text = pack.render_rfc(doc, pack.parse_brief(BRIEF), H)
        self.assertIn("No aplica: sistema nuevo; no convive con un sistema previo.", text)
        self.assertIn("| E1 | Curation | 5 story points |", text)
        self.assertIn("- E1.C1: analysts can curate", text)
        self.assertIn("### API Gateway", text)
        self.assertEqual(pbcompletion.predict("rfc", fill(text))["percentage"], 100)


class EpicTest(unittest.TestCase):
    def test_epic_packet_has_pb_shape_and_checks_clean_when_filled(self):
        text = pack.render_epic(pb_ready_doc(), "E1", H)
        self.assertIn("| Criticidad (criticality) | Alta |", text)
        self.assertIn("### US-002 — [BE] API (tarea 1.2)", text)
        self.assertIn("| Story points (story_points) | 2 |", text)
        self.assertIn("| Prioridad (priority) | Media |", text)
        self.assertIn("- US-001 (tarea 1.1)", text)
        self.assertIn("- AC1 — Dado un caso Cuando el analista lo cura Entonces queda auditado", text)
        self.assertIn("- " + pbcompletion.DOR[0], text)
        self.assertIn("- " + pbcompletion.DOD[10] + " — no", text)
        self.assertIn("E1.C1: analysts can curate", text)
        result = pbcompletion.check_epic(fill(text))
        self.assertEqual((result["percentage"], result["errors"]), (100, []))
        with self.assertRaises(ValueError):
            pack.render_epic(pb_ready_doc(), "E9", H)

    def test_draft_epic_packet_carries_draft_status(self):
        doc = pb_ready_doc()
        self.assertIn("| Estado (status) | todo |", pack.render_epic(doc, "E1", H))
        doc["epics"][0]["status"] = "draft"
        text = pack.render_epic(doc, "E1", H)
        self.assertIn("| Estado (status) | draft |", text)
        self.assertEqual(pbcompletion.check_epic(fill(text))["errors"], [])

    def test_old_manifest_epic_lists_what_is_missing(self):
        result = pbcompletion.check_epic(pack.render_epic(valid_doc(), "E1", H))
        self.assertLess(result["percentage"], 100)
        self.assertTrue(any("not Gherkin" in e for e in result["errors"]))


class WriteTest(unittest.TestCase):
    def test_refuses_overwrite_without_force_and_preamble_rules(self):
        project = make_project()
        pack.write_packet(project, "prd", "v1")
        with self.assertRaises(FileExistsError):
            pack.write_packet(project, "prd", "v2")
        text = pack.ensure_preamble(project).read_text(encoding="utf-8")
        for needle in ("API Gateway", "SLA", "Owner es el rol que decide", "No aplica", "[SIN DEFINIR]"):
            self.assertIn(needle, text)


class StateIntegrationTest(unittest.TestCase):
    def test_filled_packets_reach_phase_3_and_unfilled_stay_in_phase_2(self):
        project = make_project()
        write(project, "wow/context-pack/facts.md", "- C1: hecho de prueba [MEDIDO] (fuente: README.md)\n")
        write(project, "wow/context-pack/pending-owner.md", "")
        write(project, ".spec-kit/discovery/architecture.md", "# Arquitectura\n")
        doc = pb_ready_doc()
        doc["plan"]["readiness"] = {"verdict": "approved", "rounds": 1}
        manifest.save(project, doc)
        mhash = manifest.manifest_hash(project)
        brief = pack.parse_brief(BRIEF)
        packets = {"prd": pack.render_prd(doc, brief, mhash), "rfc": pack.render_rfc(doc, brief, mhash),
                   "epic-E1": pack.render_epic(doc, "E1", mhash)}
        for name, text in packets.items():
            pack.write_packet(project, name, text)
        result = state.compute_state(project, config.DEFAULTS)
        self.assertEqual(result["plan"]["phase"], 2)
        self.assertTrue(any(s["action"].startswith("complete the prd packet") for s in result["next_steps"]))
        for name, text in packets.items():
            pack.write_packet(project, name, fill(text), force=True)
        self.assertEqual(state.compute_state(project, config.DEFAULTS)["plan"]["phase"], 3)


class TableCellEscapeTest(unittest.TestCase):
    def test_pipes_and_newlines_in_cells_do_not_break_rows(self):
        doc = pb_ready_doc()
        doc["epics"][0]["title"] = "Auth | Gateway"
        doc["epics"][0]["done_when"] = ["E1.C1: line one\nline two"]
        text = pack.render_prd(doc, pack.parse_brief(BRIEF), H)
        self.assertIn("| 1 | E1: Auth \\| Gateway | E1.C1: line one line two |", text)
        self.assertEqual(pbcompletion.predict("prd", fill(text))["percentage"], 100)


if __name__ == "__main__":
    unittest.main()
