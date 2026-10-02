"""wow command line entrypoint."""
from __future__ import annotations

import argparse
import datetime as _dt
import shlex
import sys
from pathlib import Path
from typing import List

import json

import config
import exitcodes
import manifest
import packets
import review as review_mod
import reviewers
import runwu
import sk
import snapshot as snapshot_mod
import state as state_mod
import usage as usage_mod
from sources.jira import JiraClient

VERSION = "0.1.0"


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    """ArgumentParser that returns CANNOT_EVALUATE instead of calling sys.exit(2) on bad usage."""

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        sys.stderr.write(f"wow: error: {message}\n")
        raise _UsageError()


def _project(args) -> Path:
    return Path(args.project).resolve()


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cmd_manifest_validate(args) -> int:
    try:
        doc = manifest.load(_project(args))
    except manifest.ManifestError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    errors = manifest.validate(doc)
    for line in errors:
        print(line)
    return exitcodes.FINDINGS if errors else exitcodes.OK


def _cmd_manifest_lint(args) -> int:
    try:
        doc = manifest.load(_project(args))
    except manifest.ManifestError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    errors = manifest.validate(doc)
    if errors:
        for line in errors:
            print(line)
        return exitcodes.FINDINGS
    findings = manifest.lint(doc)
    for line in findings:
        print(line)
    return exitcodes.FINDINGS if findings else exitcodes.OK


def _cmd_plan_init(args) -> int:
    project = _project(args)
    if (project / manifest.MANIFEST_REL).exists():
        sys.stderr.write(f"wow: {manifest.MANIFEST_REL} already exists\n")
        return exitcodes.FINDINGS
    manifest.save(project, manifest.new_manifest(args.plan_id, args.title, _now()[:10]))
    print(f"created {manifest.MANIFEST_REL}")
    return exitcodes.OK


def _cmd_plan_freeze(args) -> int:
    project = _project(args)
    try:
        doc = manifest.load(project)
        keys = manifest.parse_epic_keys(args.epics)
        frozen = manifest.freeze(doc, keys, _now(), reopen_reason=args.reopen)
    except manifest.ManifestError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    except (ValueError, manifest.FrozenError) as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.FINDINGS
    manifest.save(project, frozen)
    print(f"frozen; epics: {frozen['plan']['export']['epics']}")
    return exitcodes.OK


def _jira_for(project: Path):
    creds = config.resolve_jira_credentials(project)
    return JiraClient(creds, timeout=5.0) if creds else None


def _cmd_state(args) -> int:
    project = _project(args)
    try:
        cfg = config.load_config(project)
    except config.ConfigError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    result = state_mod.compute_state(project, cfg, _jira_for(project))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return exitcodes.OK


def _cmd_snapshot(args) -> int:
    project = _project(args)
    try:
        cfg = config.load_config(project)
    except config.ConfigError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    result = state_mod.compute_state(project, cfg, _jira_for(project))
    records = usage_mod.collect(project, cfg)
    snap = snapshot_mod.build(result, snapshot_mod.load_previous(project), _now(), usage=records)
    snapshot_mod.write(project, snap)
    print(f"wrote {snapshot_mod.PROGRESS_REL}")
    for blocker in result["blockers"]:
        print(f"! {blocker}")
    for step in result["next_steps"]:
        print(f"- [{step['where']}] {step['action']} -> {step['command']}")
    return exitcodes.OK


def _cmd_usage(args) -> int:
    project = _project(args)
    try:
        cfg = config.load_config(project)
    except config.ConfigError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    for row in usage_mod.summarize(usage_mod.collect(project, cfg)):
        median = row["median_ms"] if row["median_ms"] is not None else "-"
        print(f"{row['vendor']} {row['model']} count={row['count']} in={row['tokens_in']} "
              f"out={row['tokens_out']} median_ms={median}")
    return exitcodes.OK


def _cmd_sk_cmd(args) -> int:
    project = _project(args)
    try:
        lines = sk.commands_for(args.step, config.load_config(project), epic=args.epic, feature=args.feature)
    except (ValueError, config.ConfigError) as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    for line in lines:
        print(line)
    return exitcodes.OK


def _cmd_sk_status(args) -> int:
    result = sk.status(_project(args), args.feature)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    dirty = result["import_warnings"] or any(f["orphan_tasks"] for f in result["features"])
    return exitcodes.FINDINGS if dirty else exitcodes.OK


def _cmd_run_wu(args) -> int:
    project = _project(args)
    try:
        cfg = config.load_config(project)
    except config.ConfigError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    model = args.model or cfg["models"]["cursor_generate"]
    if args.dry_run:
        print(shlex.join(runwu.build_command(args.wu, model, args.worktree)))
        return exitcodes.OK
    try:
        code, path = runwu.run(project, args.wu, model, epic=args.epic, worktree=args.worktree,
                               timeout=int(cfg.get("run_wu_timeout_s", runwu.DEFAULT_TIMEOUT_S)))
    except FileNotFoundError:
        sys.stderr.write("wow: cursor-agent not found on PATH\n")
        return exitcodes.CANNOT_EVALUATE
    if code == runwu.TIMEOUT_EXIT:
        print("cursor-agent timed out (run_wu_timeout_s in .wow/config.json)")
    print(f"run recorded: {path.relative_to(project)}")
    return exitcodes.OK if code == 0 else exitcodes.FINDINGS


def _cmd_review(args) -> int:
    project = _project(args)
    if not review_mod.safe_ref(args.ref):
        sys.stderr.write(f"wow: unsafe ref {args.ref!r}: use letters, digits, '.', '_' or '-'\n")
        return exitcodes.CANNOT_EVALUATE
    try:
        cfg = config.load_config(project)
        repo = Path(args.repo).resolve() if args.repo else project
        if args.set == "readiness":
            packet = packets.readiness_packet(project)
        elif args.set == "story":
            packet = packets.story_packet(project, args.ref, repo, args.base)
        elif args.set == "epic":
            packet = packets.epic_packet(project, args.ref, repo, args.base)
        else:
            if not args.doc:
                sys.stderr.write("wow: --set claims requires --doc PATH\n")
                return exitcodes.CANNOT_EVALUATE
            packet = packets.claims_packet(Path(args.doc).resolve(), repo)
    except (config.ConfigError, packets.PacketError, manifest.ManifestError) as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE

    ref = args.ref
    summary = review_mod.load_summary(project, ref, args.set)
    dhash = packets.diff_hash(packet["body"])
    action = review_mod.next_action(summary, dhash)
    if action == "done":
        print(f"{ref}: approved")
        return exitcodes.OK
    if action in ("hitl", "wait_for_changes"):
        last = summary["rounds"][-1]
        if action == "hitl":
            print(f"{ref}: hitl after {last['n']} rounds — decide as a human:")
        else:
            print(f"round {last['n']} has open BLOCKERs and the diff did not change; fix them first:")
        for blocker in last["blockers"]:
            print(f"BLOCKER {blocker['anchor']} {blocker['path_line']} — {blocker['text']}")
        return exitcodes.FINDINGS

    try:
        name, spec = reviewers.pick_reviewer(cfg, packet["cwd"])
        text = reviewers.run_backend(spec, packets.build_prompt(packet), packet["cwd"])
    except reviewers.NoReviewer as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    except (reviewers.ReviewerFailed, FileNotFoundError, OSError) as exc:
        sys.stderr.write(f"wow: reviewer failed: {exc}\n")
        return exitcodes.CANNOT_EVALUATE

    number = len(summary["rounds"]) + 1
    raw = project / ".wow" / "reviews" / ref / f"round-{number}.md"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(text, encoding="utf-8")
    parsed = review_mod.parse_verdict(text)
    try:
        summary = review_mod.record_round(summary, parsed, packet["anchors"], dhash)
    except review_mod.ReviewOutputError as exc:
        sys.stderr.write(f"wow: {exc}; raw output kept in {raw.relative_to(project)}\n")
        return exitcodes.CANNOT_EVALUATE
    review_mod.save_summary(project, summary)

    if args.set == "readiness":
        doc = manifest.load(project)
        verdict = {"approved": "approved", "hitl": "hitl"}.get(summary["final"], "changes_required")
        doc["plan"]["readiness"] = {"verdict": verdict, "rounds": len(summary["rounds"])}
        manifest.save(project, doc)

    last = summary["rounds"][-1]
    print(f"round {last['n']}: {last['verdict']} (reviewer: {name})")
    for blocker in last["blockers"]:
        print(f"BLOCKER {blocker['anchor']} {blocker['path_line']} — {blocker['text']}")
    if summary["final"] == "hitl":
        print("escalated to HITL: decide as a human, no new round will open")
    return exitcodes.OK if summary["final"] == "approved" else exitcodes.FINDINGS


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="wow", description="WayOfWork CLI")
    parser.add_argument("--version", action="store_true", help="print the version and exit")
    sub = parser.add_subparsers(dest="command", parser_class=_Parser)

    def with_project(p):
        p.add_argument("--project", default=".", help="project root (default: current directory)")
        return p

    m = sub.add_parser("manifest", help="validate or lint the upstream manifest")
    msub = m.add_subparsers(dest="manifest_command", parser_class=_Parser)
    with_project(msub.add_parser("validate")).set_defaults(handler=_cmd_manifest_validate)
    with_project(msub.add_parser("lint")).set_defaults(handler=_cmd_manifest_lint)

    pl = sub.add_parser("plan", help="create or freeze the upstream plan")
    psub = pl.add_subparsers(dest="plan_command", parser_class=_Parser)
    init = with_project(psub.add_parser("init"))
    init.add_argument("plan_id")
    init.add_argument("--title", required=True)
    init.set_defaults(handler=_cmd_plan_init)
    fr = with_project(psub.add_parser("freeze"))
    fr.add_argument("--epics", required=True, help="EPIC=KEY pairs, comma separated")
    fr.add_argument("--reopen", default=None, help="reason for changing an already recorded epic key")
    fr.set_defaults(handler=_cmd_plan_freeze)

    with_project(sub.add_parser("state", help="print the derived state as JSON")).set_defaults(handler=_cmd_state)
    with_project(sub.add_parser("snapshot", help="write wow/progress.json")).set_defaults(handler=_cmd_snapshot)

    rv = with_project(sub.add_parser("review", help="run an anchored independent review"))
    rv.add_argument("--set", required=True, choices=["readiness", "story", "epic", "claims"])
    rv.add_argument("--ref", required=True, help="plan | Jira story key | epic id | claims doc name")
    rv.add_argument("--repo", default=None, help="repository to diff or to verify claims against")
    rv.add_argument("--base", default="main", help="git base for story/epic diffs (default: main)")
    rv.add_argument("--doc", default=None, help="claims document (required for --set claims)")
    rv.set_defaults(handler=_cmd_review)

    with_project(sub.add_parser("usage", help="summarize LLM usage by vendor and model")).set_defaults(handler=_cmd_usage)

    rw = with_project(sub.add_parser("run-wu", help="run /spec-kit.implement headless and record usage"))
    rw.add_argument("wu")
    rw.add_argument("--model", default=None)
    rw.add_argument("--epic", default=None)
    rw.add_argument("--worktree", action="store_true")
    rw.add_argument("--dry-run", action="store_true")
    rw.set_defaults(handler=_cmd_run_wu)

    skp = sub.add_parser("sk", help="prepare Spec-Kit steps")
    sksub = skp.add_subparsers(dest="sk_command", parser_class=_Parser)
    skc = with_project(sksub.add_parser("cmd"))
    skc.add_argument("step", choices=list(sk.STEPS))
    skc.add_argument("--epic", default=None)
    skc.add_argument("--feature", default=None)
    skc.set_defaults(handler=_cmd_sk_cmd)
    sks = with_project(sksub.add_parser("status"))
    sks.add_argument("--feature", default=None)
    sks.set_defaults(handler=_cmd_sk_status)
    return parser


def main(argv: List[str]) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except _UsageError:
        return exitcodes.CANNOT_EVALUATE
    if args.version:
        print(f"wow {VERSION}")
        return exitcodes.OK
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_usage(sys.stderr)
        return exitcodes.CANNOT_EVALUATE
    return handler(args)
