"""Upstream kanban manifest: load, validate, lint, init and freeze (spec D3, 9.2)."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import schema as schema_mod

MANIFEST_REL = Path("wow/plan/manifest.json")


class ManifestError(Exception):
    """The manifest is missing or is not parseable JSON."""


class FrozenError(Exception):
    """A write was attempted on a frozen manifest without --reopen."""


def _path(project: Path) -> Path:
    return project / MANIFEST_REL


def load(project: Path) -> dict:
    path = _path(project)
    if not path.is_file():
        raise ManifestError(f"manifest not found: {MANIFEST_REL}")
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest is not valid JSON: line {exc.lineno} column {exc.colno}: {exc.msg}")


def save(project: Path, doc: dict) -> None:
    path = _path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def manifest_hash(project: Path) -> str:
    return hashlib.sha256(_path(project).read_bytes()).hexdigest()[:16]


def _tasks(doc: dict) -> Iterator[Tuple[dict, dict]]:
    for epic in doc["epics"]:
        for task in epic["tasks"]:
            yield epic, task


def validate(doc: dict) -> List[str]:
    errors = schema_mod.validate(doc, schema_mod.load_schema("manifest"))
    if errors:
        return errors
    seen_epics, tasks_by_id = set(), {}
    for epic in doc["epics"]:
        if epic["id"] in seen_epics:
            errors.append(f"duplicate epic id '{epic['id']}'")
        seen_epics.add(epic["id"])
        for item in epic["done_when"]:
            anchor = item.split(":", 1)[0]
            if not anchor.startswith(epic["id"] + "."):
                errors.append(f"epic {epic['id']}: done_when '{anchor}' does not belong to {epic['id']}")
    for _, task in _tasks(doc):
        if task["id"] in tasks_by_id:
            errors.append(f"duplicate task id '{task['id']}'")
        tasks_by_id[task["id"]] = task
        ac_ids = [item.split(":", 1)[0] for item in task["acceptance"]]
        for ac in sorted({a for a in ac_ids if ac_ids.count(a) > 1}):
            errors.append(f"task {task['id']}: duplicate acceptance id '{ac}'")
    for _, task in _tasks(doc):
        for dep in task["depends_on"]:
            if dep not in tasks_by_id:
                errors.append(f"task {task['id']} depends on unknown task '{dep}'")
    errors.extend(_cycles(tasks_by_id))
    return errors


def _cycles(tasks_by_id: Dict[str, dict]) -> List[str]:
    state: Dict[str, int] = {}  # 1 = visiting, 2 = done
    found: List[str] = []

    def visit(task_id: str) -> None:
        state[task_id] = 1
        for dep in tasks_by_id[task_id]["depends_on"]:
            if dep not in tasks_by_id:
                continue
            if state.get(dep) == 1:
                message = f"dependency cycle involving task '{dep}'"
                if message not in found:
                    found.append(message)
            elif state.get(dep) is None:
                visit(dep)
        state[task_id] = 2

    for task_id in tasks_by_id:
        if state.get(task_id) is None:
            visit(task_id)
    return found


def lint(doc: dict) -> List[str]:
    findings: List[str] = []
    for epic in doc["epics"]:
        for task in epic["tasks"]:
            ref = f"{epic['id']}/{task['id']}"
            if not task["acceptance"]:
                findings.append(f"{ref}: no acceptance criteria")
            if task["estimate"] is None:
                findings.append(f"{ref}: no estimate (story points)")
            if task["priority"] is None:
                findings.append(f"{ref}: no priority")
            if not task["labels"]:
                findings.append(f"{ref}: no labels")
        if not epic["done_when"]:
            findings.append(f"{epic['id']}: no done_when")
    return findings


def new_manifest(plan_id: str, title: str, created: str) -> dict:
    return {
        "schema_version": 1,
        "plan": {"id": plan_id, "title": title, "created": created,
                 "readiness": {"verdict": None, "rounds": 0},
                 "export": {"frozen": False, "at": None, "epics": {}}},
        "epics": [{
            "id": "E1", "title": "Replace with the first epic title", "done_when": [],
            "tasks": [{"id": "1.1", "title": "Replace with the first task title", "acceptance": [],
                       "depends_on": [], "subtasks": [], "estimate": None, "priority": None, "labels": []}],
        }],
    }


def parse_epic_keys(text: str) -> Dict[str, str]:
    keys: Dict[str, str] = {}
    for part in [p.strip() for p in text.split(",") if p.strip()]:
        if "=" not in part:
            raise ValueError(f"expected EPIC=KEY, got {part!r}")
        epic_id, key = [s.strip() for s in part.split("=", 1)]
        keys[epic_id] = key
    return keys


def freeze(doc: dict, epic_keys: Dict[str, str], now: str, reopen_reason: Optional[str] = None) -> dict:
    """Record Jira keys and freeze. New epics can be added; changing a recorded key needs reopen_reason."""
    result = copy.deepcopy(doc)
    known = {epic["id"] for epic in result["epics"]}
    unknown = sorted(set(epic_keys) - known)
    if unknown:
        raise ValueError(f"unknown epic id(s): {', '.join(unknown)}")
    export = result["plan"]["export"]
    changed = sorted(eid for eid, key in epic_keys.items() if export["epics"].get(eid) not in (None, key))
    if changed and not reopen_reason:
        raise FrozenError(
            f"epic key(s) already recorded for {', '.join(changed)}; changing them needs --reopen \"<reason>\"")
    export["epics"].update(epic_keys)
    if not export["frozen"]:
        export["frozen"] = True
        export["at"] = now
    return result


def ensure_writable(doc: dict, reopen_reason: Optional[str]) -> None:
    export = doc["plan"]["export"]
    if export["frozen"] and not reopen_reason:
        raise FrozenError(
            f"manifest is frozen since {export['at']}: change scope through Product Brain (Artifact Engine) "
            f"and /spec-kit.amend, or pass --reopen \"<reason>\"")
