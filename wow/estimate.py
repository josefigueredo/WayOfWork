"""Estimate an epic from past epics, and suggest a Cursor model per task (Product Brain and Spec-Kit do neither).

Calibration comes from finished epics: implementation minutes between feature.specified and feature.implemented
in the Spec-Kit ledger, against the work-unit hours tasks.shape estimated and the story points of the manifest;
review rounds per story and per epic; minutes per review round. Operator time (Product Brain, PRs) leaves no
readable trace, so it comes from configurable assumptions. Every component says which one it is.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import statistics
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import manifest

DEFAULTS = {"minutes_per_point": 20.0, "minutes_per_estimated_hour": 7.0, "rounds_per_story": 2.0,
            "rounds_per_epic": 2.0, "minutes_per_round": 18.0, "product_brain_minutes_per_chat": 20.0,
            "operator_minutes_per_story": 15.0, "hours_per_day": 4.0}
_DELICATE_COMPONENTS = {"INFRA", "DEVOPS", "AI"}
_DELICATE_LABELS = {"architecture", "arquitectura", "security", "seguridad", "migration", "migracion", "migración"}


def suggest_model(item: dict, cfg: dict) -> Tuple[str, str]:
    """Model for a manifest task or a Spec-Kit work unit. An explicit `model` on the task always wins."""
    models = cfg["models"]
    if item.get("model"):
        return item["model"], "set on the task"
    hours = item.get("estimated_hours")
    if isinstance(hours, (int, float)):
        if hours >= 4:
            return models["cursor_reason"], f"{hours:g} estimated hours"
        return models["cursor_generate"], f"{hours:g} estimated hours"
    if (item.get("component") or "").upper() in _DELICATE_COMPONENTS:
        return models["cursor_reason"], f"{item['component']} work"
    delicate = _DELICATE_LABELS.intersection(l.lower() for l in item.get("labels") or [])
    if delicate:
        return models["cursor_reason"], f"label {sorted(delicate)[0]}"
    if isinstance(item.get("estimate"), int) and item["estimate"] >= 5:
        return models["cursor_reason"], f"{item['estimate']} story points"
    return models["cursor_generate"], "small, routine change"


def _ts(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def _work_units(project: Path) -> List[dict]:
    paths = [project / ".spec-kit" / "work-units.json"] + sorted((project / "specs").glob("*/work-units.json"))
    for path in paths:
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            units = data.get("work_units", []) if isinstance(data, dict) else data
            return [u for u in units if isinstance(u, dict)]
    return []


def history_metrics(project: Path) -> dict:
    """What a finished epic measured. Missing pieces stay empty so they fall back to assumptions."""
    metrics: Dict[str, object] = {"impl_minutes": None, "est_hours": None, "story_points": None,
                                  "story_rounds": [], "epic_rounds": [], "round_minutes": []}
    ledger = project / ".spec-kit" / "history" / "changelog.jsonl"
    specified: Dict[str, dt.datetime] = {}
    total = 0.0
    if ledger.is_file():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            feature = row.get("feature_id")
            if row.get("event") == "feature.specified":
                specified[feature] = _ts(row["ts"])
            elif row.get("event") == "feature.implemented" and feature in specified:
                total += (_ts(row["ts"]) - specified[feature]).total_seconds() / 60
    metrics["impl_minutes"] = total or None
    hours = sum(u.get("estimated_hours") or 0 for u in _work_units(project))
    metrics["est_hours"] = hours or None
    try:
        doc = manifest.load(project)
        points = sum(t.get("estimate") or 0 for e in doc["epics"] if e.get("status") != "draft" for t in e["tasks"])
        metrics["story_points"] = points or None
    except manifest.ManifestError:
        pass
    for path in sorted((project / "wow" / "reviews").glob("*.json")):
        if path.stem.endswith(".standards"):
            continue
        try:
            summary = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        key = {"story": "story_rounds", "epic": "epic_rounds"}.get(summary.get("anchor_set"))
        if key and summary.get("rounds"):
            metrics[key].append(len(summary["rounds"]))
    # A round costs the review plus the fix before the next one, so its cost is the gap between consecutive rounds
    # of the same review. The reviewer call alone (duration_ms, under a minute) would undercount it ~10x.
    by_ref: Dict[str, List[dt.datetime]] = {}
    for path in sorted((project / "harness" / "reviews").glob("*.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if row.get("ts") and row.get("ref"):
            by_ref.setdefault(row["ref"], []).append(_ts(row["ts"]))
    for stamps in by_ref.values():
        stamps.sort()
        gaps = [(b - a).total_seconds() / 60 for a, b in zip(stamps, stamps[1:])]
        metrics["round_minutes"] += [g for g in gaps if 0 < g <= 180]  # longer gaps are waits (HITL, CI), not rounds
    return metrics


def _measured(values: List[float]) -> Optional[float]:
    return statistics.mean(values) if values else None


def add_working_days(start: dt.date, days: int) -> dt.date:
    current = start
    while days > 0:
        current += dt.timedelta(days=1)
        if current.weekday() < 5:
            days -= 1
    return current


def estimate(project: Path, histories: List[Path], cfg: dict, today: Optional[dt.date] = None) -> dict:
    knobs = dict(DEFAULTS, **(cfg.get("estimate") or {}))
    doc = manifest.load(project)
    epics = [e for e in doc["epics"] if e.get("status") != "draft"]
    tasks = [t for e in epics for t in e["tasks"]]
    past = [history_metrics(h) for h in histories]

    def ratio(num: str, den: str) -> Optional[float]:
        return _measured([m[num] / m[den] for m in past if m[num] and m[den]])

    components = []
    units = _work_units(project)
    unit_hours = sum(u.get("estimated_hours") or 0 for u in units)
    if unit_hours:
        per_hour = ratio("impl_minutes", "est_hours")
        rate = per_hour or knobs["minutes_per_estimated_hour"]
        components.append({"name": "implementation", "minutes": unit_hours * rate, "source": "measured" if per_hour else "assumed",
                           "basis": f"{unit_hours:g} work-unit hours x {rate:.1f} min per estimated hour"})
    else:
        per_point = ratio("impl_minutes", "story_points")
        rate = per_point or knobs["minutes_per_point"]
        points = sum(t.get("estimate") or 0 for t in tasks)
        components.append({"name": "implementation", "minutes": points * rate, "source": "measured" if per_point else "assumed",
                           "basis": f"{points} story points x {rate:.1f} min per point"})
    story_rounds = _measured([r for m in past for r in m["story_rounds"]])
    epic_rounds = _measured([r for m in past for r in m["epic_rounds"]])
    round_minutes = [x for m in past for x in m["round_minutes"]]
    per_round = statistics.median(round_minutes) if round_minutes else None
    rounds = len(tasks) * (story_rounds or knobs["rounds_per_story"]) + len(epics) * (epic_rounds or knobs["rounds_per_epic"])
    measured_reviews = story_rounds is not None and per_round is not None
    components.append({"name": "independent reviews", "minutes": rounds * (per_round or knobs["minutes_per_round"]),
                       "source": "measured" if measured_reviews else "assumed",
                       "basis": f"{rounds:.1f} rounds x {per_round or knobs['minutes_per_round']:.1f} min (HITL waits not included)"})
    chats = 2 + len(epics)  # PRD, RFC and one chat per epic (the PRISM pilot: 3 chats in 58 min)
    components.append({"name": "Product Brain", "minutes": chats * knobs["product_brain_minutes_per_chat"],
                       "source": "assumed", "basis": f"{chats} chats x {knobs['product_brain_minutes_per_chat']:g} min; "
                                                     "Product Brain leaves no readable timing"})
    components.append({"name": "operator", "minutes": len(tasks) * knobs["operator_minutes_per_story"], "source": "assumed",
                       "basis": f"{len(tasks)} stories x {knobs['operator_minutes_per_story']:g} min (PR, merge, sync-status)"})
    total = sum(c["minutes"] for c in components)
    spread = 0.3 if len([m for m in past if m["impl_minutes"]]) >= 2 else 0.5
    starts = [e.get("product", {}).get("start_date") for e in epics if (e.get("product") or {}).get("start_date")]
    today = today or dt.date.today()
    start = max([today] + [dt.date.fromisoformat(s) for s in starts])
    per_day = knobs["hours_per_day"] * 60

    def end(minutes: float) -> str:
        return add_working_days(start, max(1, math.ceil(minutes / per_day)) - 1).isoformat()

    return {"components": components, "minutes": total, "low_minutes": total * (1 - spread),
            "high_minutes": total * (1 + spread), "start": start.isoformat(), "end_likely": end(total),
            "end_high": end(total * (1 + spread)), "hours_per_day": knobs["hours_per_day"],
            "histories": len(past), "tasks": [dict(id=t["id"], title=t["title"], model=suggest_model(t, cfg)[0],
                                                   why=suggest_model(t, cfg)[1]) for t in tasks],
            "units": [dict(id=u["id"], model=suggest_model(u, cfg)[0], why=suggest_model(u, cfg)[1]) for u in units]}
