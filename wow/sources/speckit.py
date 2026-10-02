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


def work_unit_ids(path: Path) -> List[str]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    items = data.get("work_units", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    return [item["id"] for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)]


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
        wu_ids = work_unit_ids(wu_path)
        checked_text = [text for checked, text in parsed["lines"] if checked]
        pending = [wu for wu in wu_ids if not any(wu in text for text in checked_text)]
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
        })
    return result
