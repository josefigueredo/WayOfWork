"""A flow's checklist: what wow can verify ticks itself; a manual tick counts only with written evidence."""
from __future__ import annotations

import unittest

from helpers import ROOT  # noqa: F401  (puts wow/ on sys.path)
import checklist
from checklist import Item


class PercentTest(unittest.TestCase):
    def test_not_applicable_items_leave_the_total(self):
        items = [Item("a", "A", "done"), Item("b", "B", "todo"), Item("c", "C", "na")]
        self.assertEqual(checklist.percent(items), 50)

    def test_unverified_counts_as_not_done(self):
        self.assertEqual(checklist.percent([Item("a", "A", "done"), Item("b", "B", "unverified")]), 50)

    def test_nothing_applicable_is_zero(self):
        self.assertEqual(checklist.percent([Item("a", "A", "na")]), 0)


class ManualTest(unittest.TestCase):
    TEXT = ("# x\n\n## Derivado\n\n- [x] A\n\n## Manual\n\nTildá con…\n\n"
            "- [x] Avisar al equipo — evidencia: mensaje en #plate 2026-10-06\n"
            "- [x] Probar en el navegador\n- [ ] Pedir acceso\n")

    def test_a_ticked_item_counts_only_with_evidence(self):
        items = checklist.manual_items(self.TEXT)
        self.assertEqual([(i.label, i.state) for i in items], [
            ("Avisar al equipo", "done"), ("Probar en el navegador", "todo"), ("Pedir acceso", "todo")])
        self.assertEqual(items[0].evidence, "mensaje en #plate 2026-10-06")

    def test_ticked_without_evidence_is_reported(self):
        self.assertEqual(checklist.unproven(self.TEXT), ["Probar en el navegador"])

    def test_the_manual_section_survives_a_rewrite(self):
        kept = checklist.manual_section(self.TEXT)
        self.assertIn("- [ ] Pedir acceso", kept)
        out = checklist.render("Flujo PB", [Item("a", "A", "done")], kept)
        self.assertEqual(checklist.manual_section(out), kept)


class RenderTest(unittest.TestCase):
    def test_marks_and_percent(self):
        out = checklist.render("Flujo SK · PLATE-504", [
            Item("sync", "Sync de la épica", "done", "specs/001/spec.md"),
            Item("disc", "Discovery", "na", "greenfield"),
            Item("jira", "Historias en Done", "unverified", "jira no configurado")], "")
        self.assertIn("Completitud: 50% (1 de 2)", out)
        self.assertIn("- [x] Sync de la épica — specs/001/spec.md", out)
        self.assertIn("- [-] Discovery — no aplica: greenfield", out)
        self.assertIn("- [?] Historias en Done — sin verificar: jira no configurado", out)

    def test_manual_items_count_in_the_percent(self):
        out = checklist.render("Flujo PB", [Item("a", "A", "done")], "- [ ] Pedir acceso")
        self.assertIn("Completitud: 50% (1 de 2)", out)


if __name__ == "__main__":
    unittest.main()
