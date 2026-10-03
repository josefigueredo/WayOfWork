from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from helpers import make_project, write
import manifest
import packets
from test_manifest import valid_doc

SPEC = """# Spec
## User stories
### Story 1: [IRIS-41] Analyst curates a case
Acceptance criteria:
- AC1: the case moves to curated
- AC2: an audit row is written
### Story 2: [IRIS-42] Export
- AC1: CSV is produced
"""


def git_repo_with_change() -> Path:
    repo = make_project()

    def run(*args):
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
                       check=True, capture_output=True, text=True)

    run("init", "-q", "-b", "main")
    write(repo, "app.py", "print('v1')\n")
    run("add", "-A")
    run("commit", "-q", "-m", "base")
    write(repo, "app.py", "print('v2')\n")
    return repo


class StoryPacketTest(unittest.TestCase):
    def test_anchors_from_story_section_and_diff(self):
        project = make_project()
        write(project, "specs/001-x/spec.md", SPEC)
        packet = packets.story_packet(project, "IRIS-41", git_repo_with_change(), "main")
        self.assertEqual(packet["anchors"], {"AC1": "the case moves to curated", "AC2": "an audit row is written"})
        self.assertIn("+print('v2')", packet["body"])

    def test_anchors_in_spec_kit_given_when_then_format(self):
        # The format /spec-kit.sync writes: numbered Given/When/Then with the AC id in trailing parentheses.
        spec = ("### User Story 1 — Auditar ([PLATE-492](https://x.atlassian.net/browse/PLATE-492)) (Priority: P1)\n"
                "**Acceptance Scenarios:**\n\n"
                "1. **Given** los commits fijados, **When** corre el agente, **Then** hay un veredicto por página (AC1)\n"
                "2. **Given** una afirmación sin evidencia, **When** se arma el informe, **Then** queda sin fuente (AC2)\n"
                "### User Story 2 — Corregir ([PLATE-493](https://x.atlassian.net/browse/PLATE-493))\n"
                "1. **Given** el informe, **When** se corrige, **Then** queda corregido (AC1)\n")
        project = make_project()
        write(project, "specs/001-x/spec.md", spec)
        packet = packets.story_packet(project, "PLATE-492", git_repo_with_change(), "main")
        self.assertEqual(packet["anchors"], {
            "AC1": "Given los commits fijados, When corre el agente, Then hay un veredicto por página",
            "AC2": "Given una afirmación sin evidencia, When se arma el informe, Then queda sin fuente"})

    def test_story_without_anchors_raises(self):
        project = make_project()
        write(project, "specs/001-x/spec.md", "### Story 9: [IRIS-49] nothing\n")
        with self.assertRaises(packets.PacketError):
            packets.story_packet(project, "IRIS-49", git_repo_with_change(), "main")

    def test_empty_diff_raises(self):
        project = make_project()
        write(project, "specs/001-x/spec.md", SPEC)
        repo = git_repo_with_change()
        subprocess.run(["git", "-C", str(repo), "checkout", "--", "app.py"], check=True)
        with self.assertRaises(packets.PacketError):
            packets.story_packet(project, "IRIS-41", repo, "main")


GOLDEN = """---
description: Non-negotiable clean-code habits
alwaysApply: false
---

# Clean code (core)

## CORE (read first)

MUST use **intention-revealing** names; MUST NOT rely on cryptic abbreviations.

MUST keep **functions small** and single-purpose.

**Full reference:** [clean-code.md](./clean-code.md)
"""


class StandardsPacketTest(unittest.TestCase):
    def test_golden_rules_are_the_anchors_and_smells_only_warn(self):
        project = make_project()
        repo = git_repo_with_change()
        write(repo, ".cursor/rules/core_clean-code_golden_rules_clean-code.mdc", GOLDEN)
        write(repo, ".cursor/rules/spec-kit-core.mdc", "MUST run /spec-kit.implement\n")  # process rule, not a standard
        packet = packets.standards_packet(project, "IRIS-41", repo, "main")
        self.assertEqual(list(packet["anchors"]), ["G1"])
        self.assertIn("clean-code", packet["anchors"]["G1"])
        self.assertIn("MUST keep **functions small**", packet["anchors"]["G1"])
        self.assertNotIn("spec-kit", " ".join(packet["anchors"].values()))
        self.assertIn("+print('v2')", packet["body"])
        prompt = packets.build_prompt(packet)
        self.assertIn("Speculative Generality", prompt)
        self.assertIn("WARNING", prompt)
        self.assertIn("golden rule overrides", prompt)

    def test_documented_conventions_when_no_golden_rules(self):
        project = make_project()
        repo = git_repo_with_change()
        write(repo, "CONTRIBUTING.md", "Use type hints everywhere.\n")
        packet = packets.standards_packet(project, "E1", repo, "main")
        self.assertEqual(list(packet["anchors"]), ["DOC"])
        self.assertIn("CONTRIBUTING.md", packet["anchors"]["DOC"])
        self.assertIn("Use type hints everywhere.", packet["body"])

    def test_nothing_to_review_against_raises(self):
        with self.assertRaises(packets.PacketError):
            packets.standards_packet(make_project(), "IRIS-41", git_repo_with_change(), "main")


class OtherPacketsTest(unittest.TestCase):
    def test_epic_anchors_from_manifest(self):
        project = make_project()
        manifest.save(project, valid_doc())
        packet = packets.epic_packet(project, "E1", git_repo_with_change(), "main")
        self.assertEqual(packet["anchors"], {"E1.C1": "analysts can curate"})

    def test_readiness_anchors_and_body(self):
        project = make_project()
        manifest.save(project, valid_doc())
        write(project, "wow/plan/PLAN.md", "## Brief\n- Goal: x\n")
        packet = packets.readiness_packet(project)
        self.assertEqual(sorted(packet["anchors"]), ["R1", "R2", "R3", "R4", "R5"])
        self.assertIn("## Brief", packet["body"])
        self.assertIn('"0001-iris-v2"', packet["body"])

    def test_readiness_body_ignores_readiness_state(self):
        project = make_project()
        manifest.save(project, valid_doc())
        before = packets.diff_hash(packets.readiness_packet(project)["body"])
        doc = valid_doc()
        doc["plan"]["readiness"] = {"verdict": "changes_required", "rounds": 1}
        manifest.save(project, doc)
        self.assertEqual(before, packets.diff_hash(packets.readiness_packet(project)["body"]))

    def test_claims_anchor_formats(self):
        project = make_project()
        doc = write(project, "wow/context-pack/facts.md",
                    "C1: auth uses Nucleus profiles [MEDIDO]\n- C2: no API gateway\n**C3**: DynamoDB pk+sk\nnot a claim\n")
        packet = packets.claims_packet(doc, project)
        self.assertEqual(sorted(packet["anchors"]), ["C1", "C2", "C3"])

    def test_prompt_contains_anchors_format_and_body(self):
        project = make_project()
        write(project, "specs/001-x/spec.md", SPEC)
        prompt = packets.build_prompt(packets.story_packet(project, "IRIS-41", git_repo_with_change(), "main"))
        self.assertIn("AC1: the case moves to curated", prompt)
        self.assertIn("VERDICT: APPROVED | CHANGES_REQUIRED", prompt)
        self.assertIn("+print('v2')", prompt)

    def test_diff_hash_is_stable(self):
        self.assertEqual(packets.diff_hash("a"), packets.diff_hash("a"))
        self.assertEqual(len(packets.diff_hash("a")), 16)


if __name__ == "__main__":
    unittest.main()
