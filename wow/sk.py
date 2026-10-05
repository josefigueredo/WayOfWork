"""Spec-Kit preparation: exact cursor-agent commands and artifact status (spec 9.4)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from sources import speckit

STEPS = ("sync", "clarify", "plan", "tasks", "sync-status")
_SECTION_RE = re.compile(r"^##\s")
_TASK_RE = re.compile(r"^\s*-\s*\[[ xX]\]")
_JIRA_RE = re.compile(r"^\s*-\s*jira:\s*[A-Z][A-Z0-9]*-\d+\s*$", re.IGNORECASE)


def commands_for(step: str, cfg: dict, epic: Optional[str] = None, feature: Optional[str] = None) -> List[str]:
    """The slash command to paste in interactive Cursor: the IDE chat or `cursor-agent` without -p. Both fire the
    command's start/end and Cursor's `stop` hook (model and tokens). `cursor-agent -p` runs the command and sends its
    start/end but fires no `stop` (measured on 2026.10.01); the `spec-kit` terminal CLI sends nothing."""
    if step not in STEPS:
        raise ValueError(f"unknown step {step!r}; expected one of {', '.join(STEPS)}")
    if step == "sync":
        if not epic:
            raise ValueError("step 'sync' needs --epic KEY")
        return [f"/spec-kit.sync --epic-key {epic}"]
    if not feature:
        raise ValueError(f"step '{step}' needs --feature DIR")
    name = Path(feature).name
    if step == "clarify":
        return [f"/spec-kit.clarify Use the answers in wow/sk/{name}/clarify-answers.md"]
    if step == "plan":
        return [f"/spec-kit.plan Use wow/sk/{name}/plan-draft.md as the design input"]
    if step == "sync-status":
        return [f"/spec-kit.sync-status {feature}"]
    return ["/spec-kit.tasks", "/spec-kit.tasks.shape"]


def orphan_tasks(text: str) -> int:
    sections: List[dict] = [{"keys": 0, "orphans": 0}]
    pending = False
    for raw in text.splitlines():
        if _SECTION_RE.match(raw):
            if pending:
                sections[-1]["orphans"] += 1
            sections.append({"keys": 0, "orphans": 0})
            pending = False
        elif _TASK_RE.match(raw):
            if pending:
                sections[-1]["orphans"] += 1
            pending = True
        elif _JIRA_RE.match(raw) and pending:
            sections[-1]["keys"] += 1
            pending = False
    if pending:
        sections[-1]["orphans"] += 1
    return sum(s["orphans"] for s in sections if s["keys"])


def status(project: Path, feature: Optional[str] = None) -> dict:
    report = project / ".spec-kit" / "import_report.md"
    warnings = 0
    if report.is_file():
        warnings = sum(1 for line in report.read_text(encoding="utf-8").splitlines()
                       if "⚠" in line or "warning" in line.lower())
    out = []
    for item in speckit.features(project):
        if feature and item["dir"] != feature.rstrip("/"):
            continue
        folder, name = project / item["dir"], Path(item["dir"]).name
        missing = [f for f in ("plan.md", "tasks.md") if not (folder / f).is_file()]
        if not item["has_work_units"]:
            missing.append("work-units.json")
        for draft in ("clarify-answers.md", "plan-draft.md"):
            if not (project / "wow" / "sk" / name / draft).is_file():
                missing.append(f"wow/sk/{name}/{draft}")
        tasks = folder / "tasks.md"
        orphans = orphan_tasks(tasks.read_text(encoding="utf-8")) if tasks.is_file() else 0
        out.append({"dir": item["dir"], "epic_key": item["epic_key"], "missing": missing, "orphan_tasks": orphans})
    return {"import_warnings": warnings, "features": out}
