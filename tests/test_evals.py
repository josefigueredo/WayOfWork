from __future__ import annotations

import json
import sys
import unittest

from helpers import make_project, run_cli, write
import evals

# Answers by case: the fake reviewer finds which case it got from the content's marker line.
FAKE = """import pathlib, sys
data = sys.stdin.read()
answers = {"case-a": "VERDICT: CHANGES_REQUIRED\\nBLOCKER AC1 app.py:1 — no audit row\\n",
           "case-b": "VERDICT: APPROVED\\n",
           "case-c": "WARNING doc:1 — unclear owner\\n"}
text = "OK" if "Reply with exactly OK" in data else next(v for k, v in answers.items() if k in data)
open(sys.argv[1], "w").write(text)
"""


def dataset(cases):
    return {"schema_version": 1, "name": "basics", "cases": cases}


CASES = [
    {"id": "planted-defect", "set": "story", "anchors": {"AC1": "an audit row is written"},
     "content": "case-a\n+def curate(): pass\n", "expect": {"verdict": "CHANGES_REQUIRED", "blockers": ["AC1"]}},
    {"id": "clean", "set": "story", "anchors": {"AC1": "the case moves to curated"},
     "content": "case-b\n+status = 'curated'\n", "expect": {"verdict": "APPROVED"}},
    {"id": "critique", "set": "critique", "content": "case-c\nWe cache forever.\n", "expect": {"min_warnings": 1}},
]


def project_with_fake():
    project = make_project()
    script = write(project, "fake.py", FAKE)
    spec = {"argv": [sys.executable, str(script), "{out}"], "stdin": True, "output": "file"}
    write(project, ".wow/config.json", json.dumps({"reviewers": ["codex"], "reviewer_commands": {"codex": spec}}))
    return project


class DatasetTest(unittest.TestCase):
    def test_a_dataset_without_cases_or_expectations_is_rejected(self):
        with self.assertRaises(evals.EvalError):
            evals.validate(dataset([]))
        with self.assertRaises(evals.EvalError):
            evals.validate(dataset([{"id": "x", "set": "story", "anchors": {"AC1": "y"}, "content": "z"}]))
        with self.assertRaises(evals.EvalError):
            evals.validate(dataset([{"id": "x", "set": "nope", "content": "z", "expect": {"verdict": "APPROVED"}}]))
        evals.validate(dataset(CASES))

    def test_judging_a_parsed_round(self):
        parsed = {"verdict": "CHANGES_REQUIRED", "blockers": [{"anchor": "AC1"}], "warnings": [], "nits": []}
        self.assertEqual(evals.judge({"verdict": "CHANGES_REQUIRED", "blockers": ["AC1"]}, parsed), [])
        self.assertEqual(evals.judge({"verdict": "APPROVED"}, parsed), ["verdict CHANGES_REQUIRED, expected APPROVED"])
        self.assertEqual(evals.judge({"blockers": ["AC2"]}, parsed), ["no BLOCKER on AC2"])
        self.assertEqual(evals.judge({"min_warnings": 1}, parsed), ["0 warnings, expected at least 1"])
        self.assertEqual(evals.judge({"min_warnings": 1}, parsed, critique=True), [])


class RunTest(unittest.TestCase):
    def test_unparseable_output_or_a_crash_could_not_run(self):
        data = dataset(CASES[:2])
        results = evals.run(data, lambda prompt: "I think it is fine")
        self.assertEqual([r["status"] for r in results], ["could not run", "could not run"])
        self.assertIn("no VERDICT line", results[0]["detail"])

        def boom(prompt):
            raise RuntimeError("codex exited with 1")
        self.assertEqual(evals.run(data, boom)[0]["detail"], "codex exited with 1")


class EvalCommandTest(unittest.TestCase):
    def test_all_cases_pass_and_the_result_is_kept(self):
        project = project_with_fake()
        ds = write(project, "evals/basics.json", json.dumps(dataset(CASES)))
        code, out, _ = run_cli(["eval", "run", str(ds), "--project", str(project)])
        self.assertEqual(code, 0, out)
        self.assertIn("3 passed, 0 failed, 0 could not run (reviewer: codex)", out)
        saved = json.loads(next((project / "harness/evals").glob("*-basics.json")).read_text(encoding="utf-8"))
        self.assertEqual([c["status"] for c in saved["cases"]], ["pass", "pass", "pass"])
        self.assertEqual(saved["reviewer"], "codex")

    def test_a_missed_defect_fails(self):
        project = project_with_fake()
        wrong = dict(CASES[1], expect={"verdict": "CHANGES_REQUIRED", "blockers": ["AC1"]})
        ds = write(project, "evals/basics.json", json.dumps(dataset([wrong])))
        code, out, _ = run_cli(["eval", "run", str(ds), "--project", str(project)])
        self.assertEqual(code, 1)
        self.assertIn("FAIL clean — verdict APPROVED, expected CHANGES_REQUIRED; no BLOCKER on AC1", out)

    def test_no_reviewer_means_could_not_run_never_pass(self):
        project = project_with_fake()
        ds = write(project, "evals/basics.json", json.dumps(dataset(CASES)))
        code, out, err = run_cli(["eval", "run", str(ds), "--reviewer", "no-such-reviewer", "--project",
                                  str(project)])
        self.assertEqual(code, 2)
        self.assertIn("no reviewer available", err)
        self.assertNotIn("passed", out)

    def test_an_invalid_dataset_exits_2(self):
        project = project_with_fake()
        ds = write(project, "evals/bad.json", "{not json")
        self.assertEqual(run_cli(["eval", "run", str(ds), "--project", str(project)])[0], 2)


if __name__ == "__main__":
    unittest.main()
