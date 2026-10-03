"""wow cite check: every `path:line` a document cites exists and is in range (deterministic, no LLM)."""
from __future__ import annotations

import subprocess
import unittest

from helpers import make_project, run_cli, write
import cites
import contextpack

TEN = "".join(f"line {n}\n" for n in range(1, 11))


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
                   check=True, capture_output=True, text=True)


class ExtractTest(unittest.TestCase):
    def test_citations_in_markdown_and_html(self):
        text = ("See `src/app.py:3` and <code>completion.ts:72-99</code>, also `docs/x.md` (no line) "
                "and `MAIN:30` (an abbreviation) and `x.py:12:9` (column).")
        self.assertEqual(cites.extract(text), [("src/app.py", 3, 3), ("completion.ts", 72, 99), ("x.py", 12, 12)])


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.root = make_project()
        write(self.root, "src/app.py", TEN)
        write(self.root, "deep/nested/completion.ts", TEN)
        write(self.root, "a/dup.ts", TEN)
        write(self.root, "b/dup.ts", TEN + "different\n")

    def test_findings_for_missing_out_of_range_and_ambiguous(self):
        doc = "`src/app.py:3` `src/app.py:9-12` `src/gone.py:1` `completion.ts:4-5` `dup.ts:1`"
        result = cites.check(doc, self.root)
        self.assertEqual(result["checked"], 5)
        self.assertEqual(result["findings"], [
            "src/app.py:9-12: line 12 is past the end (10 lines)",
            "src/gone.py:1: file not found under the root",
            "dup.ts:1: ambiguous name, 2 files match (a/dup.ts, b/dup.ts); cite a longer path",
        ])

    def test_identical_mirrors_are_not_ambiguous(self):
        write(self.root, ".cursor/hooks/hook.sh", TEN)
        write(self.root, ".github/hooks/hook.sh", TEN)
        self.assertEqual(cites.check("`hook.sh:2`", self.root)["findings"], [])

    def test_aliases_expand_abbreviated_paths(self):
        write(self.root, "src/templates/skills/sync/scripts/sync.py", TEN)
        doc = "`SYNC/sync.py:4` and `SYNC/sync.py:40`"
        result = cites.check(doc, self.root, aliases={"SYNC": "src/templates/skills/sync/scripts"})
        self.assertEqual(result["findings"], ["SYNC/sync.py:40: line 40 is past the end (10 lines)"])

    def test_against_a_pinned_commit(self):
        _git(self.root, "init", "-q")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "base")
        sha = subprocess.run(["git", "-C", str(self.root), "rev-parse", "HEAD"], capture_output=True,
                             text=True).stdout.strip()
        write(self.root, "src/app.py", "short\n")  # the working tree moved on; the citation was made at sha
        self.assertEqual(cites.check("`src/app.py:8`", self.root, sha=sha)["findings"], [])
        self.assertEqual(len(cites.check("`src/app.py:8`", self.root)["findings"]), 1)

    def test_cli_codes(self):
        doc = write(self.root, "doc.md", "`src/app.py:3`\n")
        self.assertEqual(run_cli(["cite", "check", str(doc), "--root", str(self.root)])[0], 0)
        write(self.root, "doc.md", "`src/app.py:99`\n")
        code, out, _ = run_cli(["cite", "check", str(doc), "--root", str(self.root)])
        self.assertEqual(code, 1)
        self.assertIn("src/app.py:99: line 99 is past the end", out)
        self.assertEqual(run_cli(["cite", "check", str(self.root / "nope.md"), "--root", str(self.root)])[0], 2)
        write(self.root, "doc.md", "`S/app.py:3`\n")
        self.assertEqual(run_cli(["cite", "check", str(doc), "--root", str(self.root), "--alias", "S=src"])[0], 0)


class ContextPackLineTest(unittest.TestCase):
    def test_context_check_validates_the_line_too(self):
        project = make_project()
        contextpack.scan(project)
        write(project, "README.md", "one\ntwo\n")
        write(project, "wow/context-pack/facts.md", "- C1: el README existe [MEDIDO] (fuente: README.md:2)\n"
                                                    "- C2: dice algo más [MEDIDO] (fuente: README.md:40)\n")
        findings = contextpack.check(project)
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("C2", findings[0])
        self.assertIn("past the end", findings[0])


if __name__ == "__main__":
    unittest.main()
