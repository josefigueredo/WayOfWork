from __future__ import annotations

import sys
import unittest

from helpers import make_project, write
import reviewers

FAKE = """import sys
data = sys.stdin.read()
out = sys.argv[1]
text = "OK" if "Reply with exactly OK" in data else "VERDICT: APPROVED"
open(out, "w").write(text)
"""


def fake_cfg(project, names=("codex",)):
    script = write(project, "fake_reviewer.py", FAKE)
    spec = {"argv": [sys.executable, str(script), "{out}"], "stdin": True, "output": "file"}
    return {"reviewers": list(names), "reviewer_commands": {"codex": spec}}


class BackendTest(unittest.TestCase):
    def test_run_backend_reads_output_file(self):
        project = make_project()
        spec = reviewers.command_spec(fake_cfg(project), "codex")
        self.assertEqual(reviewers.run_backend(spec, "review this", project).strip(), "VERDICT: APPROVED")

    def test_stdout_backend_with_prompt_placeholder(self):
        spec = {"argv": [sys.executable, "-c", "import sys; print(sys.argv[1].upper())", "{prompt}"],
                "stdin": False, "output": "stdout"}
        self.assertEqual(reviewers.run_backend(spec, "ok", make_project()).strip(), "OK")

    def test_missing_executable_and_failure(self):
        with self.assertRaises(FileNotFoundError):
            reviewers.run_backend({"argv": ["no-such-reviewer-cli"], "stdin": False, "output": "stdout"}, "x",
                                  make_project())
        failing = {"argv": [sys.executable, "-c", "import sys; sys.exit(3)"], "stdin": False, "output": "stdout"}
        with self.assertRaises(reviewers.ReviewerFailed):
            reviewers.run_backend(failing, "x", make_project())


class PickTest(unittest.TestCase):
    def test_picks_first_with_ok_dry_run(self):
        project = make_project()
        name, _ = reviewers.pick_reviewer(fake_cfg(project), project)
        self.assertEqual(name, "codex")

    def test_excluded_names_are_never_used(self):
        project = make_project()
        cfg = fake_cfg(project, names=("claude", "cursor"))
        cfg["reviewer_commands"]["claude"] = cfg["reviewer_commands"]["codex"]
        with self.assertRaises(reviewers.NoReviewer):
            reviewers.pick_reviewer(cfg, project)

    def test_no_reviewer_lists_tried_names(self):
        cfg = {"reviewers": ["codex"], "reviewer_commands": {
            "codex": {"argv": ["no-such-reviewer-cli"], "stdin": False, "output": "stdout"}}}
        with self.assertRaises(reviewers.NoReviewer) as ctx:
            reviewers.pick_reviewer(cfg, make_project())
        self.assertIn("codex", str(ctx.exception))

    def test_defaults_exist_for_codex_and_copilot(self):
        self.assertIn("{out}", reviewers.command_spec({}, "codex")["argv"])
        self.assertIn("{prompt}", reviewers.command_spec({}, "copilot")["argv"])
        self.assertIsNone(reviewers.command_spec({}, "unknown"))


if __name__ == "__main__":
    unittest.main()
