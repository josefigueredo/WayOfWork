"""Spec-Kit artifacts: specs/<feature>/, tasks.md and work-units.json (read only)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

EPIC_RE = re.compile(r"\*\*Jira Epic:\*\*\s*\[?([A-Z][A-Z0-9]*-[0-9]+)")
TASK_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s*(.*)$")
JIRA_RE = re.compile(r"^\s*-\s*jira:\s*([A-Z][A-Z0-9]*-\d+)\s*$", re.IGNORECASE)


def parse_tasks(text: str) -> dict:
    lines: List[Tuple[bool, str]] = []
    stories: Dict[str, Dict[str, int]] = {}
    last_checked: Optional[bool] = None
    for raw in text.splitlines():
        task = TASK_RE.match(raw)
        if task:
            last_checked = task.group(1).lower() == "x"
            lines.append((last_checked, task.group(2)))
            continue
        jira = JIRA_RE.match(raw)
        if jira and last_checked is not None:
            entry = stories.setdefault(jira.group(1).upper(), {"total": 0, "done": 0})
            entry["total"] += 1
            entry["done"] += 1 if last_checked else 0
            last_checked = None
    return {"total": len(lines), "done": sum(1 for checked, _ in lines if checked), "stories": stories, "lines": lines}


TASK_ID_RE = re.compile(r"^(T[0-9]+)\b")


def _work_units(path: Path) -> List[dict]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    items = data.get("work_units", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)]


def work_unit_ids(path: Path) -> List[str]:
    return [item["id"] for item in _work_units(path)]


_REVIEW_STATUS_RE = re.compile(r"^\*\*Status\*\*:\s*(\w+)", re.MULTILINE)


def _latest_review_approved(project: Path, unit_id: str) -> bool:
    """The implement cycle's own verdict: .spec-kit/implementation/<WU>-review-<n>.md, the highest n."""
    reviews = []
    for path in (project / ".spec-kit" / "implementation").glob(f"{unit_id}-review-*.md"):
        suffix = path.stem.rsplit("-", 1)[-1]
        if suffix.isdigit():
            reviews.append((int(suffix), path))
    if not reviews:
        return False
    status = _REVIEW_STATUS_RE.search(max(reviews)[1].read_text(encoding="utf-8", errors="replace"))
    return bool(status) and status.group(1) == "APPROVED"


def _unit_done(unit: dict, checked_text: List[str], checked_ids: set, project: Optional[Path] = None) -> bool:
    """A unit that lists its task_ids (as /spec-kit.tasks.shape writes them) is done when all of them are checked;
    otherwise its id has to appear on a checked task line, or its latest Spec-Kit review has to approve it
    (tasks.shape does not always write task_ids, and tasks.md does not always name the unit)."""
    task_ids = [t for t in unit.get("task_ids") or [] if isinstance(t, str)]
    if task_ids:
        return all(t in checked_ids for t in task_ids)
    if any(unit["id"] in text for text in checked_text):
        return True
    return project is not None and _latest_review_approved(project, unit["id"])


def features(project: Path) -> List[dict]:
    result: List[dict] = []
    specs = project / "specs"
    if not specs.is_dir():
        return result
    for spec in sorted(specs.glob("*/spec.md")):
        folder = spec.parent
        match = EPIC_RE.search(spec.read_text(encoding="utf-8"))
        tasks_path = folder / "tasks.md"
        parsed = parse_tasks(tasks_path.read_text(encoding="utf-8")) if tasks_path.is_file() else parse_tasks("")
        wu_path = folder / "work-units.json"
        if not wu_path.is_file():
            wu_path = project / ".spec-kit" / "work-units.json"
        units = _work_units(wu_path)
        wu_ids = [unit["id"] for unit in units]
        checked_text = [text for checked, text in parsed["lines"] if checked]
        checked_ids = {m.group(1) for m in (TASK_ID_RE.match(text) for text in checked_text) if m}
        pending = [unit["id"] for unit in units if not _unit_done(unit, checked_text, checked_ids, project)]
        result.append({
            "dir": folder.relative_to(project).as_posix(),
            "epic_key": match.group(1) if match else None,
            "has_plan": (folder / "plan.md").is_file(),
            "has_tasks": tasks_path.is_file(),
            "has_work_units": bool(wu_ids),
            "tasks_total": parsed["total"],
            "tasks_done": parsed["done"],
            "stories": parsed["stories"],
            "pending_work_units": pending,
            "units": {unit["id"]: unit for unit in units},
        })
    return result
