"""wow progress: one checklist per flow in wow/checklists/, and the one-line summary the statusline shows.

`write` reads every source (Jira included) and rewrites the checklists, keeping each file's manual section.
`line` only reads wow/checklists/progress.json: ccstatusline gives a widget one second, so it never touches the network.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import checklist
import flow_pb
import flow_sk
import manifest

DIR = Path("wow") / "checklists"


def _keys(project: Path) -> List[Tuple[str, Optional[int], Optional[str], Optional[str]]]:
    """(key, expected stories, review ref, plan mode) for every epic the Spec-Kit flow follows."""
    out, seen, mode = [], set(), None
    try:
        doc = manifest.load(project)
        mode = doc["plan"].get("mode")
        for epic in doc["epics"]:
            key = doc["plan"]["export"]["epics"].get(epic["id"])
            if key and epic.get("status") != "draft":
                out.append((key, len(epic["tasks"]), epic["id"], mode))
                seen.add(key)
    except (manifest.ManifestError, KeyError, TypeError):
        pass
    out += [(key, None, None, mode) for key in flow_sk.registered(project) if key not in seen]
    return out


def _one(path: Path, title: str, derived: List[checklist.Item], name: str, unproven: List[str]) -> Dict[str, int]:
    previous = path.read_text(encoding="utf-8") if path.is_file() else ""
    manual = checklist.manual_section(previous)
    unproven += [f"{name}: {label}" for label in checklist.unproven(previous)]
    path.write_text(checklist.render(title, derived, manual), encoding="utf-8")
    everything = derived + checklist.manual_items(previous)
    counted = [i for i in everything if i.state != "na"]
    return {"percent": checklist.percent(everything), "done": sum(i.state == "done" for i in counted),
            "total": len(counted)}


class _Once:
    """One epic_summary per key for the whole run: both flows read the same epic, and with Jira down each read
    costs the client's timeout. A failure is remembered too, so it is not paid twice."""

    def __init__(self, jira):
        self._jira, self._seen = jira, {}

    def epic_summary(self, key: str) -> dict:
        if key not in self._seen:
            try:
                self._seen[key] = (self._jira.epic_summary(key), None)
            except Exception as exc:  # noqa: BLE001 — replayed to every caller, exactly as raised
                self._seen[key] = (None, exc)
        found, error = self._seen[key]
        if error is not None:
            raise error
        return found

    def __getattr__(self, name):
        return getattr(self._jira, name)


def write(project: Path, cfg: dict, jira) -> dict:
    jira = _Once(jira) if jira is not None else None
    base = project / DIR
    base.mkdir(parents=True, exist_ok=True)
    unproven: List[str] = []
    result = {"pb": _one(base / "pb.md", "Flujo PB · Product Brain", flow_pb.items(project, cfg, jira), "pb", unproven),
              "sk": {}, "manual_without_evidence": unproven}
    for key, expected, ref, mode in _keys(project):
        items = flow_sk.state(project, cfg, key, jira, expected=expected, ref=ref, mode=mode)["items"]
        result["sk"][key] = _one(base / f"sk-{key}.md", f"Flujo SK · Spec-Kit · {key}", items, f"sk {key}", unproven)
    (base / "progress.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def line(cwd: Path) -> str:
    for folder in [cwd, *cwd.parents]:
        path = folder / DIR / "progress.json"
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            parts = [f"PB {data['pb']['percent']}%"] + [f"SK {key} {v['percent']}%" for key, v in data["sk"].items()]
            return " · ".join(parts)
    return ""
