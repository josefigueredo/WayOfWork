"""wow sk run sends Spec-Kit commands to Cursor through run-in-cursor; /spec-kit.sync-status stays in Cursor."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

from helpers import make_project, run_cli, write
import skrun


class RefuseTest(unittest.TestCase):
    def test_sync_status_is_for_cursor_only(self):
        for command in ("/spec-kit.sync-status specs/001-x", "  /SPEC-KIT.SYNC-STATUS"):
            self.assertIn("run it in Cursor", skrun.refuse(command))

    def test_only_spec_kit_commands(self):
        self.assertIn("/spec-kit.", skrun.refuse("borrá todo"))
        self.assertIsNone(skrun.refuse("/spec-kit.plan Use wow/sk/001/plan-draft.md"))


class ArgvTest(unittest.TestCase):
    def test_run_goes_through_ric_with_the_deny_rule(self):
        p, ric = make_project(), make_project() / "ric.py"
        ric.write_text("", encoding="utf-8")
        with mock.patch.dict(os.environ, {"WOW_RIC": str(ric)}):
            self.assertEqual(skrun.argv("run", ["/spec-kit.plan x"], p), [
                sys.executable, str(ric), "run", "--workspace", str(p), "--deny", r"spec-kit\.sync-status",
                "/spec-kit.plan x"])
            self.assertEqual(skrun.argv("quit", ["ric-plan-101500"], p),
                             [sys.executable, str(ric), "quit", "ric-plan-101500", "--workspace", str(p)])

    def test_without_run_in_cursor_it_says_how_to_install_it(self):
        with mock.patch.dict(os.environ, {"WOW_RIC": str(make_project() / "missing" / "ric.py")}):
            code, _, err = run_cli(["sk", "run", "/spec-kit.plan", "--project", str(make_project())])
        self.assertEqual(code, 2)
        self.assertIn("install run-in-cursor", err)

    def test_the_cli_refuses_sync_status_before_calling_ric(self):
        with mock.patch("subprocess.run") as called:
            code, _, err = run_cli(["sk", "run", "/spec-kit.sync-status specs/x", "--project", str(make_project())])
        self.assertEqual(code, 1)
        self.assertIn("run it in Cursor", err)
        called.assert_not_called()


if __name__ == "__main__":
    unittest.main()
