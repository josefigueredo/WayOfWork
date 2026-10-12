"""Every skill of this repo conforms to the Agent Skills format (https://agentskills.io/specification).

`skillspec.py` is the checker (a stdlib port of the reference validator, see its docstring). The first class proves the
checker itself still bites, with one broken fixture per rule; the second runs it over the real skills and compares the
set of skills with the set `install.sh` links.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT
from skillspec import check_skill, discover, parse_frontmatter

VALID = "---\nname: demo\ndescription: >\n  Does a thing.\n  Use when asked.\nmetadata:\n  owner: team\n---\n\n# Demo\n"


def _skill(tmp: str, front: str, folder: str = "demo") -> Path:
    path = Path(tmp) / folder
    path.mkdir()
    (path / "SKILL.md").write_text(front, encoding="utf-8")
    return path


def _doc(*lines: str) -> str:
    return "---\n" + "\n".join(lines) + "\n---\n\nbody\n"


class CheckerBitesTest(unittest.TestCase):
    def errors(self, front: str, folder: str = "demo") -> list:
        with tempfile.TemporaryDirectory() as tmp:
            return check_skill(_skill(tmp, front, folder))

    def assertRejects(self, front: str, needle: str, folder: str = "demo"):
        errors = self.errors(front, folder)
        self.assertTrue(any(needle in e for e in errors), errors)

    def test_valid_skill_with_folded_block_and_metadata_passes(self):
        self.assertEqual(self.errors(VALID), [])
        self.assertEqual(parse_frontmatter(VALID)["description"], "Does a thing. Use when asked.")

    def test_field_outside_the_spec(self):
        self.assertRejects(_doc("name: demo", "description: x", "version: 1"), "unexpected frontmatter fields: version")

    def test_uppercase_name(self):
        self.assertRejects(_doc("name: Demo", "description: x"), "lowercase", folder="Demo")

    def test_consecutive_hyphens(self):
        self.assertRejects(_doc("name: de--mo", "description: x"), "consecutive hyphens", folder="de--mo")

    def test_hyphen_at_the_edge(self):
        self.assertRejects(_doc("name: -demo", "description: x"), "starts or ends with a hyphen", folder="-demo")

    def test_name_differs_from_folder(self):
        self.assertRejects(_doc("name: other", "description: x"), "does not match 'demo'")

    def test_missing_description(self):
        self.assertRejects(_doc("name: demo"), "missing required field: description")

    def test_description_too_long(self):
        self.assertRejects(_doc("name: demo", "description: " + "a" * 1025), "description is 1025 chars")

    def test_compatibility_too_long(self):
        self.assertRejects(_doc("name: demo", "description: x", "compatibility: " + "a" * 501), "compatibility is 501 chars")

    def test_no_frontmatter(self):
        self.assertRejects("# Demo\n", "no YAML frontmatter")

    def test_name_too_long(self):
        name = "a" * 65
        self.assertRejects(_doc(f"name: {name}", "description: x"), "max 64", folder=name)

    def test_published_name_replaces_the_folder_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = _skill(tmp, _doc("name: demo", "description: x"), folder="clone-1")
            self.assertEqual(check_skill(skill, published_name="demo"), [])
            self.assertTrue(check_skill(skill))


class RepoSkillsTest(unittest.TestCase):
    def test_every_skill_conforms(self):
        skills = discover(ROOT)
        self.assertTrue(skills, "no skills found")
        for skill in skills:
            # install.sh publishes skills/<name>/ under <name>, so the folder rule is the right one here
            self.assertEqual(check_skill(skill, published_name=skill.name), [], str(skill))

    def test_skills_found_are_the_ones_install_sh_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            proc = subprocess.run(["bash", str(ROOT / "install.sh"), "--skills"], capture_output=True, text=True,
                                  env=dict(os.environ, HOME=str(home)))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            linked = sorted(p.name for p in (home / ".agents/skills").iterdir())
        self.assertEqual(linked, sorted(p.name for p in discover(ROOT)))


if __name__ == "__main__":
    unittest.main()
