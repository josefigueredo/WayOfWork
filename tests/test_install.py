"""install.sh: the CLI on PATH and the skills where Claude Code and Codex look for them."""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT

SKILLS = sorted(p.name for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").is_file())


def _install(home: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, HOME=str(home))
    return subprocess.run(["bash", str(ROOT / "install.sh"), *args], capture_output=True, text=True, env=env)


class InstallTest(unittest.TestCase):
    def test_skills_are_linked_for_claude_and_codex_through_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            proc = _install(home, "--skills")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((home / ".local/bin/wow").is_symlink())
            for name in SKILLS:
                shared = home / ".agents/skills" / name
                self.assertEqual(shared.resolve(), (ROOT / "skills" / name).resolve())
                for host in (".claude/skills", ".codex/skills"):
                    link = home / host / name
                    self.assertTrue(link.is_symlink(), link)
                    self.assertEqual(os.readlink(link), f"../../.agents/skills/{name}")
                    self.assertTrue((link / "SKILL.md").is_file())
            self.assertEqual(_install(home, "--skills").returncode, 0)  # idempotent

    def test_never_replaces_a_real_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            mine = home / ".claude/skills" / SKILLS[0]
            mine.mkdir(parents=True)
            (mine / "SKILL.md").write_text("mine\n", encoding="utf-8")
            proc = _install(home, "--skills")
            self.assertEqual(proc.returncode, 1)
            self.assertIn(str(mine), proc.stdout + proc.stderr)
            self.assertEqual((mine / "SKILL.md").read_text(encoding="utf-8"), "mine\n")

    def test_without_skills_flag_only_the_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self.assertEqual(_install(home).returncode, 0)
            self.assertFalse((home / ".claude/skills").exists())


if __name__ == "__main__":
    unittest.main()
