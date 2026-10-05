"""Put back on the Jira stories what Product Brain's export leaves wrong, from the manifest.

Product Brain (acme-agent @ 9b19a89) copies the epic's labels and priority to every story (jira.exporter.ts:551-616).
A component the Jira project does not have is caught by PB's export preflight (jira.preflight.ts:116-120) and listed
in the export modal with "Omitir en los issues" preselected (export-modal.tsx:364-371): exported as is, the stories
get no component. It also looks for story points in the first float field of the instance (jira.client.ts:1342-1348), which can be any
number field ("Valor del Riesgo" in the IRIS pilot's Jira).

The lint warns before the export; `wow jira fix-fields` repairs after it (dry run by default, the user applies).
WoW never invents a component: one the project does not have is reported and left out.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

import manifest

# Story points fields by name, most specific first; any other number field is not story points.
_POINTS_NAMES = ("story point estimate", "story points", "estimación de puntos de historia", "puntos de historia")
_PRIORITY_ALIASES = {"highest": ("highest", "muy alta"), "high": ("high", "alta"), "medium": ("medium", "media"),
                     "low": ("low", "baja"), "lowest": ("lowest", "muy baja")}
_PREFIX_RE = re.compile(r"^\s*\[[^\]]+\]\s*")


def points_field(edit_fields: Dict[str, str]) -> Optional[str]:
    """The story points field on an issue's edit screen ({field id: name}), chosen by name."""
    by_name = {name.strip().lower(): fid for fid, name in edit_fields.items()}
    return next((by_name[name] for name in _POINTS_NAMES if name in by_name), None)


def project_key(doc: dict, creds_project: Optional[str]) -> Optional[str]:
    keys = list(((doc.get("plan") or {}).get("export") or {}).get("epics", {}).values())
    return keys[0].split("-")[0] if keys else creds_project


def _match(component: str, available: List[str]) -> Optional[str]:
    return next((name for name in available if name.lower() == component.lower()), None)


def component_findings(doc: dict, available: List[str], key: str) -> List[str]:
    findings = []
    for epic in doc.get("epics", []):
        for task in epic.get("tasks", []):
            component = task.get("component")
            if component and _match(component, available) is None:
                findings.append(
                    f"{task['id']}: component {component} is not in Jira project {key} ({', '.join(available) or '-'}): "
                    f"Product Brain's export modal preselects \"Omitir en los issues\" for it, so the story gets no "
                    f"component; map it there to an existing one, ask a Jira admin to create it, or leave it empty")
    return findings


def _title(summary: str) -> str:
    return _PREFIX_RE.sub("", summary or "").strip().casefold()


def _priority(value: Optional[str], names: List[str]) -> Optional[str]:
    aliases = _PRIORITY_ALIASES.get((value or "").lower(), ())
    return next((name for name in names if name.lower() in aliases), None)


def plan(project: Path, epic_id: str, jira) -> dict:
    doc = manifest.load(project)
    key = doc["plan"]["export"]["epics"].get(epic_id)
    result = {"epic": epic_id, "key": key, "blockers": [], "changes": [], "unmatched": []}
    if not key:
        result["blockers"].append(f"{epic_id} is not exported to Jira: run wow plan freeze --epics {epic_id}=<KEY>")
        return result
    epic = next((e for e in doc["epics"] if e["id"] == epic_id), None)
    if epic is None:
        result["blockers"].append(f"{epic_id} is not in the manifest")
        return result
    pkey = key.split("-")[0]
    components = jira.project_components(pkey)
    priorities = jira.priority_names()
    tasks = {_title(t["title"]): t for t in epic.get("tasks", [])}
    for story in jira.stories_of(key):
        task = tasks.get(_title(story["summary"]))
        if task is None:
            result["unmatched"].append(f"{story['key']} \"{story['summary']}\": no task of {epic_id} has that title")
            continue
        fields, skipped = {}, []
        component = task.get("component")
        if component:
            name = _match(component, components)
            if name is None:
                skipped.append(f"component {component} is not in {pkey} ({', '.join(components) or '-'})")
            elif story.get("components") != [name]:
                fields["components"] = [{"name": name}]
        if task.get("estimate") is not None and story.get("points") != task["estimate"]:
            fid = points_field(jira.edit_fields(story["key"]))
            if fid is None:
                skipped.append("no story points field on its edit screen")
            else:
                fields[fid] = task["estimate"]
        wanted = _priority(task.get("priority"), priorities)
        if task.get("priority") and wanted is None:
            skipped.append(f"priority {task['priority']} has no match in Jira ({', '.join(priorities)})")
        elif wanted and story.get("priority") != wanted:
            fields["priority"] = {"name": wanted}
        if task.get("labels") is not None and sorted(story.get("labels") or []) != sorted(task["labels"]):
            fields["labels"] = list(task["labels"])
        if fields or skipped:
            result["changes"].append({"key": story["key"], "task": task["id"], "fields": fields, "skipped": skipped})
    result["changes"] = [c for c in result["changes"] if c["fields"] or c["skipped"]]
    return result


def apply(result: dict, jira) -> List[str]:
    errors = []
    for change in result["changes"]:
        if not change["fields"]:
            continue
        try:
            jira.update(change["key"], change["fields"])
        except Exception as exc:  # noqa: BLE001 — one rejected issue must not hide the others
            errors.append(f"{change['key']}: {exc}")
    return errors
