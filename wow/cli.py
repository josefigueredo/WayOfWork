"""wow command line entrypoint."""
from __future__ import annotations

import argparse
import datetime as _dt
import shlex
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import json

import cites
import estimate
import closing
import jirafields
import jiralog
import shellguard
import config
import contextpack
import evidence
import exitcodes
import flow_sk
import links
import manifest
import pack
import packets
import pbcompletion
import pbaudit
import progress as progress_mod
import refs
import review as review_mod
import reviews
import reviewers
import runwu
import sk
import skrun
import snapshot as snapshot_mod
import state as state_mod
import usage as usage_mod
from sources import SourceUnavailable, github
from sources import repo as repo_src
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
    if getattr(args, "pb", False):
        findings += manifest.pb_lint(doc)
        findings += _jira_component_findings(_project(args), doc)
    for line in findings:
        print(line)
    return exitcodes.FINDINGS if findings else exitcodes.OK


def _cmd_plan_init(args) -> int:
    project = _project(args)
    if (project / manifest.MANIFEST_REL).exists():
        sys.stderr.write(f"wow: {manifest.MANIFEST_REL} already exists\n")
        return exitcodes.FINDINGS
    manifest.save(project, manifest.new_manifest(args.plan_id, args.title, _now()[:10], mode=args.mode))
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


def _cmd_plan_guard(args) -> int:
    try:
        doc = manifest.load(_project(args))
    except manifest.ManifestError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    try:
        manifest.ensure_writable(doc, args.reopen)
    except manifest.FrozenError as exc:
        print(str(exc))
        return exitcodes.FINDINGS
    print("writable")
    return exitcodes.OK


def _jira_for(project: Path, command: Optional[str] = None):
    """A Jira client; with `command`, every write it makes is logged in harness/jira-writes.jsonl (wow/jiralog.py)."""
    creds = config.resolve_jira_credentials(project)
    if not creds:
        return None
    return JiraClient(creds, timeout=5.0, journal=jiralog.journal(project, command) if command else None)


def _jira_component_findings(project: Path, doc: dict) -> list:
    """Components the Jira project lacks make Product Brain's export drop component, points and priority."""
    creds = config.resolve_jira_credentials(project)
    key = jirafields.project_key(doc, creds.project_key if creds else None)
    if creds is None or key is None:
        sys.stderr.write("wow: components not checked against Jira (no credentials or no project key)\n")
        return []
    try:
        return jirafields.component_findings(doc, JiraClient(creds, timeout=5.0).project_components(key), key)
    except SourceUnavailable as exc:
        sys.stderr.write(f"wow: components not checked against Jira: {exc}\n")
        return []


def _cmd_jira_fix_fields(args) -> int:
    project = _project(args)
    creds = config.resolve_jira_credentials(project)
    # The field list of a large Jira (3000+ fields) does not fit the 5 s the quick reads use.
    jira = JiraClient(creds, journal=jiralog.journal(project, f"jira fix-fields --epic {args.epic}")) if creds else None
    if jira is None:
        sys.stderr.write("wow: Jira credentials not found (IC_JIRA_BASE_URL, IC_JIRA_USER_EMAIL, IC_JIRA_API_TOKEN)\n")
        return exitcodes.CANNOT_EVALUATE
    try:
        result = jirafields.plan(project, args.epic, jira)
    except (manifest.ManifestError, SourceUnavailable) as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    for blocker in result["blockers"]:
        print(f"blocked: {blocker}")
    if result["blockers"]:
        return exitcodes.FINDINGS
    for line in result["unmatched"]:
        print(f"unmatched: {line}")
    for change in result["changes"]:
        shown = {k: (v["name"] if isinstance(v, dict) else [c.get("name", c) if isinstance(c, dict) else c for c in v]
                     if isinstance(v, list) else v) for k, v in change["fields"].items()}
        print(f"{change['key']} (task {change['task']}): {shown or 'nothing to set'}")
        for note in change["skipped"]:
            print(f"  skipped: {note}")
    writable = [c for c in result["changes"] if c["fields"]]
    print(f"{result['key']}: {len(writable)} stor{'y' if len(writable) == 1 else 'ies'} to fix")
    if not args.apply:
        jirafields.record_check(project, result)  # what the dry run measured feeds wow progress
        print("dry run: nothing changed; --apply writes these fields in Jira")
        return exitcodes.OK
    errors = jirafields.apply(result, jira)
    if not errors:
        jirafields.record_check(project, dict(result, changes=[]))
    for error in errors:
        print(f"error: {error}")
    if not errors:
        print(f"updated {len(writable)} issues")
    return exitcodes.FINDINGS if errors else exitcodes.OK


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


def _github_prs(project: Path, cfg: dict):
    if not (cfg.get("github") or {}).get("enabled", True):
        return [], "disabled"
    prs, errors, ok = [], [], 0
    dirs = ([project] if (project / ".git").exists() else []) + [project / p for p in repo_src.child_repos(project)]
    if not dirs:
        return [], "no git repositories found"
    for directory in dirs:
        try:
            prs += github.pull_requests(directory)
            ok += 1
        except SourceUnavailable as exc:
            errors.append(str(exc))
    if not errors:
        return prs, "ok"
    return prs, ("partial: " + "; ".join(errors)) if ok else errors[0]


def _refresh_snapshot(project: Path, backfill: bool = False):
    """Compute state, write wow/progress.json and return (state, snapshot). Raises config.ConfigError.
    With backfill, history also gets one point per git commit that touched specs/*/tasks.md."""
    cfg = config.load_config(project)
    result = state_mod.compute_state(project, cfg, _jira_for(project))
    prs, result["sources"]["github"] = _github_prs(project, cfg)
    result = links.build_links(project, result, prs)
    result["pb"] = evidence.pb_status(project, [e["id"] for e in result["epics"]])
    result["reviews"] = evidence.review_summaries(project)
    result["pricing"] = evidence.pricing(cfg)
    records = usage_mod.collect(project, cfg)
    snap = snapshot_mod.build(result, snapshot_mod.load_previous(project), _now(), usage=records)
    if backfill:
        try:
            keys = manifest.load(project)["plan"]["export"]["epics"]
        except (manifest.ManifestError, KeyError, TypeError):
            keys = {}
        epic_by_key = {key: eid for eid, key in keys.items() if key}
        snap["history"] = snapshot_mod.merge_history(snap["history"], snapshot_mod.backfill_points(project, epic_by_key))
    snapshot_mod.write(project, snap)
    return result, snap


def _cmd_dashboard(args) -> int:
    import standalone
    projects = [Path(p).expanduser().resolve() for p in (args.project or ["."])]
    docs = []
    for project in projects:
        try:
            _, snap = _refresh_snapshot(project, backfill=args.backfill_git)
        except config.ConfigError as exc:
            sys.stderr.write(f"wow: {project}: {exc}\n")
            return exitcodes.CANNOT_EVALUATE
        docs.append((f"{project.name}/{snapshot_mod.PROGRESS_REL}", snap))
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(standalone.embed(standalone.TEMPLATE.read_text(encoding="utf-8"), docs), encoding="utf-8")
    print(f"wrote {out} ({len(docs)} snapshot(s) embedded; opens offline, no drop needed)")
    return exitcodes.OK


def _cmd_hook(args) -> int:
    import cursorhook
    if args.hook_command == "install-cursor":
        changed = cursorhook.install(Path(args.hooks_file).expanduser(), cursorhook.default_command())
        print(f"{args.hooks_file}: {'stop hook added' if changed else 'stop hook already present'}")
        return exitcodes.OK
    if args.hook_command == "cursor-shell":
        # beforeShellExecution: deny only what shellguard names; any failure of the guard lets the command run.
        answer = {"permission": "allow"}
        try:
            payload = json.loads(sys.stdin.read() or "{}")
            reason = shellguard.check(str(payload.get("command") or ""), payload.get("cwd"))
            if reason:
                answer = {"permission": "deny", "user_message": f"WoW blocked this command: {reason}",
                          "agent_message": f"Blocked by WoW's shell guard: {reason} Rewrite the command; do not "
                                           f"work around the guard."}
        except Exception:  # noqa: BLE001 — a guard that crashes must not stop the agent
            pass
        print(json.dumps(answer))
        return exitcodes.OK
    # cursor-stop runs inside Cursor's agent loop: it must never fail and always answers with JSON.
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        cursorhook.record_turn(payload, _now())
    except Exception:  # noqa: BLE001 — a hook that crashes would surface in every agent turn
        pass
    print("{}")
    return exitcodes.OK


def _cmd_snapshot(args) -> int:
    project = _project(args)
    try:
        result, _ = _refresh_snapshot(project, backfill=args.backfill_git)
    except config.ConfigError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
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


def _cmd_progress(args) -> int:
    if args.line:
        # The statusline calls this before every prompt with one second to answer: never fail, never print errors.
        try:
            # By hand in a terminal there is no JSON coming: never wait on the keyboard, use the current folder.
            data = {} if sys.stdin.isatty() else json.loads(sys.stdin.read() or "{}")
            folder = (data.get("workspace") or {}).get("current_dir") or data.get("cwd") or "."
            text = progress_mod.line(Path(folder).resolve())
        except Exception:  # noqa: BLE001
            text = ""
        if text:
            print(text)
        return exitcodes.OK
    project = _project(args)
    try:
        cfg = config.load_config(project)
    except config.ConfigError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    result = progress_mod.write(project, cfg, _jira_for(project))
    flows = [("Flujo PB", progress_mod.DIR / "pb.md", result["pb"])] + \
            [(f"Flujo SK {key}", progress_mod.DIR / f"sk-{key}.md", v) for key, v in result["sk"].items()]
    for title, rel, summary in flows:
        print(f"{title:<22} {summary['percent']:>3}%  ({summary['done']} de {summary['total']})  {rel}")
        for line in (project / rel).read_text(encoding="utf-8").splitlines():
            if line.startswith(("- [ ]", "- [?]")):
                print(f"    {line[2:]}")
    for label in result["manual_without_evidence"]:
        print(f"! ticked without evidence, not counted: {label}")
    return exitcodes.OK


def _cmd_sk_ric(args) -> int:
    action = args.sk_command
    # A reply starting with / runs as a slash command, so send is checked as well as run.
    reason = {"run": lambda: skrun.refuse(args.command), "send": lambda: skrun.refuse_reply(args.text),
              "quit": lambda: None}[action]()
    if reason:
        sys.stderr.write(f"wow: {reason}\n")
        return exitcodes.FINDINGS
    if not skrun.ric_path().is_file():
        sys.stderr.write(f"wow: {skrun.ric_path()} not found: install run-in-cursor (its install.sh) or set WOW_RIC\n")
        return exitcodes.CANNOT_EVALUATE
    rest = {"run": lambda: [args.command], "send": lambda: [args.session, args.text],
            "quit": lambda: [args.session]}[action]()
    return subprocess.run(skrun.argv(action, rest, _project(args))).returncode  # the user sees ric's screen as is


def _cmd_sk_start(args) -> int:
    try:
        added = flow_sk.register(_project(args), args.key)
    except ValueError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    print(f"{'tracking' if added else 'already tracked'} {args.key}")
    return exitcodes.OK


def _cmd_sk_status(args) -> int:
    result = sk.status(_project(args), args.feature)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    dirty = result["import_warnings"] or any(f["orphan_tasks"] for f in result["features"])
    return exitcodes.FINDINGS if dirty else exitcodes.OK


def _cmd_run_wu(args) -> int:
    sys.stderr.write("wow: run-wu is deprecated: run /spec-kit.implement in interactive Cursor (IDE chat or cursor-agent without -p); "
                     "`wow hook install-cursor` records its tokens\n")
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


def _decision_author(project: Path) -> str:
    import os
    import subprocess
    name = subprocess.run(["git", "-C", str(project), "config", "user.name"], capture_output=True, text=True).stdout
    return name.strip() or os.environ.get("USER", "unknown")


def _cmd_review_decide(args, project: Path) -> int:
    if not args.reason or not args.reason.strip():
        sys.stderr.write("wow: --decide needs --reason \"<why>\"\n")
        return exitcodes.CANNOT_EVALUATE
    summary = review_mod.load_summary(project, args.ref, args.set or "story")
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        summary = review_mod.decide(summary, args.decide, args.reason, _decision_author(project), now)
    except ValueError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    review_mod.save_summary(project, summary)
    print(f"{args.ref}: {args.decide} by a human after HITL — {summary['decision']['reason']}")
    return exitcodes.OK


def _sync_readiness(project: Path, summary: dict) -> None:
    """plan.readiness mirrors the readiness review: its verdict and the rounds of the current cycle (a plan edited
    after approval reopens the review; the schema allows at most 3 rounds)."""
    doc = manifest.load(project)
    verdict = {"approved": "approved", "approved_by_human": "approved", "hitl": "hitl"}.get(summary["final"],
                                                                                         "changes_required")
    readiness = {"verdict": verdict, "rounds": len(summary["rounds"]) - summary.get("cycle_start", 0)}
    if doc["plan"].get("readiness") != readiness:
        doc["plan"]["readiness"] = readiness
        manifest.save(project, doc)


def _cmd_review(args) -> int:
    project = _project(args)
    if not review_mod.safe_ref(args.ref):
        sys.stderr.write(f"wow: unsafe ref {args.ref!r}: use letters, digits, '.', '_' or '-'\n")
        return exitcodes.CANNOT_EVALUATE
    if args.decide:
        return _cmd_review_decide(args, project)
    if not args.set:
        sys.stderr.write("wow: review needs --set readiness|story|epic|standards|claims (or --decide after HITL)\n")
        return exitcodes.CANNOT_EVALUATE
    try:
        cfg = config.load_config(project)
        repo = Path(args.repo).resolve() if args.repo else project
        if args.set == "readiness":
            packet = packets.readiness_packet(project)
        elif args.set == "story":
            packet = packets.story_packet(project, args.ref, repo, args.base, ci=packets.ci_evidence)
        elif args.set == "epic":
            packet = packets.epic_packet(project, args.ref, repo, args.base, ci=packets.ci_evidence)
        elif args.set == "standards":
            packet = packets.standards_packet(project, args.ref, repo, args.base)
        else:
            if not args.doc:
                sys.stderr.write("wow: --set claims requires --doc PATH\n")
                return exitcodes.CANNOT_EVALUATE
            packet = packets.claims_packet(Path(args.doc).resolve(), repo)
    except (config.ConfigError, packets.PacketError, manifest.ManifestError) as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE

    # The standards axis of a story or epic keeps its own rounds: it never closes or reopens the spec axis.
    ref = f"{args.ref}.standards" if args.set == "standards" else args.ref
    summary = review_mod.load_summary(project, ref, args.set)
    dhash = packets.diff_hash(packet["body"])
    action = review_mod.next_action(summary, dhash)
    if action == "run" and summary["final"] is not None:
        print(f"{ref}: the content changed after its {summary['final']} verdict; opening a new review cycle")
        summary = review_mod.reopen_if_stale(summary, dhash)
    if action == "done":
        if args.set == "readiness":
            _sync_readiness(project, summary)  # repairs a manifest written by an older build
        print(f"{ref}: approved" + (" by a human after HITL" if summary["final"] == "approved_by_human" else ""))
        return exitcodes.OK
    if action == "rejected":
        print(f"{ref}: rejected by a human after HITL — {summary['decision']['reason']}")
        return exitcodes.FINDINGS
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
        started = _dt.datetime.now(_dt.timezone.utc)
        text, used = reviewers.run_backend_with_usage(spec, packets.build_prompt(packet), packet["cwd"])
        duration_ms = int((_dt.datetime.now(_dt.timezone.utc) - started).total_seconds() * 1000)
    except reviewers.NoReviewer as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    except (reviewers.ReviewerFailed, FileNotFoundError, OSError) as exc:
        sys.stderr.write(f"wow: reviewer failed: {exc}\n")
        return exitcodes.CANNOT_EVALUATE

    number = len(summary["rounds"]) + 1
    # Usage lands in the project the review belongs to, whatever directory the command ran from.
    stamp = _dt.datetime.now(_dt.timezone.utc)
    usage_file = project / "harness" / "reviews" / f"{stamp.strftime('%Y%m%dT%H%M%SZ')}-{ref}-r{number}.json"
    usage_file.parent.mkdir(parents=True, exist_ok=True)
    usage_file.write_text(json.dumps({
        "schema_version": 1, "ts": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"), "ref": ref, "set": args.set, "round": number,
        "reviewer": name, "model": reviewers.codex_model() if name == "codex" else None, "usage": used,
        "duration_ms": duration_ms}, indent=2) + "\n",
        encoding="utf-8")
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
        _sync_readiness(project, summary)

    last = summary["rounds"][-1]
    print(f"round {last['n']}: {last['verdict']} (reviewer: {name})")
    for blocker in last["blockers"]:
        print(f"BLOCKER {blocker['anchor']} {blocker['path_line']} — {blocker['text']}")
    if summary["final"] == "hitl":
        print("escalated to HITL: decide as a human, no new round will open")
    return exitcodes.OK if summary["final"] == "approved" else exitcodes.FINDINGS


def _cmd_pack_check(args, project: Path) -> int:
    if args.target is None or (args.target == "epic" and not args.id):
        sys.stderr.write("wow: pack check needs prd | rfc | epic --id E<n>\n")
        return exitcodes.CANNOT_EVALUATE
    name = f"epic-{args.id}" if args.target == "epic" else args.target
    result = pbcompletion.check_file(project, name)
    if result is None:
        sys.stderr.write(f"wow: wow/pb/{name}.md not found; run wow pack {args.target} first\n")
        return exitcodes.CANNOT_EVALUATE
    # Product Brain resolves commits with the user's GitHub access: one that is not on a remote breaks the paste.
    result["errors"] += refs.check((project / "wow" / "pb" / f"{name}.md").read_text(encoding="utf-8"), project)
    units = f"{result['units']:g}"
    print(f"predicted completion: {result['percentage']}% ({units}/{result['total']} units)")
    for item in result["pending"]:
        if item["field"] in pbcompletion.OPTIONAL_FIELDS:
            print(f"optional: {item['field']} ({item['state']}) — Product Brain can fill it at Jira export")
        else:
            print(f"pending: {item['field']} ({item['state']}) in {item['section']}")
    for error in result["errors"]:
        print(f"error: {error}")
    return exitcodes.OK if pbcompletion.ready(result) else exitcodes.FINDINGS


def _git_author(project: Path) -> str:
    proc = subprocess.run(["git", "-C", str(project), "config", "user.name"], capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _cmd_pack(args) -> int:
    project = _project(args)
    if args.kind == "check":
        return _cmd_pack_check(args, project)
    try:
        doc = manifest.load(project)
    except manifest.ManifestError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    if manifest.validate(doc):
        sys.stderr.write("wow: manifest is invalid; run wow manifest validate\n")
        return exitcodes.CANNOT_EVALUATE
    plan_md = project / "wow" / "plan" / "PLAN.md"
    brief = pack.parse_brief(plan_md.read_text(encoding="utf-8") if plan_md.is_file() else "")
    mhash = manifest.manifest_hash(project)
    try:
        if args.kind == "epic":
            if not args.id:
                sys.stderr.write("wow: pack epic needs --id E<n>\n")
                return exitcodes.CANNOT_EVALUATE
            name, text = f"epic-{args.id}", pack.render_epic(doc, args.id, mhash)
        else:
            if args.full:
                sys.stderr.write("wow: --full is deprecated: Product Brain registers the work, the plan already "
                                 "carries it; the default registro packet scores 100% with nothing to fill\n")
            render = pack.render_prd if args.kind == "prd" else pack.render_rfc
            name, text = args.kind, render(doc, brief, mhash, pending=repo_src.pending_items(project),
                                           registro=not args.full, author=_git_author(project))
    except ValueError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    try:
        pack.write_packet(project, name, text, force=args.force)
    except FileExistsError:
        sys.stderr.write(f"wow: wow/pb/{name}.md exists; --force overwrites it (filled sections are lost)\n")
        return exitcodes.FINDINGS
    pack.ensure_preamble(project)
    print(f"wrote wow/pb/{name}.md")
    return exitcodes.OK


def _cmd_close(args) -> int:
    project = _project(args)
    jira = _jira_for(project, command=f"close --epic {args.epic}" + (" --subtasks" if args.subtasks else ""))
    if jira is None:
        sys.stderr.write("wow: Jira credentials not found (IC_JIRA_BASE_URL, IC_JIRA_USER_EMAIL, IC_JIRA_API_TOKEN)\n")
        return exitcodes.CANNOT_EVALUATE
    try:
        result = (closing.plan_subtasks if args.subtasks else closing.plan)(project, args.epic, jira)
    except (manifest.ManifestError, SourceUnavailable) as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    for blocker in result["blockers"]:
        print(f"blocked: {blocker}")
    if result["blockers"]:
        return exitcodes.FINDINGS
    print(f"{result['key']}: {result['already_done']} already done, {len(result['to_close'])} to close: "
          f"{', '.join(result['to_close']) or '-'}")
    if result.get("waiting"):
        print(f"{result['waiting']} subtask{'s wait' if result['waiting'] > 1 else ' waits'} for its story: "
              f"Spec-Kit closes the story (sync-status), then run this again")
    if not args.apply:
        print("dry run: nothing changed; --apply closes them in this order")
        return exitcodes.OK
    errors = closing.apply(result, jira)
    for error in errors:
        print(f"error: {error}")
    if not errors:
        print(f"closed {len(result['to_close'])} issues")
    return exitcodes.FINDINGS if errors else exitcodes.OK


def _print_editor_fixes(fixes) -> None:
    for fix in fixes:
        print(f"\nFix in Product Brain's document editor: replace the section \"{fix['section']}\" with "
              f"(the chat cannot fix it: {fix['reason']}):\n\n{fix['replace_with']}\n")


def _cmd_pbchat_decide(args, project: Path) -> int:
    if not args.reason or not args.reason.strip():
        sys.stderr.write("wow: --decide needs --reason \"<why>\"\n")
        return exitcodes.CANNOT_EVALUATE
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        result = pbaudit.decide(project, args.doc, args.decide, args.reason, _decision_author(project), now)
    except ValueError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    print(f"{args.doc}: {args.decide} by a human over a changes_required audit — {result['decision']['reason']}")
    return exitcodes.OK if args.decide == "approved" else exitcodes.FINDINGS


def _cmd_pbchat_audit(args) -> int:
    project = _project(args)
    if not review_mod.safe_ref(args.doc):
        sys.stderr.write(f"wow: unsafe document name {args.doc!r}\n")
        return exitcodes.CANNOT_EVALUATE
    if args.decide:
        return _cmd_pbchat_decide(args, project)
    extra = []
    if args.deep:
        try:
            extra = pbaudit.deep_inventions(project, args.doc, config.load_config(project))
        except FileNotFoundError:
            sys.stderr.write(f"wow: wow/pb/chats/{args.doc}.md not found or reviewer CLI missing\n")
            return exitcodes.CANNOT_EVALUATE
        except (reviewers.NoReviewer, reviewers.ReviewerFailed, review_mod.ReviewOutputError,
                config.ConfigError, OSError) as exc:
            sys.stderr.write(f"wow: deep audit failed: {exc}\n")
            return exitcodes.CANNOT_EVALUATE
    try:
        result = pbaudit.audit(project, args.doc, extra_inventions=extra)
    except FileNotFoundError:
        fixes = pbaudit.editor_fixes(project, args.doc)
        if not fixes:
            sys.stderr.write(f"wow: wow/pb/chats/{args.doc}.md not found; copy the Product Brain chat there first\n")
            return exitcodes.CANNOT_EVALUATE
        print(f"no wow/pb/chats/{args.doc}.md: only the panel copy was checked")
        _print_editor_fixes(fixes)
        return exitcodes.FINDINGS
    pbaudit.write_audit(project, result)
    print(f"verdict: {result['verdict']}")
    if result.get("decision"):
        print(f"human decision kept ({result['decision']['author']}, {result['decision']['at']}): the material "
              f"is the one it was decided on — {result['decision']['reason']}")
    if result.get("decision_dropped"):
        print(f"human decision dropped: {result['decision_dropped']['why']} "
              f"(it said: {result['decision_dropped']['reason']})")
    if result["corrections_to_paste"]:
        print(result["corrections_to_paste"])
    changes = result["pb_changes"]
    if changes is None:
        print(f"no wow/pb/chats/{args.doc}.final.md: copy the document from Product Brain's panel there "
              f"to see what it changed against the packet")
    else:
        print(f"Product Brain changed {len(changes)} lines against the packet" + (":" if changes else ""))
        for change in changes:
            print(f"{change['op']} [{change['section']}] {change['text'][:160]}")
    _print_editor_fixes(result["editor_fixes"])
    return exitcodes.OK if result["verdict"] in reviews.CLOSED else exitcodes.FINDINGS


def _cmd_context_scan(args) -> int:
    result = contextpack.scan(_project(args))
    print(f"children: {', '.join(result['children']) or '-'}")
    print(f"docs: {len(result['docs'])}")
    for path in result["created"]:
        print(f"created {path}")
    return exitcodes.OK


def _cmd_estimate(args) -> int:
    project = _project(args)
    try:
        cfg = config.load_config(project)
        histories = [Path(h).expanduser().resolve() for h in (args.history or (cfg.get("estimate") or {}).get("history", []))]
        result = estimate.estimate(project, histories, cfg)
    except (manifest.ManifestError, config.ConfigError, ValueError) as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    print(f"calibrated on {result['histories']} past epic(s); hours per day: {result['hours_per_day']:g}")
    for c in result["components"]:
        print(f"  {c['name']:<20} {c['minutes'] / 60:5.1f} h  {c['source']:<8} {c['basis']}")
    print(f"total: {result['minutes'] / 60:.1f} h (range {result['low_minutes'] / 60:.1f}-{result['high_minutes'] / 60:.1f} h)")
    print(f"start: {result['start']}  end: {result['end_likely']} (likely) - {result['end_high']} (high)")
    rows = result["units"] or result["tasks"]
    print("suggested model per " + ("work unit" if result["units"] else "task") + " (Product Brain and Spec-Kit set none):")
    for row in rows:
        print(f"  {row['id']:<8} {row['model']:<26} {row['why']}")
    return exitcodes.OK


def _cmd_ref_check(args) -> int:
    doc = Path(args.doc)
    if not doc.is_file():
        sys.stderr.write(f"wow: {doc} not found\n")
        return exitcodes.CANNOT_EVALUATE
    text = doc.read_text(encoding="utf-8", errors="replace")
    findings = refs.check(text, _project(args))
    for finding in findings:
        print(finding)
    # A bare hash cannot be tied to a repo, so it is not verified; say so instead of reporting a clean pass.
    loose = refs.unchecked(text)
    if loose:
        print(f"warning: not checked: {', '.join(loose)} (write them as `name @ sha` or as a GitHub URL to verify them)")
    summary = f"{len(refs.extract(text))} references checked, {len(findings)} findings"
    if loose:
        summary += f", {len(loose)} bare hash{'es' if len(loose) > 1 else ''} not checked"
    print(summary)
    return exitcodes.FINDINGS if findings else exitcodes.OK


def _cmd_cite_check(args) -> int:
    doc = Path(args.doc)
    if not doc.is_file():
        sys.stderr.write(f"wow: {doc} not found\n")
        return exitcodes.CANNOT_EVALUATE
    try:
        aliases = dict(a.split("=", 1) for a in args.alias if "=" in a)
        result = cites.check(doc.read_text(encoding="utf-8", errors="replace"), Path(args.root).resolve(), args.sha,
                             aliases)
    except ValueError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    for finding in result["findings"]:
        print(finding)
    print(f"{result['checked']} citations checked, {len(result['findings'])} findings")
    return exitcodes.FINDINGS if result["findings"] else exitcodes.OK


def _cmd_context_restore(args) -> int:
    restored = contextpack.restore_discovery(_project(args))
    for rel in restored:
        print(f"restored {rel}")
    if not restored:
        print("discovery matches its verified copies")
    return exitcodes.OK


def _cmd_context_check(args) -> int:
    findings = contextpack.check(_project(args))
    for line in findings:
        print(line)
    return exitcodes.FINDINGS if findings else exitcodes.OK


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
    ml = with_project(msub.add_parser("lint"))
    ml.add_argument("--pb", action="store_true", help="also check what Product Brain needs per story")
    ml.set_defaults(handler=_cmd_manifest_lint)

    pl = sub.add_parser("plan", help="create or freeze the upstream plan")
    psub = pl.add_subparsers(dest="plan_command", parser_class=_Parser)
    init = with_project(psub.add_parser("init"))
    init.add_argument("plan_id")
    init.add_argument("--title", required=True)
    init.add_argument("--mode", choices=list(manifest.MODES), default=None)
    init.set_defaults(handler=_cmd_plan_init)
    fr = with_project(psub.add_parser("freeze"))
    fr.add_argument("--epics", required=True, help="EPIC=KEY pairs, comma separated")
    fr.add_argument("--reopen", default=None, help="reason for changing an already recorded epic key")
    fr.set_defaults(handler=_cmd_plan_freeze)
    gd = with_project(psub.add_parser("guard"))
    gd.add_argument("--reopen", default=None, help="reason to edit a frozen manifest")
    gd.set_defaults(handler=_cmd_plan_guard)

    with_project(sub.add_parser("state", help="print the derived state as JSON")).set_defaults(handler=_cmd_state)
    sp = with_project(sub.add_parser("snapshot", help="write wow/progress.json"))
    sp.add_argument("--backfill-git", action="store_true",
                    help="add history points from the git commits that touched specs/*/tasks.md")
    sp.set_defaults(handler=_cmd_snapshot)
    hk = sub.add_parser("hook", help="Cursor hook entry points")
    hk.add_argument("hook_command", choices=["cursor-stop", "cursor-shell", "install-cursor"])
    hk.add_argument("--hooks-file", default=str(Path.home() / ".cursor" / "hooks.json"),
                    help="Cursor user hooks file for install-cursor (default: ~/.cursor/hooks.json)")
    hk.set_defaults(handler=_cmd_hook)
    db = sub.add_parser("dashboard", help="write a standalone offline HTML summary with fresh snapshots embedded")
    db.add_argument("--out", required=True, help="HTML file to write")
    db.add_argument("--project", action="append", default=None,
                    help="project root; repeat for a portfolio (default: current directory)")
    db.add_argument("--backfill-git", action="store_true",
                    help="add history points from the git commits that touched specs/*/tasks.md")
    db.set_defaults(handler=_cmd_dashboard)

    rv = with_project(sub.add_parser("review", help="run an anchored independent review"))
    rv.add_argument("--set", default=None, choices=["readiness", "story", "epic", "standards", "claims"])
    rv.add_argument("--decide", default=None, choices=["approved", "rejected"],
                    help="record a human verdict on a review escalated to HITL (needs --reason)")
    rv.add_argument("--reason", default=None, help="why the human decided (required with --decide)")
    rv.add_argument("--ref", required=True, help="plan | Jira story key | epic id | claims doc name")
    rv.add_argument("--repo", default=None, help="repository to diff or to verify claims against")
    rv.add_argument("--base", default="main", help="git base for story/epic diffs (default: main)")
    rv.add_argument("--doc", default=None, help="claims document (required for --set claims)")
    rv.set_defaults(handler=_cmd_review)

    pk = with_project(sub.add_parser("pack", help="render Product Brain packets from the manifest"))
    pk.add_argument("kind", choices=["prd", "rfc", "epic", "check"])
    pk.add_argument("target", nargs="?", choices=["prd", "rfc", "epic"], default=None,
                    help="packet to check, only with kind 'check'")
    pk.add_argument("--id", default=None, help="epic id for kind 'epic'")
    pk.add_argument("--force", action="store_true", help="overwrite an existing packet")
    pk.add_argument("--full", action="store_true",
                    help="deprecated: PRD/RFC with {{placeholders}} for an LLM to fill instead of the registro packet")
    pk.set_defaults(handler=_cmd_pack)

    cl = with_project(sub.add_parser("close", help="close the subtasks and the epic Spec-Kit leaves open in Jira"))
    cl.add_argument("--epic", required=True, help="epic id from the manifest (E1)")
    cl.add_argument("--apply", action="store_true", help="apply the done transitions (default: dry run)")
    cl.add_argument("--subtasks", action="store_true",
                    help="only the subtasks of stories Spec-Kit already closed; run it after each sync-status")
    cl.set_defaults(handler=_cmd_close)

    jr = sub.add_parser("jira", help="repair what Product Brain's Jira export leaves wrong")
    jrsub = jr.add_subparsers(dest="jira_command", parser_class=_Parser)
    jrsub.required = True
    jf = with_project(jrsub.add_parser("fix-fields", help="component, story points, priority and labels of each story, "
                                                          "from the manifest"))
    jf.add_argument("--epic", required=True, help="epic id from the manifest (E1)")
    jf.add_argument("--apply", action="store_true", help="write the fields in Jira (default: dry run)")
    jf.set_defaults(handler=_cmd_jira_fix_fields)

    pc = sub.add_parser("pbchat", help="audit local copies of Product Brain chats")
    pcsub = pc.add_subparsers(dest="pbchat_command", parser_class=_Parser)
    pa = with_project(pcsub.add_parser("audit"))
    pa.add_argument("doc", help="prd | rfc | epic-E<n>")
    pa.add_argument("--deep", action="store_true", help="also ask an independent reviewer")
    pa.add_argument("--decide", default=None, choices=["approved", "rejected"],
                    help="record a human verdict on a changes_required audit whose document the owner decides "
                         "not to correct in Product Brain; needs --reason")
    pa.add_argument("--reason", default=None, help="why the human decided (required with --decide)")
    pa.set_defaults(handler=_cmd_pbchat_audit)

    cx = sub.add_parser("context", help="inventory and validate the context pack")
    cxsub = cx.add_subparsers(dest="context_command", parser_class=_Parser)
    with_project(cxsub.add_parser("scan")).set_defaults(handler=_cmd_context_scan)
    with_project(cxsub.add_parser("check")).set_defaults(handler=_cmd_context_check)
    es = with_project(sub.add_parser("estimate", help="estimate the plan from past epics and suggest a model per task"))
    es.add_argument("--history", action="append", default=None, metavar="PROJECT",
                    help="a finished epic's project to calibrate on; repeatable (default: estimate.history in config)")
    es.set_defaults(handler=_cmd_estimate)

    rf = sub.add_parser("ref", help="check that every commit or GitHub URL a document hands out exists on its remote")
    rfsub = rf.add_subparsers(dest="ref_command", required=True)
    rc = with_project(rfsub.add_parser("check"))
    rc.add_argument("doc", help="any text document (packet, Brief, manifest)")
    rc.set_defaults(handler=_cmd_ref_check)

    ct = sub.add_parser("cite", help="check that every path:line a document cites exists and is in range")
    ctsub = ct.add_subparsers(dest="cite_command", required=True)
    cc = ctsub.add_parser("check")
    cc.add_argument("doc", help="Markdown or HTML document")
    cc.add_argument("--root", default=".", help="directory the citations are relative to (default: .)")
    cc.add_argument("--sha", default=None, help="read the files at this commit of --root instead of the working tree")
    cc.add_argument("--alias", action="append", default=[], metavar="NAME=PATH",
                    help="expand an abbreviation the document uses (NAME/file → PATH/file); repeatable")
    cc.set_defaults(handler=_cmd_cite_check)

    with_project(cxsub.add_parser("restore", help="put the verified discovery copies back")).set_defaults(
        handler=_cmd_context_restore)

    with_project(sub.add_parser("usage", help="summarize LLM usage by vendor and model")).set_defaults(handler=_cmd_usage)

    rw = with_project(sub.add_parser("run-wu", help="deprecated: run /spec-kit.implement headless and record usage"))
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
    skr = with_project(sksub.add_parser("run", help="send a /spec-kit.* command to Cursor (interactive, recorded)"))
    skr.add_argument("command")
    skr.set_defaults(handler=_cmd_sk_ric)
    skn = with_project(sksub.add_parser("send", help="answer in a running Cursor session"))
    skn.add_argument("session")
    skn.add_argument("text")
    skn.set_defaults(handler=_cmd_sk_ric)
    skq = with_project(sksub.add_parser("quit", help="leave a Cursor session"))
    skq.add_argument("session")
    skq.set_defaults(handler=_cmd_sk_ric)
    sst = with_project(sksub.add_parser("start", help="follow a Jira epic in the Spec-Kit flow, wherever it came from"))
    sst.add_argument("key")
    sst.set_defaults(handler=_cmd_sk_start)
    pr = with_project(sub.add_parser("progress", help="write and print the checklist of each flow, with %% complete"))
    pr.add_argument("--line", action="store_true", help="one line for the statusline (reads JSON on stdin, no network)")
    pr.set_defaults(handler=_cmd_progress)
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
