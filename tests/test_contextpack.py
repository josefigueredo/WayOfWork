from __future__ import annotations

import unittest

from helpers import make_project, write
import contextpack


class ScanTest(unittest.TestCase):
    def test_scan_inventories_children_docs_and_creates_skeletons_once(self):
        project = make_project()
        write(project, ".gitmodules", '[submodule "api"]\n\tpath = backend-api\n\turl = x\n')
        write(project, "backend-api/.git", "gitdir: ../.git/modules/api\n")
        write(project, "backend-api/README.md", "# API\n")
        write(project, "backend-api/docs/adr/0001-dynamo.md", "# ADR\n")
        write(project, "mfe/.git/HEAD", "ref: refs/heads/main\n")
        write(project, "wow/context-pack/facts.md", "# mine\n")
        result = contextpack.scan(project)
        self.assertEqual(result["children"], ["backend-api", "mfe"])
        self.assertIn("backend-api/docs/adr/0001-dynamo.md", result["docs"])
        self.assertNotIn("wow/context-pack/facts.md", result["created"])
        self.assertIn("wow/context-pack/pending-owner.md", result["created"])
        self.assertEqual((project / "wow/context-pack/facts.md").read_text(encoding="utf-8"), "# mine\n")
        self.assertIn("backend-api", (project / "wow/context-pack/inventory.md").read_text(encoding="utf-8"))


class CheckTest(unittest.TestCase):
    def test_check_reports_each_problem(self):
        project = make_project()
        write(project, "README.md", "x")
        contextpack.scan(project)
        write(project, "wow/context-pack/facts.md",
              "# Hechos\n"
              "- C1: auth contra Nucleus [MEDIDO] (fuente: README.md:3)\n"
              "- C2: sin tag (fuente: README.md)\n"
              "- C3: sin fuente [MEDIDO]\n"
              "- C4: fuente rota [ESTIMACIÓN] (fuente: missing.py:1)\n"
              "- C5: pendiente [SIN DEFINIR]\n"
              "- texto suelto\n")
        write(project, "wow/context-pack/metrics.md", "- C1: duplicado [MEDIDO] (source: README.md)\n")
        findings = contextpack.check(project)
        self.assertEqual(findings, [
            "facts.md:3: C2 needs a tag [MEDIDO], [ESTIMACIÓN] or [SIN DEFINIR]",
            "facts.md:4: C3 needs a source (fuente: path:line)",
            "facts.md:5: C4 source not found: missing.py",
            "facts.md:7: not a claim (expected '- C<n>: … [TAG] (fuente: …)')",
            "metrics.md:1: duplicate id C1 (first at facts.md:2)",
        ])

    def test_missing_files_are_findings(self):
        self.assertEqual(len(contextpack.check(make_project())), 4)


class SourceScopeTest(unittest.TestCase):
    def test_source_outside_project_is_rejected(self):
        project = make_project()
        contextpack.scan(project)
        outside = project.parent / f"{project.name}-outside.md"
        outside.write_text("x", encoding="utf-8")
        self.addCleanup(outside.unlink)
        write(project, "wow/context-pack/facts.md", f"- C1: x [MEDIDO] (fuente: ../{outside.name}:1)\n")
        self.assertEqual(contextpack.check(project), [f"facts.md:1: C1 source outside the project: ../{outside.name}"])


if __name__ == "__main__":
    unittest.main()
