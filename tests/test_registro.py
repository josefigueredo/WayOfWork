"""Registro packets: Product Brain's full template shape, real content only where it orients the epic."""
from __future__ import annotations

import re
import unittest

from helpers import make_project, run_cli
import manifest
import pack
import pbcompletion
from pbfill import fill
from test_manifest import pb_ready_doc

BRIEF = """# Plan
## Brief
- Goal: Curar casos en IRIS v2
- Problem: Hoy los casos se curan a mano y sin auditoría (C3)
- Decisions: D1 una sola máquina de estados (C3) · D2 BFF como frontera (C4, C5)
- Constraints: costo del juez ≤ USD 100 · sin PCI (C7)
- Non-goals: migrar datos históricos · curación masiva
- Open questions: none

## Contexto
IRIS v2 corre sobre Lambda y la curación vive en el BFF (C1).
El deploy coincide con main (medido, C8) y con el BFF (D2).
"""
H = "0123456789abcdef"


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    nxt = re.search(r"^#{1,3} ", text[start + len(heading):], re.MULTILINE)
    return text[start:start + len(heading) + (nxt.start() if nxt else len(text))]


class BriefTest(unittest.TestCase):
    def test_brief_reads_problem_and_context(self):
        brief = pack.parse_brief(BRIEF)
        self.assertEqual(brief["Problem"], "Hoy los casos se curan a mano y sin auditoría (C3)")
        self.assertTrue(brief["Context"].startswith("IRIS v2 corre sobre Lambda y la curación vive en el BFF (C1)."))


class RegistroPrdTest(unittest.TestCase):
    def setUp(self):
        self.text = pack.render_prd(pb_ready_doc(), pack.parse_brief(BRIEF), H, registro=True)

    def test_scores_100_with_no_placeholder_left(self):
        self.assertNotIn("{{", self.text)
        result = pbcompletion.predict("prd", self.text)
        self.assertEqual((result["percentage"], result["errors"]), (100, []))

    def test_orienting_fields_carry_the_plan(self):
        self.assertIn("Curar casos en IRIS v2", _section(self.text, "## Resumen Ejecutivo"))
        self.assertIn("Hoy los casos se curan a mano y sin auditoría", _section(self.text, "### Problema"))
        self.assertIn("IRIS v2 corre sobre Lambda", _section(self.text, "### Contexto"))
        self.assertIn("El deploy coincide con main (medido) y con el BFF.", _section(self.text, "### Contexto"))
        self.assertIn("| 1 | migrar datos históricos |", self.text)
        self.assertIn("costo del juez ≤ USD 100", _section(self.text, "## Requerimientos No Funcionales"))
        self.assertIn("| 1 | Ninguna | Owner de producto | Cerrada |", self.text)

    def test_unused_tables_collapse_to_one_marked_row(self):
        kpis = _section(self.text, "### KPIs Primarios")
        rows = [l for l in kpis.splitlines() if l.startswith("|") and "---" not in l][1:]
        self.assertEqual(len(rows), 1, kpis)
        self.assertIn("No aplica", rows[0])
        self.assertIn(pack.REGISTRO_REASON, self.text)

    def test_internal_references_never_reach_product_brain(self):
        for ref in ("(C3)", "C4", "(C1)", "(C7)", "D1 ", "D2 "):
            self.assertNotIn(ref, self.text, ref)
        self.assertIn("E1.C1", self.text)
        self.assertIn("AC1", self.text)


class RegistroRfcTest(unittest.TestCase):
    def setUp(self):
        self.text = pack.render_rfc(pb_ready_doc(), pack.parse_brief(BRIEF), H, registro=True)

    def test_scores_100_with_no_placeholder_left(self):
        self.assertNotIn("{{", self.text)
        result = pbcompletion.predict("rfc", self.text)
        self.assertEqual((result["percentage"], result["errors"]), (100, []))

    def test_orienting_fields_carry_the_plan(self):
        self.assertIn("una sola máquina de estados", _section(self.text, "## 5. Alternativas"))
        self.assertIn("sin PCI", _section(self.text, "### Seguridad"))
        self.assertIn("| BE |", self.text)
        self.assertIn("- E1.C1: analysts can curate", self.text)
        for letter in "ABC":
            self.assertIn(f"#### {letter}. No aplica", self.text)
        self.assertNotIn("#### D.", self.text)


class EpicHygieneTest(unittest.TestCase):
    def test_epic_packet_has_no_task_suffix_commas_or_references(self):
        doc = pb_ready_doc()
        doc["epics"][0]["product"]["insights"] = ["Las mediciones traen su comando, así que se re-ejecutan (C22, C23)"]
        doc["epics"][0]["product"]["out_of_scope"] = "Corregir el contenido (tarea 1.2) y automatizar"
        text = pack.render_epic(doc, "E1", H)
        self.assertIn("| Corregir el contenido y automatizar |", text)
        self.assertNotIn("(tarea", text)
        self.assertIn("### US-002 — [BE] API\n", text)
        self.assertIn("- US-001\n", text)
        self.assertIn("- Las mediciones traen su comando; así que se re-ejecutan\n", text)
        result = pbcompletion.check_epic(fill(text))
        self.assertEqual((result["percentage"], result["errors"]), (100, []))


class HygieneCheckTest(unittest.TestCase):
    def test_check_flags_what_product_brain_breaks(self):
        text = fill(pack.render_epic(pb_ready_doc(), "E1", H))
        broken = text.replace("### US-002 — [BE] API\n", "### US-002 — [BE] API (tarea 1.2)\n", 1)
        broken = broken.replace("- Caso ya curado", "- Caso ya curado, o borrado (C14)", 1)
        errors = pbcompletion.check_epic(broken)["errors"]
        self.assertTrue(any("(tarea" in e for e in errors), errors)
        self.assertTrue(any("comma" in e for e in errors), errors)
        self.assertTrue(any("C14" in e for e in errors), errors)

    def test_fixed_product_brain_lists_may_keep_their_commas(self):
        text = fill(pack.render_epic(pb_ready_doc(), "E1", H))
        self.assertIn("APIs, Figmas", text)
        self.assertEqual(pbcompletion.check_epic(text)["errors"], [])

    def test_rfc_api_block_beyond_c_is_an_error(self):
        text = pack.render_rfc(pb_ready_doc(), pack.parse_brief(BRIEF), H, registro=True)
        extra = text.replace("### Modelo de Datos", "#### D. Extra\n- Endpoint: `x`\n\n### Modelo de Datos", 1)
        self.assertTrue(any("API D" in e for e in pbcompletion.predict("rfc", extra)["errors"]))

    def test_bare_commit_is_an_error_but_a_full_commit_url_is_fine(self):
        text = pack.render_prd(pb_ready_doc(), pack.parse_brief(BRIEF), H, registro=True)
        bare = text.replace("Curar casos en IRIS v2", "Curar casos (motor @ 53fd100, tablero @ b65505c)", 1)
        errors = pbcompletion.predict("prd", bare)["errors"]
        self.assertTrue(any("53fd100" in e and "github.com/<owner>/<repo>/commit/" in e for e in errors), errors)
        url = text.replace("Curar casos en IRIS v2",
                           "Curar casos (https://github.com/acme/engine/commit/53fd100fa3b04295f91b4960b442a7259e401895)", 1)
        self.assertEqual(pbcompletion.predict("prd", url)["errors"], [])

    def test_prd_reference_is_an_error(self):
        text = pack.render_prd(pb_ready_doc(), pack.parse_brief(BRIEF), H, registro=True)
        broken = text.replace("Curar casos en IRIS v2", "Curar casos en IRIS v2 (C9)", 1)
        self.assertTrue(any("C9" in e for e in pbcompletion.predict("prd", broken)["errors"]))


class ReviewFindingsTest(unittest.TestCase):
    def test_partly_filled_groups_keep_every_row(self):
        doc = pb_ready_doc()
        doc["epics"][0]["tasks"][1]["component"] = "FE"
        prd = pack.render_prd(doc, pack.parse_brief(BRIEF), H, registro=True)
        self.assertIn("| 2 | curación masiva | No aplica | No aplica |", prd)
        rfc = pack.render_rfc(doc, pack.parse_brief(BRIEF), H, registro=True)
        self.assertIn("| BE | No aplica | Model |", rfc)
        self.assertIn("| FE | No aplica | API |", rfc)

    def test_bare_ids_in_prose_are_content_not_references(self):
        brief = BRIEF.replace("- Goal: Curar casos en IRIS v2",
                              "- Goal: Subir la retención D1, D7 y D30 con diagramas C4 y D3.js")
        text = pack.render_prd(pb_ready_doc(), pack.parse_brief(brief), H, registro=True)
        self.assertIn("retención D1, D7 y D30 con diagramas C4 y D3.js", text)
        self.assertEqual(pbcompletion.predict("prd", text)["errors"], [])

    def test_tarea_in_prose_is_not_a_task_suffix(self):
        brief = BRIEF.replace("costo del juez ≤ USD 100", "recálculo como job nocturno (tarea programada)")
        text = pack.render_rfc(pb_ready_doc(), pack.parse_brief(brief), H, registro=True)
        self.assertIn("(tarea programada)", text)
        self.assertEqual(pbcompletion.predict("rfc", text)["errors"], [])

    def test_single_braces_in_content_survive(self):
        doc = pb_ready_doc()
        doc["epics"][0]["tasks"][1]["title"] = "GET /orders/{orderId}"
        text = pack.render_rfc(doc, pack.parse_brief(BRIEF), H, registro=True)
        self.assertIn("GET /orders/{orderId}", text)

    def test_decimal_commas_survive_in_epic_lists(self):
        doc = pb_ready_doc()
        doc["epics"][0]["product"]["insights"] = ["latencia p95 ≤ 1,5 s, medida en prod"]
        text = pack.render_epic(doc, "E1", H)
        self.assertIn("- latencia p95 ≤ 1,5 s; medida en prod\n", text)
        self.assertEqual(pbcompletion.check_epic(fill(text))["errors"], [])


class RegistroCliTest(unittest.TestCase):
    def _project(self):
        project = make_project()
        manifest.save(project, pb_ready_doc())
        (project / "wow/plan").mkdir(parents=True, exist_ok=True)
        (project / "wow/plan/PLAN.md").write_text(BRIEF, encoding="utf-8")
        return project

    def test_registro_is_the_default_and_checks_clean(self):
        project = self._project()
        for kind in ("prd", "rfc"):
            self.assertEqual(run_cli(["pack", kind, "--project", str(project)])[0], 0)
            self.assertNotIn("{{", (project / f"wow/pb/{kind}.md").read_text(encoding="utf-8"))
            self.assertEqual(run_cli(["pack", "check", kind, "--project", str(project)])[0], 0)

    def test_full_keeps_placeholders_and_warns_deprecated(self):
        project = self._project()
        code, _, err = run_cli(["pack", "prd", "--full", "--project", str(project)])
        self.assertEqual(code, 0)
        self.assertIn("deprecated", err)
        self.assertIn("{{why_now}}", (project / "wow/pb/prd.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
