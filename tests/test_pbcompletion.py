from __future__ import annotations

import unittest

from helpers import make_project, write
import pbcompletion
import pbtemplate
from pbfill import fill


class ValueStateTest(unittest.TestCase):
    def test_states(self):
        self.assertEqual(pbcompletion.value_state("  "), "empty")
        self.assertEqual(pbcompletion.value_state("{{x}}"), "empty")
        self.assertEqual(pbcompletion.value_state("texto {{x}}"), "partial")
        self.assertEqual(pbcompletion.value_state("[SIN DEFINIR] — decide el owner"), "filled")
        self.assertEqual(pbcompletion.value_state("<!-- wow:fill x -->"), "empty")


class PredictTest(unittest.TestCase):
    def test_raw_templates_are_zero_and_filled_are_hundred(self):
        for kind, total in (("prd", 49), ("rfc", 35)):
            raw = pbcompletion.predict(kind, pbtemplate.load(kind))
            self.assertEqual((raw["percentage"], raw["total"]), (0, total), kind)
            full = pbcompletion.predict(kind, fill(pbtemplate.load(kind)))
            self.assertEqual((full["percentage"], full["pending"]), (100, []), kind)

    def test_open_question_without_owner_is_partial(self):
        text = fill(pbtemplate.load("prd")).replace("| 1 | dato | Owner de producto | Abierta |", "| 1 | dato |  | Abierta |")
        result = pbcompletion.predict("prd", text)
        self.assertEqual(result["percentage"], 99)
        self.assertEqual(result["pending"], [{"field": "open_questions", "state": "partial",
                                              "section": "## Preguntas Abiertas"}])

    def test_group_with_one_complete_row_is_filled_and_empty_kv_cell_is_empty(self):
        lines = fill(pbtemplate.load("prd")).replace("| Autor | dato |", "| Autor |  |").splitlines()
        start = lines.index("### KPIs Primarios")
        kpi_rows = [i for i in range(start, start + 9) if lines[i].startswith("| dato |")]
        for index in reversed(kpi_rows[1:]):
            del lines[index]
        result = pbcompletion.predict("prd", "\n".join(lines))
        self.assertIn({"field": "author", "state": "empty", "section": "# dato"}, result["pending"])
        self.assertNotIn("kpi", [p["field"] for p in result["pending"]])
        self.assertEqual(result["percentage"], 98)

    def test_accented_heading_still_matches(self):
        text = fill(pbtemplate.load("prd")).replace("## Vision y Estrategia", "## Visión y Estrategia")
        self.assertEqual(pbcompletion.predict("prd", text)["percentage"], 100)

    def test_missing_section_empties_its_fields(self):
        text = fill(pbtemplate.load("rfc"))
        start = text.index("### Coexistencia y Fallback")
        end = text.index("### Especificaciones de API")
        result = pbcompletion.predict("rfc", text[:start] + text[end:])
        self.assertIn("coexistence_strategy", [p["field"] for p in result["pending"]])

    def test_only_optional_fields_pending_is_ready_for_product_brain(self):
        import re
        import pack
        from test_manifest import pb_ready_doc
        full = fill(pack.render_epic(pb_ready_doc(), "E1", "0123456789abcdef"))
        no_prefix = re.sub(r"\| Prefijo Jira \(jira_prefix\) \| [^|]* \|", "| Prefijo Jira (jira_prefix) | {{jira_prefix}} |", full)
        result = pbcompletion.check_epic(no_prefix)
        self.assertEqual([p["field"] for p in result["pending"]], ["jira_prefix"])
        self.assertTrue(pbcompletion.ready(result))
        no_owner = no_prefix.replace("| Owner (owner) | Owner de producto |", "| Owner (owner) | {{owner}} |")
        self.assertFalse(pbcompletion.ready(pbcompletion.check_epic(no_owner)))

    def test_table_in_free_text_section_fills_it_like_pb(self):
        text = fill(pbtemplate.load("rfc"))
        start = text.index("## 5. Alternativas Consideradas")
        end = text.index("## 6. Preguntas Abiertas")
        table = "## 5. Alternativas Consideradas\n| Alternativa | Pros | Contras |\n| --- | --- | --- |\n| A | x | y |\n\n"
        self.assertEqual(pbcompletion.predict("rfc", text[:start] + table + text[end:])["percentage"], 100)


class EpicCheckTest(unittest.TestCase):
    def test_epic_errors_for_invalid_values(self):
        packet = ("# Épica E1 — X\n\n## Datos de la épica\n| Campo | Valor |\n| --- | --- |\n"
                  "| Criticidad (criticality) | [SIN DEFINIR] |\n| Fecha de inicio (start_date) | pronto |\n"
                  "| Quarter (quarter) | {{quarter}} |\n\n## Historias\n\n### US-001 — [Backend] API (tarea 1.1)\n"
                  "| Campo | Valor |\n| --- | --- |\n| Story points (story_points) | 4 |\n| Componente (component) | Backend |\n"
                  "| Historia (user_story_text) | Quiero curar |\n\n#### Criterios de aceptación (acceptance_criteria)\n"
                  "- AC1 — devuelve 200\n")
        result = pbcompletion.check_epic(packet)
        self.assertEqual(result["errors"], [
            "criticality: '[SIN DEFINIR]' must be one of Alta, Media, Baja",
            "start_date: 'pronto' must be YYYY-MM-DD",
            "US-001 story_points: 4 is not Fibonacci (1, 2, 3, 5, 8, 13)",
            "US-001 component: 'Backend' must be FE, BE, BO, QA, DEVOPS, INFRA, BFF or AI",
            "US-001 user_story_text: must read 'Como … quiero … para …'",
            "US-001 acceptance_criteria: 'AC1 — devuelve 200' is not Gherkin",
            "US-001 definition_of_ready: must be the 4 fixed Product Brain items",
            "US-001 definition_of_done: must be the 11 fixed Product Brain items with si/no",
        ])
        self.assertEqual(result["total"], 26)


class CheckFileTest(unittest.TestCase):
    def test_missing_and_present(self):
        project = make_project()
        self.assertIsNone(pbcompletion.check_file(project, "prd"))
        write(project, "wow/pb/prd.md", fill(pbtemplate.load("prd")))
        self.assertEqual(pbcompletion.check_file(project, "prd")["percentage"], 100)


class ReviewFixesTest(unittest.TestCase):
    def test_heading_punctuation_is_normalized_like_pb(self):
        text = fill(pbtemplate.load("rfc")).replace("### Definicion del Problema", "### Definición del problema:")
        self.assertEqual(pbcompletion.predict("rfc", text)["percentage"], 100)
        raw = pbtemplate.load("prd").replace("## Vision y Estrategia", "## Visión y Estrategia:")
        self.assertEqual(pbcompletion.predict("prd", raw)["percentage"], 0)

    def test_open_question_row_with_missing_cells_is_partial(self):
        text = fill(pbtemplate.load("prd")).replace("| 1 | dato | Owner de producto | Abierta |",
                                                    "| 1 | dato | Owner de producto | Abierta |\n| 2 | ¿Quién decide? | Owner de producto |")
        result = pbcompletion.predict("prd", text)
        self.assertIn("open_questions", [p["field"] for p in result["pending"]])


if __name__ == "__main__":
    unittest.main()
