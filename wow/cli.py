"""wow command line entrypoint."""
from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path
from typing import List

import json

import config
import exitcodes
import manifest
import snapshot as snapshot_mod
import state as state_mod
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
    snap = snapshot_mod.build(result, snapshot_mod.load_previous(project), _now())
    snapshot_mod.write(project, snap)
    print(f"wrote {snapshot_mod.PROGRESS_REL}")
    for blocker in result["blockers"]:
        print(f"! {blocker}")
    for step in result["next_steps"]:
        print(f"- [{step['where']}] {step['action']} -> {step['command']}")
    return exitcodes.OK


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
