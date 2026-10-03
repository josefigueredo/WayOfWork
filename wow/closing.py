"""Close what neither Product Brain nor Spec-Kit closes: subtasks and the epic (/sync-status closes only stories).

Stories are Spec-Kit's: an open story is an anomaly (a task without its `- jira:` key, or sync-status not run)
that blocks the run and is reported, never closed here, so the closure stays in Spec-Kit's telemetry.

Runs only after the epic review is approved (by the reviewer or by a human with `wow review --decide`) and every
task in tasks.md is checked. Without --apply it only lists what it would close.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import manifest
from sources import SourceUnavailable, speckit
from state import REVIEW_CLOSED, review_final

_ORDER = {"subtask": 0, "epic": 1}


def plan(project: Path, epic_id: str, jira) -> dict:
    doc = manifest.load(project)
    key = doc["plan"]["export"]["epics"].get(epic_id)
    result = {"epic": epic_id, "key": key, "blockers": [], "to_close": [], "already_done": 0}
    if not key:
        result["blockers"].append(f"{epic_id} is not exported to Jira: run wow plan freeze --epics {epic_id}=<KEY>")
        return result
    feature = next((f for f in speckit.features(project) if f["epic_key"] == key), None)
    if feature is None:
        result["blockers"].append(f"no specs/*/spec.md carries Jira Epic {key}: run /spec-kit.sync first")
    elif feature["tasks_done"] != feature["tasks_total"] or not feature["tasks_total"]:
        result["blockers"].append(f"tasks.md is at {feature['tasks_done']}/{feature['tasks_total']}")
    if review_final(project, epic_id) not in REVIEW_CLOSED:
        result["blockers"].append(f"the epic review is not approved: wow review --set epic --ref {epic_id}, "
                                  f"then wow review --decide approved if it escalated to HITL")
    issues = jira.open_issues(key)
    sync = f"spec-kit sync-status {feature['dir']}" if feature else "spec-kit sync-status"
    for story in (i for i in issues if i["level"] == "story" and not i["done"]):
        result["blockers"].append(f"story {story['key']} is open in Jira: Spec-Kit closes stories; check its "
                                  f"`- jira: {story['key']}` lines in tasks.md and run {sync}")
    result["already_done"] = sum(1 for i in issues if i["done"])
    result["to_close"] = [i["key"] for i in sorted((i for i in issues if not i["done"] and i["level"] in _ORDER),
                                                   key=lambda i: _ORDER[i["level"]])]
    return result


def plan_subtasks(project: Path, epic_id: str, jira) -> dict:
    """Open subtasks whose story Spec-Kit already closed: they can close as each story ends, not at the epic's end.
    Subtasks of open stories wait for their story; the story's closure stays Spec-Kit's signal."""
    key = manifest.load(project)["plan"]["export"]["epics"].get(epic_id)
    result = {"epic": epic_id, "key": key, "blockers": [], "to_close": [], "already_done": 0, "waiting": 0}
    if not key:
        result["blockers"].append(f"{epic_id} is not exported to Jira: run wow plan freeze --epics {epic_id}=<KEY>")
        return result
    issues = jira.open_issues(key)
    done_stories = {i["key"] for i in issues if i["level"] == "story" and i["done"]}
    subtasks = [i for i in issues if i["level"] == "subtask"]
    result["already_done"] = sum(1 for i in subtasks if i["done"])
    result["to_close"] = [i["key"] for i in subtasks if not i["done"] and i.get("parent") in done_stories]
    result["waiting"] = sum(1 for i in subtasks if not i["done"] and i.get("parent") not in done_stories)
    return result


def apply(result: dict, jira) -> List[str]:
    """Close in order (subtasks, then the epic); stop at the first failure so the epic never closes over open work."""
    if result["blockers"]:
        return [f"blocked: {b}" for b in result["blockers"]]
    for key in result["to_close"]:
        try:
            jira.close(key)
        except SourceUnavailable as exc:
            return [str(exc)]
    return []
