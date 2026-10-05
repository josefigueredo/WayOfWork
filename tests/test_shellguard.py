"""wow hook cursor-shell: Cursor's beforeShellExecution guard against commands that destroy or flood a repo.

IRIS pilot (2026-10-04): the Cursor agent ran `cp -R "$SRC"/. <dest>` with SRC empty, which copied from the filesystem
root, and nothing stopped it. Cursor runs this hook before every shell command (also in cursor-agent) and honours
{"permission": "deny"}; the hook fails open on any internal error.
"""
from __future__ import annotations

import io
import json
import subprocess
import unittest
from unittest import mock

from helpers import make_project, run_cli, write
import cursorhook
import shellguard


class DestructiveCommandTest(unittest.TestCase):
    def test_the_pilot_incident_is_blocked(self):
        reason = shellguard.check('cp -R "$SRC"/. docs/site')
        self.assertIsNotNone(reason)
        self.assertIn("${SRC:?}", reason)

    def test_unguarded_variables_as_a_path_root_are_blocked_for_destructive_commands(self):
        for command in ('rm -rf "$BUILD_DIR"/', "rm -rf $OUT/*", 'mv ${TMP}/ out', 'rsync -a --delete "$A"/ b/',
                        "cd repo && rm -rf $DIST/assets"):
            self.assertIsNotNone(shellguard.check(command), command)

    def test_guarded_or_harmless_variables_pass(self):
        for command in ('cp -R "${SRC:?}"/. docs/site', 'rm -rf "${BUILD_DIR:?missing}"/', 'echo "$HOME/x"',
                        'cp "$FILE" out/', "ls $DIR/", 'rm -f "$TMPFILE"', 'git commit -m "rm -rf $X/ is blocked"'):
            self.assertIsNone(shellguard.check(command), command)

    def test_filesystem_and_home_roots_are_blocked(self):
        for command in ("rm -rf /", "rm -rf /*", "cp -R /. out", "rm -rf ~", "rm -rf ~/", 'rm -rf "$HOME"',
                        "sudo rm -rf / --no-preserve-root"):
            self.assertIsNotNone(shellguard.check(command), command)

    def test_ordinary_commands_pass(self):
        for command in ("rm -rf node_modules", "cp -R src/. build/", "rm -rf ./dist", "npm test", "hugo --minify",
                        "git status", "rm -rf .gocache tmp"):
            self.assertIsNone(shellguard.check(command), command)


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
                   check=True, capture_output=True, text=True)


class CommitSizeTest(unittest.TestCase):
    def repo(self):
        repo = make_project()
        _git(repo, "init", "-q")
        return repo

    def test_a_commit_that_stages_too_many_files_is_blocked(self):
        repo = self.repo()
        for n in range(6):
            write(repo, f"f{n}.txt", "x\n")
        _git(repo, "add", "-A")
        reason = shellguard.check("git commit -m 'site'", cwd=repo, max_files=5)
        self.assertIsNotNone(reason)
        self.assertIn("6 files", reason)

    def test_a_commit_that_stages_too_many_bytes_is_blocked(self):
        repo = self.repo()
        write(repo, "big.bin", "x" * 2048)
        _git(repo, "add", "-A")
        self.assertIn("MB", shellguard.check("git commit -m big", cwd=repo, max_bytes=1024))

    def test_a_normal_commit_passes(self):
        repo = self.repo()
        write(repo, "a.txt", "x\n")
        _git(repo, "add", "-A")
        self.assertIsNone(shellguard.check("git commit -m ok", cwd=repo))


class CliTest(unittest.TestCase):
    def run_hook(self, payload):
        with mock.patch("sys.stdin", io.StringIO(json.dumps(payload))):
            code, out, _ = run_cli(["hook", "cursor-shell"])
        return code, json.loads(out)

    def test_deny_answers_with_messages_for_the_user_and_the_agent(self):
        code, answer = self.run_hook({"hook_event_name": "beforeShellExecution", "command": 'cp -R "$SRC"/. out',
                                      "cwd": str(make_project())})
        self.assertEqual(code, 0)
        self.assertEqual(answer["permission"], "deny")
        self.assertIn("${SRC:?}", answer["agent_message"])
        self.assertTrue(answer["user_message"])

    def test_allow_and_fail_open(self):
        self.assertEqual(self.run_hook({"command": "npm test", "cwd": str(make_project())})[1], {"permission": "allow"})
        with mock.patch("sys.stdin", io.StringIO("not json")):
            code, out, _ = run_cli(["hook", "cursor-shell"])
        self.assertEqual((code, json.loads(out)), (0, {"permission": "allow"}))

    def test_install_adds_the_shell_guard_once(self):
        home = make_project()
        hooks = write(home, "hooks.json", json.dumps({"version": 1, "hooks": {}}))
        for _ in range(2):
            self.assertEqual(run_cli(["hook", "install-cursor", "--hooks-file", str(hooks)])[0], 0)
        saved = json.loads(hooks.read_text(encoding="utf-8"))
        [entry] = saved["hooks"]["beforeShellExecution"]
        self.assertIn("hook cursor-shell", entry["command"])
        self.assertEqual(len(saved["hooks"]["stop"]), 1)


if __name__ == "__main__":
    unittest.main()
