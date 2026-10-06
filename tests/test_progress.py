"""wow progress writes one checklist per flow and a summary the statusline reads in well under a second."""
from __future__ import annotations

import io
import json
import unittest
from unittest import mock

from helpers import make_project, run_cli, write
import config
import flow_sk
import progress
from test_state import FakeJira, project_at_phase_3, summary

CFG = config.DEFAULTS


class WriteTest(unittest.TestCase):
    def test_writes_a_checklist_per_flow_and_the_summary(self):
        p = project_at_phase_3()  # E1 exported as IRIS-40
        flow_sk.register(p, "PLATE-553")
        jira = FakeJira({"IRIS-40": summary("IRIS-40", 2, 0), "PLATE-553": summary("PLATE-553", 1, 0)})
        result = progress.write(p, CFG, jira)
        base = p / "wow" / "checklists"
        self.assertIn("Completitud:", (base / "pb.md").read_text(encoding="utf-8"))
        self.assertTrue((base / "sk-IRIS-40.md").is_file())
        self.assertTrue((base / "sk-PLATE-553.md").is_file())
        saved = json.loads((base / "progress.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, result)
        self.assertEqual(sorted(saved["sk"]), ["IRIS-40", "PLATE-553"])
        self.assertTrue(0 < saved["pb"]["percent"] < 100)

    def test_jira_is_read_once_per_epic(self):
        # Minor 5: flow_pb and flow_sk each asked for the same summary; with Jira down that doubled the wait.
        p = project_at_phase_3()
        jira = FakeJira({"IRIS-40": summary("IRIS-40", 2, 0)})
        calls = []
        real = jira.epic_summary
        jira.epic_summary = lambda key: calls.append(key) or real(key)
        progress.write(p, CFG, jira)
        self.assertEqual(calls, ["IRIS-40"])

    def test_the_manual_section_survives_and_unproven_ticks_are_listed(self):
        p = project_at_phase_3()
        progress.write(p, CFG, None)
        pb = p / "wow" / "checklists" / "pb.md"
        pb.write_text(pb.read_text(encoding="utf-8") + "- [x] Avisar al equipo\n- [x] Demo — evidencia: grabación\n",
                      encoding="utf-8")
        result = progress.write(p, CFG, None)
        text = pb.read_text(encoding="utf-8")
        self.assertIn("- [x] Avisar al equipo", text)
        self.assertIn("- [x] Demo — evidencia: grabación", text)
        self.assertEqual(result["manual_without_evidence"], ["pb: Avisar al equipo"])


class LineTest(unittest.TestCase):
    def test_from_a_subfolder_of_the_project(self):
        p = project_at_phase_3()
        flow_sk.register(p, "PLATE-553")
        progress.write(p, CFG, None)
        sub = write(p, "src/app/main.py", "").parent
        line = progress.line(sub)
        self.assertRegex(line, r"^PB \d+% · SK IRIS-40 \d+% · SK PLATE-553 \d+%$")

    def test_outside_a_wow_project_it_is_empty(self):
        self.assertEqual(progress.line(make_project()), "")

    def test_the_cli_never_fails_the_statusline(self):
        for stdin in ("not json", json.dumps({"workspace": {"current_dir": str(make_project())}})):
            with mock.patch("sys.stdin", io.StringIO(stdin)):
                code, out, err = run_cli(["progress", "--line"])
            self.assertEqual((code, out.strip(), err), (0, "", ""))

    def test_an_interactive_terminal_is_never_read(self):
        # Minor 6: run by hand, --line waited on the keyboard; with a tty it uses the current folder.
        class Tty(io.StringIO):
            def isatty(self):
                return True

            def read(self, *a):
                raise AssertionError("read a tty")
        p = project_at_phase_3()
        progress.write(p, CFG, None)
        with mock.patch("sys.stdin", Tty()), mock.patch("os.getcwd", return_value=str(p)):
            code, out, _ = run_cli(["progress", "--line"])
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("PB "))

    def test_the_cli_prints_the_line_for_the_workspace(self):
        p = project_at_phase_3()
        progress.write(p, CFG, None)
        with mock.patch("sys.stdin", io.StringIO(json.dumps({"workspace": {"current_dir": str(p)}}))):
            code, out, _ = run_cli(["progress", "--line"])
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("PB "))


class CliTest(unittest.TestCase):
    def test_progress_prints_each_flow_and_what_is_left(self):
        p = project_at_phase_3()
        code, out, _ = run_cli(["progress", "--project", str(p)])
        self.assertEqual(code, 0)
        self.assertRegex(out, r"Flujo PB\s+\d+%")
        self.assertIn("[ ] Chat PRD cerrado y auditado", out)

    def test_sk_start_rejects_a_malformed_key(self):
        code, _, err = run_cli(["sk", "start", "plate-553", "--project", str(make_project())])
        self.assertEqual(code, 2)
        self.assertIn("not a Jira key", err)

    def test_sk_start_registers_once(self):
        p = make_project()
        self.assertIn("tracking PLATE-553", run_cli(["sk", "start", "PLATE-553", "--project", str(p)])[1])
        self.assertIn("already tracked PLATE-553", run_cli(["sk", "start", "PLATE-553", "--project", str(p)])[1])


if __name__ == "__main__":
    unittest.main()
