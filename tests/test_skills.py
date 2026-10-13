import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class SkillTextTest(unittest.TestCase):
    def test_no_skill_sends_users_to_the_artifact_engine(self):
        # Confluence describes an Artifact Engine, but Product Brain's code has none; a skill must not route work to it.
        offenders = [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / "skills").glob("*/SKILL.md"))
                     if "Artifact Engine" in p.read_text(encoding="utf-8")]
        self.assertEqual(offenders, [])

    def test_wow_plan_spells_out_the_manual_scope_change_path(self):
        text = (ROOT / "skills" / "wow-plan" / "SKILL.md").read_text(encoding="utf-8")
        for step in ("PRD", "RFC", "Jira", "/spec-kit.amend", "wow plan freeze --reopen"):
            self.assertIn(step, text)


if __name__ == "__main__":
    unittest.main()
