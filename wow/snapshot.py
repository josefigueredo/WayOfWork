"""Persist the derived state as wow/progress.json with a compact history (spec 7.1)."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

PROGRESS_REL = Path("wow/progress.json")


def _git(project: Path, *args: str) -> Optional[str]:
    proc = subprocess.run(["git", "-C", str(project), *args], capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else None


def _utc(iso: str) -> str:
    # Python 3.9's fromisoformat rejects the "Z" git prints for UTC.
    value = iso.strip()
    value = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(value).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def backfill_points(project: Path, epic_by_key: Dict[str, str]) -> List[dict]:
    """History points rebuilt from every commit that touched specs/*/tasks.md, so velocity has the real burn-up
    of work done before the first snapshot. Points carry source "git" to stay distinguishable from snapshots."""
    from sources import speckit
    if _git(project, "rev-parse", "--git-dir") is None:
        return []
    points: List[dict] = []
    for spec in sorted((project / "specs").glob("*/spec.md")):
        match = speckit.EPIC_RE.search(spec.read_text(encoding="utf-8"))
        epic = epic_by_key.get(match.group(1)) if match else None
        if epic is None:
            continue
        rel = (spec.parent / "tasks.md").relative_to(project).as_posix()
        for line in (_git(project, "log", "--format=%H %cI", "--", rel) or "").splitlines()[::-1]:
            sha, iso = line.split(" ", 1)
            text = _git(project, "show", f"{sha}:{rel}")
            if text is None:
                continue
            parsed = speckit.parse_tasks(text)
            points.append({"ts": _utc(iso), "plan_phase": None, "phases": {}, "source": "git",
                           "tasks_done": parsed["done"], "tasks_total": parsed["total"],
                           "epics": {epic: {"done": parsed["done"], "total": parsed["total"]}}})
    return points


def merge_history(existing: List[dict], points: List[dict]) -> List[dict]:
    """Add backfilled points whose timestamp is not already in the history; existing points always win."""
    seen = {h.get("ts") for h in existing}
    merged = list(existing)
    for point in points:
        if point["ts"] not in seen:
            merged.append(point)
            seen.add(point["ts"])
    return sorted(merged, key=lambda h: str(h.get("ts") or ""))


def history_point(state: dict, now: str) -> dict:
    done = total = 0
    per_epic = {}
    for epic in state["epics"]:
        progress = epic.get("progress")
        if progress:
            d, t = (int(x) for x in progress.split("/"))
            done, total = done + d, total + t
            per_epic[epic["id"]] = {"done": d, "total": t}
    return {"ts": now, "plan_phase": state["plan"]["phase"],
            "phases": {e["id"]: e["phase"] for e in state["epics"]},
            "tasks_done": done, "tasks_total": total, "epics": per_epic}


def build(state: dict, previous: Optional[dict], now: str, usage: Optional[list] = None) -> dict:
    previous = previous or {}
    return {"schema_version": 1, "generated_at": now, "current": state,
            "history": list(previous.get("history", [])) + [history_point(state, now)],
            "usage": list(usage) if usage is not None else list(previous.get("usage", []))}


def load_previous(project: Path) -> Optional[dict]:
    path = project / PROGRESS_REL
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def write(project: Path, snap: dict) -> Path:
    path = project / PROGRESS_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
