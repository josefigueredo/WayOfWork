"""Persist the derived state as wow/progress.json with a compact history (spec 7.1)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

PROGRESS_REL = Path("wow/progress.json")


def history_point(state: dict, now: str) -> dict:
    done = total = 0
    for epic in state["epics"]:
        progress = epic.get("progress")
        if progress:
            d, t = progress.split("/")
            done, total = done + int(d), total + int(t)
    return {"ts": now, "plan_phase": state["plan"]["phase"],
            "phases": {e["id"]: e["phase"] for e in state["epics"]},
            "tasks_done": done, "tasks_total": total}


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
