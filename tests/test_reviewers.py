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

    def test_the_host_that_wrote_never_reviews_itself(self):
        project = make_project()
        cfg = fake_cfg(project, names=("claude", "codex"))
        cfg["reviewer_commands"]["claude"] = cfg["reviewer_commands"]["codex"]
        name, _ = reviewers.pick_reviewer(cfg, project, env={"CLAUDECODE": "1"})
        self.assertEqual(name, "codex")
        name, _ = reviewers.pick_reviewer(cfg, project, env={"CODEX_THREAD_ID": "t1"})
        self.assertEqual(name, "claude")

    def test_nested_hosts_are_all_skipped(self):
        # Environment variables are inherited: codex launched from Claude Code sees both markers, and the env alone
        # cannot tell which one wrote, so neither reviews.
        project = make_project()
        cfg = fake_cfg(project, names=("claude", "codex"))
        cfg["reviewer_commands"]["claude"] = cfg["reviewer_commands"]["codex"]
        with self.assertRaises(reviewers.NoReviewer) as ctx:
            reviewers.pick_reviewer(cfg, project, env={"CLAUDECODE": "1", "CODEX_THREAD_ID": "t1"})
        self.assertIn("skipped as author: claude, codex", str(ctx.exception))

    def test_author_hosts_from_markers_and_wow_host(self):
        self.assertEqual(reviewers.author_hosts({}), set())
        self.assertEqual(reviewers.author_hosts({"CURSOR_AGENT": "1"}), {"cursor-agent"})
        self.assertEqual(reviewers.author_hosts({"GEMINI_CLI": "1"}), {"gemini"})
        self.assertEqual(reviewers.author_hosts({"WOW_HOST": "copilot, gemini"}), {"copilot", "gemini"})

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

    def test_new_defaults_run_read_only_and_headless(self):
        claude = reviewers.command_spec({}, "claude")
        self.assertEqual(claude["argv"][:2], ["claude", "--print"])
        self.assertIn("plan", claude["argv"])
        self.assertTrue(claude["stdin"])
        cursor = reviewers.command_spec({}, "cursor-agent")
        self.assertIn("ask", cursor["argv"])
        self.assertIn("{prompt}", cursor["argv"])
        gemini = reviewers.command_spec({}, "gemini")
        self.assertIn("--approval-mode", gemini["argv"])
        self.assertIn("{prompt}", gemini["argv"])


CODEX_JSON = """import sys
sys.stdin.read()
open(sys.argv[1], "w").write("VERDICT: APPROVED")
print('{"type":"thread.started","thread_id":"t1"}')
print('{"type":"turn.completed","usage":{"input_tokens":16425,"cached_input_tokens":7936,"cache_write_input_tokens":0,"output_tokens":5,"reasoning_output_tokens":2}}')
"""


class UsageCaptureTest(unittest.TestCase):
    def test_codex_json_events_give_the_round_usage_and_the_text_stays_the_same(self):
        project = make_project()
        script = write(project, "fake_codex.py", CODEX_JSON)
        spec = {"argv": [sys.executable, str(script), "{out}"], "stdin": True, "output": "file"}
        text, used = reviewers.run_backend_with_usage(spec, "review", project)
        self.assertEqual(text, "VERDICT: APPROVED")
        self.assertEqual(used, {"input_tokens": 16425, "cached_input_tokens": 7936, "output_tokens": 5,
                                "reasoning_output_tokens": 2})
        self.assertIn("--json", reviewers.DEFAULT_COMMANDS["codex"]["argv"])

    def test_no_json_events_means_no_usage(self):
        spec = {"argv": [sys.executable, "-c", "print('VERDICT: APPROVED')"], "stdin": False, "output": "stdout"}
        self.assertIsNone(reviewers.run_backend_with_usage(spec, "x", make_project())[1])

    def test_codex_model_from_config(self):
        project = make_project()
        cfg = write(project, "config.toml", 'model_provider = "openai"\nmodel = "gpt-6-luna"\nmodel_reasoning_effort = "medium"\n')
        self.assertEqual(reviewers.codex_model(cfg), "gpt-6-luna")
        self.assertIsNone(reviewers.codex_model(project / "missing.toml"))


class CodexOutsideGitTest(unittest.TestCase):
    def test_codex_runs_in_non_git_workspaces(self):
        # Multi-repo umbrellas (a workspace root holding many repos) are not git repositories; without this flag
        # `codex exec` refuses to start and the dry run silently falls back to the next reviewer.
        self.assertIn("--skip-git-repo-check", reviewers.DEFAULT_COMMANDS["codex"]["argv"])


if __name__ == "__main__":
    unittest.main()
