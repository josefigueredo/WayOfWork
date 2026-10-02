from __future__ import annotations

import json
import subprocess
import unittest

from helpers import make_project
import runwu


def fake_runner(stdout, code=0, seen=None):
    def run(argv, cwd=None, env=None, capture_output=None, text=None):
        if seen is not None:
            seen.update({"argv": argv, "cwd": cwd, "tmpdir": env.get("TMPDIR")})
        return subprocess.CompletedProcess(argv, code, stdout, "stderr secret")
    return run


class RunTest(unittest.TestCase):
    def test_records_numbers_only_and_isolates_tmpdir(self):
        project, seen = make_project(), {}
        payload = json.dumps({"type": "result", "subtype": "success", "is_error": False, "duration_ms": 9123,
                              "result": "THE AGENT ANSWER TEXT", "session_id": "s1",
                              "usage": {"inputTokens": 11861, "outputTokens": 68}})
        code, path = runwu.run(project, "WU-001", "composer-2.5", epic="E1",
                               runner=fake_runner(payload, seen=seen), which=lambda n: "/bin/" + n,
                               now=lambda: "2026-10-02T10:00:00Z")
        self.assertEqual(code, 0)
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved["ref"], "E1/WU-001")
        self.assertEqual(saved["result"]["usage"]["inputTokens"], 11861)
        self.assertNotIn("result", saved["result"])
        self.assertNotIn("THE AGENT ANSWER TEXT", path.read_text(encoding="utf-8"))
        self.assertNotIn("stderr secret", path.read_text(encoding="utf-8"))
        self.assertTrue(seen["tmpdir"])
        self.assertEqual(seen["argv"][:3], ["cursor-agent", "-p", "/spec-kit.implement WU-001 --max-iterations 5"])

    def test_non_json_output_records_null_result(self):
        code, path = runwu.run(make_project(), "WU-002", "composer-2.5", runner=fake_runner("oops", code=1),
                               which=lambda n: "/bin/" + n, now=lambda: "2026-10-02T10:00:00Z")
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual((code, saved["result"], saved["ref"]), (1, None, "WU-002"))

    def test_missing_cursor_agent(self):
        with self.assertRaises(FileNotFoundError):
            runwu.run(make_project(), "WU-1", "m", which=lambda n: None)

    def test_worktree_flag(self):
        self.assertEqual(runwu.build_command("WU-3", "m", True)[-2:], ["--worktree", "wu-WU-3"])


if __name__ == "__main__":
    unittest.main()
