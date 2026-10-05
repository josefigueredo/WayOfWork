from __future__ import annotations

import json
import unittest

from helpers import make_project, run_cli, write
import cursorhook
import usage

STOP = {"hook_event_name": "stop", "conversation_id": "c1", "generation_id": "g1", "model": "auto",
        "model_id": "auto-smart", "input_tokens": 681878, "output_tokens": 1485, "cache_read_tokens": 600000,
        "cache_write_tokens": 12, "status": "completed", "loop_count": 0, "cursor_version": "3.22.12",
        "user_email": "dev@example.com", "transcript_path": "/Users/dev/.cursor/t.jsonl"}


class RecordTurnTest(unittest.TestCase):
    def test_turn_lands_in_the_wow_repo_without_personal_data(self):
        repo = make_project()
        write(repo, "wow/plan/manifest.json", "{}")
        other = make_project()  # a workspace root without wow/ gets nothing
        written = cursorhook.record_turn(dict(STOP, workspace_roots=[str(repo), str(other)]), "2026-10-02T23:39:00Z")
        self.assertEqual(written, [repo / "harness/cursor-turns/2026-10-02.jsonl"])
        [line] = written[0].read_text(encoding="utf-8").splitlines()
        turn = json.loads(line)
        self.assertEqual((turn["model_id"], turn["input_tokens"], turn["cache_read_tokens"], turn["status"]),
                         ("auto-smart", 681878, 600000, "completed"))
        self.assertNotIn("user_email", turn)
        self.assertNotIn("transcript_path", turn)
        self.assertFalse((other / "harness").exists())

    def test_a_child_repo_with_only_wow_sk_records_in_the_workspace_that_holds_the_plan(self):
        # IRIS pilot: Cursor opens the site repo, which carries wow/sk/ for the Spec-Kit drafts; the plan lives
        # in the workspace root above it, and that is where wow reads the turns from.
        workspace = make_project()
        write(workspace, "wow/plan/manifest.json", "{}")
        child = workspace / "docs" / "site"
        write(child, "wow/sk/001-x/plan-draft.md", "x\n")
        written = cursorhook.record_turn(dict(STOP, workspace_roots=[str(child)]), "2026-10-05T01:53:15Z")
        self.assertEqual(written, [workspace / "harness/cursor-turns/2026-10-05.jsonl"])
        self.assertFalse((child / "harness").exists())

    def test_non_stop_events_and_missing_roots_record_nothing(self):
        repo = make_project()
        write(repo, "wow/plan/manifest.json", "{}")
        self.assertEqual(cursorhook.record_turn(dict(STOP, hook_event_name="sessionStart",
                                                     workspace_roots=[str(repo)]), "2026-10-02T23:39:00Z"), [])
        self.assertEqual(cursorhook.record_turn(dict(STOP), "2026-10-02T23:39:00Z"), [])

    def test_usage_reads_the_turns_as_cursor_records(self):
        repo = make_project()
        write(repo, "wow/plan/manifest.json", "{}")
        cursorhook.record_turn(dict(STOP, workspace_roots=[str(repo)]), "2026-10-02T23:39:00Z")
        [record] = usage.cursor_turn_records(repo)
        self.assertEqual((record["vendor"], record["tool"], record["model"], record["scope"], record["source"]),
                         ("cursor", "cursor-ide", "auto-smart", "turn", "cursor-hook"))
        self.assertEqual((record["tokens_in"], record["tokens_out"], record["cache_read"], record["cache_write"]),
                         (681878, 1485, 600000, 12))
        self.assertIn(record, usage.collect(repo, {"usage": {"claude_root": str(repo / "c"), "codex_root": str(repo / "x")}}))


class HookCommandTest(unittest.TestCase):
    def test_stop_command_never_fails_and_answers_empty_json(self):
        import io
        import sys
        old = sys.stdin
        try:
            sys.stdin = io.StringIO("not json")
            code, out, _ = run_cli(["hook", "cursor-stop"])
        finally:
            sys.stdin = old
        self.assertEqual((code, out.strip()), (0, "{}"))

    def test_install_adds_the_stop_hook_once_and_keeps_the_rest(self):
        home = make_project()
        hooks = write(home, "hooks.json", json.dumps({"version": 1, "hooks": {
            "sessionStart": [{"command": "bash herdr.sh session"}]}}))
        for _ in range(2):
            self.assertEqual(run_cli(["hook", "install-cursor", "--hooks-file", str(hooks)])[0], 0)
        saved = json.loads(hooks.read_text(encoding="utf-8"))
        self.assertEqual(saved["hooks"]["sessionStart"], [{"command": "bash herdr.sh session"}])
        [entry] = saved["hooks"]["stop"]
        self.assertIn("hook cursor-stop", entry["command"])


if __name__ == "__main__":
    unittest.main()
