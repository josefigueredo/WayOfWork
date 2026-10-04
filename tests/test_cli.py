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
    def test_dashboard_writes_a_standalone_html_with_fresh_snapshots(self):
        project = make_project()
        write(project, ".wow/config.json", _json.dumps({"github": {"enabled": False}, "usage": {"claude_root": str(project / "none-c"),
                                                                    "codex_root": str(project / "none-x")}}))
        out_file = project / "out" / "resumen.html"
        code, out, _ = run_cli(["dashboard", "--out", str(out_file), "--project", str(project)])
        self.assertEqual(code, 0, out)
        self.assertTrue((project / "wow/progress.json").is_file())  # refreshed, not just read
        html = out_file.read_text(encoding="utf-8")
        block = _re.search(r'<script type="application/json" id="wow-embedded">(.*?)</script>', html, _re.S).group(1)
        [entry] = _json.loads(block)
        self.assertEqual(entry["doc"]["schema_version"], _json.loads((project / "wow/progress.json").read_text())["schema_version"])
        self.assertIn(str(out_file), out)

    def test_snapshot_writes_file_and_grows_history(self):
        project = make_project()
        write(project, ".wow/config.json", _json.dumps({"github": {"enabled": False}, "usage": {"claude_root": str(project / "none-c"),
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
    def test_standards_axis_keeps_its_own_rounds_and_smells_never_block(self):
        from test_packets import GOLDEN, git_repo_with_change
        project, _ = _review_project("VERDICT: CHANGES_REQUIRED\nBLOCKER S9 app.py:1 — Speculative Generality\n")
        repo = git_repo_with_change()
        write(repo, ".cursor/rules/core_clean-code_golden_rules_clean-code.mdc", GOLDEN)
        code, out, _ = run_cli(["review", "--set", "standards", "--ref", "IRIS-41", "--repo", str(repo),
                                "--project", str(project)])
        self.assertEqual(code, 0, out)  # S9 is not an anchor: downgraded to a warning, the round approves
        saved = _json.loads((project / "wow/reviews/IRIS-41.standards.json").read_text(encoding="utf-8"))
        self.assertEqual((saved["anchor_set"], saved["final"]), ("standards", "approved"))
        self.assertFalse((project / "wow/reviews/IRIS-41.json").exists())

    def test_readiness_approved_updates_manifest(self):
        project, _ = _review_project("VERDICT: APPROVED\n")
        code, out, _ = run_cli(["review", "--set", "readiness", "--ref", "plan", "--project", str(project)])
        self.assertEqual(code, 0)
        self.assertIn("round 1: APPROVED (reviewer: codex)", out)
        saved = _json.loads((project / "wow/plan/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["plan"]["readiness"], {"verdict": "approved", "rounds": 1})
        self.assertTrue((project / ".wow/reviews/plan/round-1.md").is_file())

    def test_readiness_rounds_count_the_current_cycle_and_keep_the_manifest_valid(self):
        project, _ = _review_project("VERDICT: APPROVED\n")
        args = ["review", "--set", "readiness", "--ref", "plan", "--project", str(project)]
        for n in range(4):  # four approved cycles: the plan changes after each approval
            write(project, "wow/plan/PLAN.md", f"## Brief\n- Goal: version {n}\n")
            self.assertEqual(run_cli(args)[0], 0)
        saved = _manifest.load(project)
        self.assertEqual(saved["plan"]["readiness"], {"verdict": "approved", "rounds": 1})
        self.assertEqual(_manifest.validate(saved), [])

    def test_an_approved_readiness_repairs_a_manifest_written_with_cumulative_rounds(self):
        project, _ = _review_project("VERDICT: APPROVED\n")
        args = ["review", "--set", "readiness", "--ref", "plan", "--project", str(project)]
        for n in range(4):
            write(project, "wow/plan/PLAN.md", f"## Brief\n- Goal: version {n}\n")
            run_cli(args)
        doc = _manifest.load(project)
        doc["plan"]["readiness"]["rounds"] = 4  # what the a7cca66 build wrote in the IRIS pilot
        _manifest.save(project, doc)
        code, out, _ = run_cli(args)  # unchanged plan: no new round, but the manifest gets the cycle count back
        self.assertEqual((code, out.strip()), (0, "plan: approved"))
        self.assertEqual(_manifest.load(project)["plan"]["readiness"], {"verdict": "approved", "rounds": 1})

    def test_changed_claims_after_approval_get_a_new_round(self):
        project, _ = _review_project("VERDICT: APPROVED\n")
        doc = write(project, "facts.md", "- C1: el motor tiene 46 estados\n")
        args = ["review", "--set", "claims", "--ref", "facts", "--doc", str(doc), "--project", str(project)]
        self.assertIn("round 1: APPROVED", run_cli(args)[1])
        self.assertEqual(run_cli(args)[1].strip(), "facts: approved")  # unchanged: the approval still holds
        write(project, "facts.md", "- C1: el motor tiene 47 estados\n")
        code, out, _ = run_cli(args)
        self.assertEqual(code, 0)
        self.assertIn("round 2: APPROVED", out)

    def test_each_round_records_how_long_it_took(self):
        project, _ = _review_project("VERDICT: APPROVED\n")
        run_cli(["review", "--set", "readiness", "--ref", "plan", "--project", str(project)])
        [usage] = list((project / "harness/reviews").glob("*.json"))
        self.assertIsInstance(_json.loads(usage.read_text(encoding="utf-8"))["duration_ms"], int)

    def test_each_round_records_its_usage_in_the_project(self):
        # Recorded where the review belongs, not where the command ran: codex runs --ephemeral, so its own session
        # log is never written and the usage collector would not see the round otherwise.
        project, _ = _review_project("VERDICT: APPROVED\n")
        run_cli(["review", "--set", "readiness", "--ref", "plan", "--project", str(project)])
        [record_file] = sorted((project / "harness/reviews").glob("*-plan-r1.json"))
        saved = _json.loads(record_file.read_text(encoding="utf-8"))
        self.assertEqual((saved["ref"], saved["set"], saved["round"], saved["reviewer"]), ("plan", "readiness", 1, "codex"))
        self.assertIn("usage", saved)

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

    def test_unsafe_ref_exits_2_and_writes_nothing_outside(self):
        project, _ = _review_project("VERDICT: APPROVED\n")
        code, _, err = run_cli(["review", "--set", "readiness", "--ref", "../../escape", "--project", str(project)])
        self.assertEqual(code, 2)
        self.assertIn("unsafe ref", err)
        self.assertFalse((project.parent / "escape.json").exists())
        self.assertFalse((project / ".wow").joinpath("escape").exists())

    def test_claims_requires_doc(self):
        project, _ = _review_project("VERDICT: APPROVED\n")
        self.assertEqual(run_cli(["review", "--set", "claims", "--ref", "facts", "--project", str(project)])[0], 2)

    def test_decide_records_a_human_verdict_only_after_hitl(self):
        import review as _review
        project = make_project()
        decide = ["review", "--decide", "approved", "--reason", "AC3 did not fire", "--ref", "IRIS-41",
                  "--project", str(project)]
        code, _, err = run_cli(decide)
        self.assertEqual(code, 2)
        self.assertIn("only after HITL", err)
        summary = _review.new_summary("IRIS-41", "story")
        blocked = _review.parse_verdict("VERDICT: CHANGES_REQUIRED\nBLOCKER AC1 a.py:1 — x\n")
        for n in range(3):
            summary = _review.record_round(summary, blocked, {"AC1"}, f"h{n}")
        _review.save_summary(project, summary)
        self.assertEqual(run_cli(decide[:3] + ["--ref", "IRIS-41", "--project", str(project)])[0], 2)  # no reason
        code, out, _ = run_cli(decide)
        self.assertEqual(code, 0)
        saved = _json.loads((project / "wow/reviews/IRIS-41.json").read_text())
        self.assertEqual((saved["final"], saved["decision"]["reason"]), ("approved_by_human", "AC3 did not fire"))
        self.assertIn("approved by a human", out)


class UsageCommandTest(unittest.TestCase):
    def test_usage_prints_cursor_rows_and_snapshot_includes_them(self):
        project = make_project()
        write(project, ".wow/config.json", _json.dumps({"github": {"enabled": False}, "usage": {"claude_root": str(project / "none-c"),
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


class RunWuCommandTest(unittest.TestCase):
    def test_dry_run_prints_command_with_default_model(self):
        code, out, err = run_cli(["run-wu", "WU-008", "--dry-run", "--project", str(make_project())])
        self.assertEqual(code, 0)
        self.assertIn("deprecated", err)
        self.assertIn("cursor-agent -p '/spec-kit.implement WU-008 --max-iterations 5' --model composer-2.5", out)


class SkCommandTest(unittest.TestCase):
    def test_sk_cmd_and_status_codes(self):
        project = make_project()
        code, out, _ = run_cli(["sk", "cmd", "sync", "--epic", "IRIS-40", "--project", str(project)])
        self.assertEqual(code, 0)
        self.assertIn("/spec-kit.sync --epic-key IRIS-40", out)
        self.assertEqual(run_cli(["sk", "cmd", "sync", "--project", str(project)])[0], 2)
        self.assertEqual(run_cli(["sk", "status", "--project", str(project)])[0], 0)
        write(project, ".spec-kit/import_report.md", "⚠ missing AC\n")
        self.assertEqual(run_cli(["sk", "status", "--project", str(project)])[0], 1)

    def test_sk_prep_skill_frontmatter(self):
        text = (ROOT / "skills/wow-sk-prep/SKILL.md").read_text(encoding="utf-8")
        front = _re.match(r"^---\nname: (.+)\ndescription: (.+)\n---\n", text)
        self.assertEqual(front.group(1), "wow-sk-prep")
        self.assertLessEqual(len(text.splitlines()), 80)


class ReviewSkillContractTest(unittest.TestCase):
    def test_review_skill_frontmatter(self):
        text = (ROOT / "skills/wow-review/SKILL.md").read_text(encoding="utf-8")
        front = _re.match(r"^---\nname: (.+)\ndescription: (.+)\n---\n", text)
        self.assertEqual(front.group(1), "wow-review")
        self.assertLessEqual(len(text.splitlines()), 80)



class PackCommandTest(unittest.TestCase):
    def test_pack_epic_writes_and_refuses_second_time(self):
        project = make_project()
        _manifest.save(project, valid_doc())
        args = ["pack", "epic", "--id", "E1", "--project", str(project)]
        code, out, _ = run_cli(args)
        self.assertEqual(code, 0)
        self.assertIn("wrote wow/pb/epic-E1.md", out)
        self.assertTrue((project / "wow/pb/preamble.md").is_file())
        self.assertEqual(run_cli(args)[0], 1)
        self.assertEqual(run_cli(args + ["--force"])[0], 0)

    def test_pack_epic_needs_valid_id_and_manifest(self):
        project = make_project()
        self.assertEqual(run_cli(["pack", "prd", "--project", str(project)])[0], 2)
        _manifest.save(project, valid_doc())
        self.assertEqual(run_cli(["pack", "epic", "--project", str(project)])[0], 2)
        self.assertEqual(run_cli(["pack", "epic", "--id", "E9", "--project", str(project)])[0], 2)


class PbchatAuditCommandTest(unittest.TestCase):
    def test_audit_codes_and_file(self):
        project = make_project()
        write(project, "wow/pb/chats/prd.md", "llega al 100%\n✅ Todo listo.\n")
        code, out, _ = run_cli(["pbchat", "audit", "prd", "--project", str(project)])
        self.assertEqual(code, 1)
        self.assertIn("verdict: changes_required", out)
        self.assertIn("no wow/pb/chats/prd.final.md", out)
        self.assertTrue((project / "wow/pb/chats/prd.audit.json").is_file())
        self.assertEqual(run_cli(["pbchat", "audit", "rfc", "--project", str(project)])[0], 2)
        self.assertEqual(run_cli(["pbchat", "audit", "../x", "--project", str(project)])[0], 2)


class PbchatDeepAuditCommandTest(unittest.TestCase):
    def test_deep_audit_adds_reviewer_inventions(self):
        project, _ = _review_project("VERDICT: CHANGES_REQUIRED\nINVENTION 1 — SLA 99.9% — no está en el contexto\n")
        write(project, "wow/pb/chats/prd.md", "llega al 100%\n")
        code, out, _ = run_cli(["pbchat", "audit", "prd", "--deep", "--project", str(project)])
        self.assertEqual(code, 1)
        saved = _json.loads((project / "wow/pb/chats/prd.audit.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["inventions"][0]["source"], "reviewer")

    def test_deep_audit_without_reviewer_exits_2(self):
        project, _ = _review_project("VERDICT: APPROVED\n")
        write(project, ".wow/config.json", _json.dumps({"reviewers": ["claude"]}))
        write(project, "wow/pb/chats/prd.md", "llega al 100%\n")
        self.assertEqual(run_cli(["pbchat", "audit", "prd", "--deep", "--project", str(project)])[0], 2)
        self.assertFalse((project / "wow/pb/chats/prd.audit.json").exists())


class ContextCommandTest(unittest.TestCase):
    def test_scan_then_check_codes(self):
        project = make_project()
        self.assertEqual(run_cli(["context", "scan", "--project", str(project)])[0], 0)
        self.assertEqual(run_cli(["context", "check", "--project", str(project)])[0], 0)
        write(project, "wow/context-pack/facts.md", "- C1: x [MEDIDO]\n")
        code, out, _ = run_cli(["context", "check", "--project", str(project)])
        self.assertEqual(code, 1)
        self.assertIn("C1 needs a source", out)


class SnapshotGithubDisabledTest(unittest.TestCase):
    def test_disabled_github_is_reported(self):
        project = make_project()
        write(project, ".wow/config.json", _json.dumps({"github": {"enabled": False},
                                                        "usage": {"claude_root": str(project / "c"),
                                                                  "codex_root": str(project / "x")}}))
        self.assertEqual(run_cli(["snapshot", "--project", str(project)])[0], 0)
        saved = _json.loads((project / "wow/progress.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["current"]["sources"]["github"], "disabled")
        self.assertIn("links", saved["current"]["plan"])


import argparse as _argparse  # noqa: E402


class PlanGuardCommandTest(unittest.TestCase):
    def test_guard_codes(self):
        project = make_project()
        self.assertEqual(run_cli(["plan", "guard", "--project", str(project)])[0], 2)
        _manifest.save(project, valid_doc())
        self.assertEqual(run_cli(["plan", "guard", "--project", str(project)])[0], 0)
        run_cli(["plan", "freeze", "--epics", "E1=IRIS-40", "--project", str(project)])
        code, out, _ = run_cli(["plan", "guard", "--project", str(project)])
        self.assertEqual(code, 1)
        self.assertIn("/spec-kit.amend", out)
        self.assertEqual(run_cli(["plan", "guard", "--reopen", "scope", "--project", str(project)])[0], 0)


class AllSkillsContractTest(unittest.TestCase):
    def test_every_skill_is_small_named_and_cites_real_commands(self):
        import cli
        parser = cli.build_parser()
        subs = next(a for a in parser._actions if isinstance(a, _argparse._SubParsersAction)).choices
        names = []
        for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
            text = path.read_text(encoding="utf-8")
            front = _re.match(r"^---\nname: (.+)\ndescription: (.+)\n---\n", text)
            self.assertIsNotNone(front, path)
            self.assertEqual(front.group(1), path.parent.name)
            self.assertLessEqual(len(text.splitlines()), 80, path)
            for command in _re.findall(r"`wow ([a-z-]+)", text):
                self.assertIn(command, subs, f"{path}: wow {command}")
            names.append(path.parent.name)
        self.assertEqual(names, ["wow-context", "wow-guide", "wow-pack", "wow-pb-audit", "wow-plan",
                                 "wow-review", "wow-sk-prep"])


class SnapshotEvidenceTest(unittest.TestCase):
    def test_snapshot_writes_pb_reviews_pricing_and_validates(self):
        import schema as _schema
        project = make_project()
        write(project, ".wow/config.json", _json.dumps({"github": {"enabled": False},
                                                        "usage": {"claude_root": str(project / "c"),
                                                                  "codex_root": str(project / "x")}}))
        write(project, "wow/reviews/plan.json", _json.dumps({"ref": "plan", "anchor_set": "readiness",
                                                             "rounds": [], "final": None}))
        self.assertEqual(run_cli(["snapshot", "--project", str(project)])[0], 0)
        saved = _json.loads((project / "wow/progress.json").read_text(encoding="utf-8"))
        current = saved["current"]
        self.assertEqual(list(current["pb"]), ["prd", "rfc"])
        self.assertEqual(current["reviews"][0]["ref"], "plan")
        self.assertEqual(current["pricing"], {"as_of": None, "per_mtok": {}})
        self.assertEqual(_schema.validate(saved, _schema.load_schema("progress")), [])


class PbManifestCommandTest(unittest.TestCase):
    def test_init_with_mode_and_lint_pb(self):
        project = make_project()
        self.assertEqual(run_cli(["plan", "init", "0007-x", "--title", "X", "--mode", "greenfield",
                                  "--project", str(project)])[0], 0)
        saved = _json.loads((project / "wow/plan/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["plan"]["mode"], "greenfield")
        project2 = make_project()
        _manifest.save(project2, valid_doc())
        code, out, _ = run_cli(["manifest", "lint", "--pb", "--project", str(project2)])
        self.assertEqual(code, 1)
        self.assertIn("plan: no mode", out)


class PackCheckCommandTest(unittest.TestCase):
    def test_check_codes(self):
        import pbtemplate as _pbt
        from pbfill import fill as _fill
        project = make_project()
        self.assertEqual(run_cli(["pack", "check", "prd", "--project", str(project)])[0], 2)
        write(project, "wow/pb/prd.md", _pbt.load("prd"))
        code, out, _ = run_cli(["pack", "check", "prd", "--project", str(project)])
        self.assertEqual(code, 1)
        self.assertIn("predicted completion: 0% (0/49 units)", out)
        write(project, "wow/pb/prd.md", _fill(_pbt.load("prd")))
        self.assertEqual(run_cli(["pack", "check", "prd", "--project", str(project)])[0], 0)
        self.assertEqual(run_cli(["pack", "check", "epic", "--project", str(project)])[0], 2)

    def test_epic_missing_only_jira_prefix_passes_with_an_optional_note(self):
        import re
        import pack as _pack
        from pbfill import fill as _fill
        from test_manifest import pb_ready_doc
        project = make_project()
        text = _fill(_pack.render_epic(pb_ready_doc(), "E1", "0123456789abcdef"))
        text = re.sub(r"\| Prefijo Jira \(jira_prefix\) \| [^|]* \|", "| Prefijo Jira (jira_prefix) | {{jira_prefix}} |", text)
        write(project, "wow/pb/epic-E1.md", text)
        code, out, _ = run_cli(["pack", "check", "epic", "--id", "E1", "--project", str(project)])
        self.assertEqual(code, 0)
        self.assertIn("optional: jira_prefix", out)
        self.assertNotIn("pending: jira_prefix", out)


class ReferencesContractTest(unittest.TestCase):
    def test_prompts_exist_follow_the_packet_and_cite_the_real_discovery_path(self):
        base = ROOT / "skills/wow-pack/references"
        for name in ("brownfield-prd.md", "brownfield-rfc.md", "greenfield-prd.md", "greenfield-rfc.md", "epic.md"):
            text = (base / name).read_text(encoding="utf-8")
            self.assertIn("wow pack check", text, name)
            self.assertNotIn("discovery/architecture.md`", text.replace(".spec-kit/discovery/architecture.md`", ""), name)
            self.assertNotIn("TEMPLATE (fill it)", text, name)
        skill = (ROOT / "skills/wow-pack/SKILL.md").read_text(encoding="utf-8")
        for name in ("brownfield-prd.md", "greenfield-prd.md", "epic.md"):
            self.assertIn(name, skill)


if __name__ == "__main__":
    unittest.main()
