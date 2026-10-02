from __future__ import annotations

import subprocess
import sys
import unittest

from helpers import ROOT, run_cli


class VersionTest(unittest.TestCase):
    def test_version_flag_prints_version_and_exits_ok(self):
        code, out, _ = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "wow 0.1.0")

    def test_unknown_subcommand_exits_cannot_evaluate(self):
        code, _, err = run_cli(["nope"])
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_entrypoint_script_runs(self):
        proc = subprocess.run([sys.executable, str(ROOT / "wow" / "wow"), "--version"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "wow 0.1.0")


import json as _json  # noqa: E402

from helpers import make_project, write  # noqa: E402
import manifest as _manifest  # noqa: E402
from test_manifest import valid_doc  # noqa: E402


class ManifestCommandsTest(unittest.TestCase):
    def test_validate_missing_manifest_exits_2(self):
        code, _, err = run_cli(["manifest", "validate", "--project", str(make_project())])
        self.assertEqual(code, 2)
        self.assertIn("manifest not found", err)

    def test_validate_invalid_json_exits_2_without_traceback(self):
        project = make_project()
        write(project, "wow/plan/manifest.json", "{bad")
        code, _, err = run_cli(["manifest", "validate", "--project", str(project)])
        self.assertEqual(code, 2)
        self.assertNotIn("Traceback", err)

    def test_validate_and_lint_codes(self):
        project = make_project()
        _manifest.save(project, valid_doc())
        self.assertEqual(run_cli(["manifest", "validate", "--project", str(project)])[0], 0)
        self.assertEqual(run_cli(["manifest", "lint", "--project", str(project)])[0], 0)
        doc = valid_doc()
        doc["epics"][0]["tasks"][0]["labels"] = []
        _manifest.save(project, doc)
        code, out, _ = run_cli(["manifest", "lint", "--project", str(project)])
        self.assertEqual(code, 1)
        self.assertIn("E1/1.1: no labels", out)

    def test_plan_init_refuses_existing(self):
        project = make_project()
        self.assertEqual(run_cli(["plan", "init", "0001-demo", "--title", "Demo", "--project", str(project)])[0], 0)
        self.assertEqual(run_cli(["plan", "init", "0001-demo", "--title", "Demo", "--project", str(project)])[0], 1)

    def test_plan_freeze_records_keys(self):
        project = make_project()
        _manifest.save(project, valid_doc())
        code, _, _ = run_cli(["plan", "freeze", "--epics", "E1=IRIS-40", "--project", str(project)])
        self.assertEqual(code, 0)
        saved = _json.loads((project / "wow/plan/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["plan"]["export"]["epics"], {"E1": "IRIS-40"})
        self.assertTrue(saved["plan"]["export"]["frozen"])

    def test_plan_freeze_changing_recorded_key_needs_reopen(self):
        project = make_project()
        _manifest.save(project, valid_doc())
        run_cli(["plan", "freeze", "--epics", "E1=IRIS-40", "--project", str(project)])
        code, _, err = run_cli(["plan", "freeze", "--epics", "E1=IRIS-99", "--project", str(project)])
        self.assertEqual(code, 1)
        self.assertIn("--reopen", err)
        code, _, _ = run_cli(["plan", "freeze", "--epics", "E1=IRIS-99", "--reopen", "wrong key",
                              "--project", str(project)])
        self.assertEqual(code, 0)
        saved = _json.loads((project / "wow/plan/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["plan"]["export"]["epics"], {"E1": "IRIS-99"})


class StateCommandTest(unittest.TestCase):
    def test_state_on_fresh_project_prints_json_and_exits_ok(self):
        code, out, _ = run_cli(["state", "--project", str(make_project())])
        self.assertEqual(code, 0)
        self.assertEqual(_json.loads(out)["plan"]["phase"], 0)

    def test_state_with_invalid_config_exits_2(self):
        project = make_project()
        write(project, ".wow/config.json", "{bad")
        self.assertEqual(run_cli(["state", "--project", str(project)])[0], 2)

    def test_state_output_never_contains_token(self):
        project = make_project()
        write(project, ".env.local", "IC_JIRA_BASE_URL=http://127.0.0.1:9\nIC_JIRA_USER_EMAIL=a@b.c\n"
                                     "IC_JIRA_API_TOKEN=tok-SECRET-777\n")
        code, out, err = run_cli(["state", "--project", str(project)])
        self.assertEqual(code, 0)
        self.assertNotIn("tok-SECRET-777", out + err)


class SnapshotCommandTest(unittest.TestCase):
    def test_snapshot_writes_file_and_grows_history(self):
        project = make_project()
        write(project, ".wow/config.json", _json.dumps({"usage": {"claude_root": str(project / "none-c"),
                                                                    "codex_root": str(project / "none-x")}}))
        code, out, _ = run_cli(["snapshot", "--project", str(project)])
        self.assertEqual(code, 0)
        self.assertIn("wrote wow/progress.json", out)
        self.assertIn("build the context pack", out)
        run_cli(["snapshot", "--project", str(project)])
        saved = _json.loads((project / "wow/progress.json").read_text(encoding="utf-8"))
        self.assertEqual(len(saved["history"]), 2)


import re as _re  # noqa: E402


class SkillContractTest(unittest.TestCase):
    def test_guide_skill_frontmatter_and_commands_exist(self):
        text = (ROOT / "skills/wow-guide/SKILL.md").read_text(encoding="utf-8")
        front = _re.match(r"^---\nname: (.+)\ndescription: (.+)\n---\n", text)
        self.assertIsNotNone(front)
        self.assertEqual(front.group(1), "wow-guide")
        self.assertLessEqual(len(text.splitlines()), 80)
        for command in _re.findall(r"`wow ([a-z]+)", text):
            self.assertIn(command, {"snapshot", "state"})

    def test_install_script_is_executable(self):
        import os
        self.assertTrue(os.access(ROOT / "install.sh", os.X_OK))


import sys as _sys  # noqa: E402

_FAKE_REVIEWER = """import sys, pathlib
data = sys.stdin.read()
out = sys.argv[1]
answer = pathlib.Path(sys.argv[2]).read_text()
open(out, "w").write("OK" if "Reply with exactly OK" in data else answer)
"""


def _review_project(answer: str):
    project = make_project()
    script = write(project, "fake_reviewer.py", _FAKE_REVIEWER)
    answer_file = write(project, "answer.txt", answer)
    spec = {"argv": [_sys.executable, str(script), "{out}", str(answer_file)], "stdin": True, "output": "file"}
    write(project, ".wow/config.json", _json.dumps({"reviewers": ["codex"], "reviewer_commands": {"codex": spec}}))
    _manifest.save(project, valid_doc())
    write(project, "wow/plan/PLAN.md", "## Brief\n- Goal: x\n")
    return project, answer_file


class ReviewCommandTest(unittest.TestCase):
    def test_readiness_approved_updates_manifest(self):
        project, _ = _review_project("VERDICT: APPROVED\n")
        code, out, _ = run_cli(["review", "--set", "readiness", "--ref", "plan", "--project", str(project)])
        self.assertEqual(code, 0)
        self.assertIn("round 1: APPROVED (reviewer: codex)", out)
        saved = _json.loads((project / "wow/plan/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["plan"]["readiness"], {"verdict": "approved", "rounds": 1})
        self.assertTrue((project / ".wow/reviews/plan/round-1.md").is_file())

    def test_blocker_then_same_diff_waits(self):
        project, _ = _review_project("VERDICT: CHANGES_REQUIRED\nBLOCKER R1 manifest.json:1 — task 1.1 has no AC\n")
        args = ["review", "--set", "readiness", "--ref", "plan", "--project", str(project)]
        code, out, _ = run_cli(args)
        self.assertEqual(code, 1)
        self.assertIn("BLOCKER R1", out)
        code, out, _ = run_cli(args)
        self.assertEqual(code, 1)
        self.assertIn("round 1 has open BLOCKERs and the diff did not change", out)

    def test_unparseable_output_exits_2_without_recording(self):
        project, _ = _review_project("I think it is fine")
        code, _, err = run_cli(["review", "--set", "readiness", "--ref", "plan", "--project", str(project)])
        self.assertEqual(code, 2)
        self.assertIn("VERDICT", err)
        self.assertFalse((project / "wow/reviews/plan.json").exists())

    def test_no_reviewer_exits_2(self):
        project, _ = _review_project("VERDICT: APPROVED\n")
        write(project, ".wow/config.json", _json.dumps({"reviewers": ["claude"]}))
        code, _, err = run_cli(["review", "--set", "readiness", "--ref", "plan", "--project", str(project)])
        self.assertEqual(code, 2)
        self.assertIn("no reviewer available", err)

    def test_claims_requires_doc(self):
        project, _ = _review_project("VERDICT: APPROVED\n")
        self.assertEqual(run_cli(["review", "--set", "claims", "--ref", "facts", "--project", str(project)])[0], 2)


class UsageCommandTest(unittest.TestCase):
    def test_usage_prints_cursor_rows_and_snapshot_includes_them(self):
        project = make_project()
        write(project, ".wow/config.json", _json.dumps({"usage": {"claude_root": str(project / "none-c"),
                                                                    "codex_root": str(project / "none-x")}}))
        write(project, "harness/runs/WU-001-1.json", _json.dumps({
            "schema_version": 1, "work_unit": "WU-001", "ref": "WU-001", "model": "composer-2.5",
            "started_at": "2026-10-01T10:00:00Z", "ended_at": "2026-10-01T10:01:00Z", "exit_code": 0,
            "result": {"duration_ms": 60000, "usage": {"inputTokens": 1000, "outputTokens": 50}}}))
        code, out, _ = run_cli(["usage", "--project", str(project)])
        self.assertEqual(code, 0)
        self.assertIn("cursor composer-2.5 count=1 in=1000 out=50 median_ms=60000", out)
        run_cli(["snapshot", "--project", str(project)])
        saved = _json.loads((project / "wow/progress.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["usage"][0]["model"], "composer-2.5")


class ReviewSkillContractTest(unittest.TestCase):
    def test_review_skill_frontmatter(self):
        text = (ROOT / "skills/wow-review/SKILL.md").read_text(encoding="utf-8")
        front = _re.match(r"^---\nname: (.+)\ndescription: (.+)\n---\n", text)
        self.assertEqual(front.group(1), "wow-review")
        self.assertLessEqual(len(text.splitlines()), 80)


if __name__ == "__main__":
    unittest.main()
