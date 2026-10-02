from __future__ import annotations

import unittest

from helpers import make_project, write
import config
import manifest
import pack
import state
from sources import repo
from test_manifest import valid_doc

BRIEF = """# Plan
## Brief
- Goal: Curar casos en IRIS v2
- Decisions: D1 una sola máquina de estados · D2 BFF como frontera
- Constraints: costo del juez ≤ USD 100
- Non-goals: migrar datos históricos
- Open questions: none
## Other
- Goal: ignored
"""


class BriefTest(unittest.TestCase):
    def test_parse_brief_only_reads_brief_section(self):
        brief = pack.parse_brief(BRIEF)
        self.assertEqual(brief["Goal"], "Curar casos en IRIS v2")
        self.assertEqual(brief["Non-goals"], "migrar datos históricos")
        self.assertEqual(brief["Open questions"], "none")

    def test_missing_brief_gives_empty_values(self):
        self.assertEqual(pack.parse_brief("nothing")["Goal"], "")


class RenderTest(unittest.TestCase):
    def test_epic_packet_maps_tasks_to_stories(self):
        text = pack.render_epic(valid_doc(), "E1", "0123456789abcdef")
        self.assertEqual(repo.HASH_RE.search(text).group(1), "0123456789abcdef")
        self.assertIn("# Épica E1 — Curation", text)
        self.assertIn("- E1.C1: analysts can curate", text)
        self.assertIn("### H2 — API (tarea 1.2)", text)
        self.assertIn("- Story points: 2   ·   Prioridad: media   ·   Depende de: H1", text)
        self.assertIn("  - AC1: endpoint returns 200", text)
        self.assertIn("<!-- wow:fill", text)

    def test_epic_undefined_values_and_unknown_epic(self):
        doc = valid_doc()
        doc["epics"][0]["tasks"][0].update({"estimate": None, "priority": None, "labels": []})
        text = pack.render_epic(doc, "E1", "0123456789abcdef")
        self.assertIn("- Story points: [SIN DEFINIR]   ·   Prioridad: [SIN DEFINIR]   ·   Depende de: —", text)
        with self.assertRaises(ValueError):
            pack.render_epic(doc, "E9", "0123456789abcdef")

    def test_prd_and_rfc_use_brief(self):
        brief = pack.parse_brief(BRIEF)
        prd = pack.render_prd(valid_doc(), brief, "0123456789abcdef")
        self.assertIn("## Resumen\nCurar casos en IRIS v2", prd)
        self.assertIn("### Fuera de alcance\nmigrar datos históricos", prd)
        self.assertIn("## Preguntas abiertas\nNinguna.", prd)
        self.assertIn("- Autor: [SIN DEFINIR]", prd)
        rfc = pack.render_rfc(valid_doc(), brief, "0123456789abcdef")
        self.assertIn("- D1 una sola máquina de estados", rfc)
        self.assertIn("- D2 BFF como frontera", rfc)
        self.assertIn("### E1 — Curation", rfc)


class WriteTest(unittest.TestCase):
    def test_refuses_overwrite_without_force(self):
        project = make_project()
        pack.write_packet(project, "prd", "v1")
        with self.assertRaises(FileExistsError):
            pack.write_packet(project, "prd", "v2")
        pack.write_packet(project, "prd", "v2", force=True)
        self.assertEqual((project / "wow/pb/prd.md").read_text(encoding="utf-8"), "v2")

    def test_preamble_written_once(self):
        project = make_project()
        path = pack.ensure_preamble(project)
        self.assertIn("[SIN DEFINIR]", path.read_text(encoding="utf-8"))
        path.write_text("edited", encoding="utf-8")
        pack.ensure_preamble(project)
        self.assertEqual(path.read_text(encoding="utf-8"), "edited")


class StateIntegrationTest(unittest.TestCase):
    def test_packed_project_reaches_phase_3(self):
        project = make_project()
        write(project, "wow/context-pack/facts.md", "x")
        write(project, "wow/context-pack/pending-owner.md", "")
        doc = valid_doc()
        doc["plan"]["readiness"] = {"verdict": "approved", "rounds": 1}
        manifest.save(project, doc)
        write(project, "wow/plan/PLAN.md", BRIEF)
        mhash = manifest.manifest_hash(project)
        brief = pack.parse_brief(BRIEF)
        pack.write_packet(project, "prd", pack.render_prd(doc, brief, mhash))
        pack.write_packet(project, "rfc", pack.render_rfc(doc, brief, mhash))
        pack.write_packet(project, "epic-E1", pack.render_epic(doc, "E1", mhash))
        self.assertEqual(state.compute_state(project, config.DEFAULTS)["plan"]["phase"], 3)


if __name__ == "__main__":
    unittest.main()
