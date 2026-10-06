"""The Spec-Kit flow for one Jira epic key, independent of how the epic came to exist.

The key may come from Product Brain's export (the manifest), from jk create, or from `wow sk start KEY`. The flow
needs nothing else from Product Brain: `expected` (the manifest's story count) only tightens the check when there is
one, and `ref` names the epic's reviews (the manifest's epic id, or the key itself).

`state()` returns the phase and next steps (what state.compute_state ranks) and the checklist items (what wow progress
shows). Local items are derived from the repo even without Jira; Jira items are then unverified, never done.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import estimate
import sk
from checklist import Item
from sources import SourceUnavailable, speckit

REVIEW_CLOSED = ("approved", "approved_by_human")  # same as state.REVIEW_CLOSED; state imports this module
_REGISTRY = Path("wow") / "sk" / "epics.json"


def _review_final(project: Path, ref: str) -> Optional[str]:
    path = project / "wow" / "reviews" / f"{ref}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("final")
    except (json.JSONDecodeError, AttributeError):
        return None


def registered(project: Path) -> List[str]:
    path = project / _REGISTRY
    if not path.is_file():
        return []
    try:
        return [str(k) for k in json.loads(path.read_text(encoding="utf-8")).get("epics", [])]
    except (json.JSONDecodeError, AttributeError):
        return []


def register(project: Path, key: str) -> bool:
    keys = registered(project)
    if key in keys:
        return False
    path = project / _REGISTRY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"epics": keys + [key]}, indent=2) + "\n", encoding="utf-8")
    return True


def _step(epic, phase, action, where, model, command, why) -> dict:
    return {"epic": epic, "phase": phase, "action": action, "where": where,
            "model": model, "command": command, "why": why}


def _clarified(project: Path, feature: Optional[dict]) -> bool:
    if feature is None:
        return False
    spec = project / feature["dir"] / "spec.md"
    text = spec.read_text(encoding="utf-8") if spec.is_file() else ""
    return "## Clarifications" in text and "### Session" in text  # spec-kit.clarify.md:150-151 (65a6940)


def _items(project, key, ref, feature, mode, summary, reason) -> List[Item]:
    has = lambda flag: "done" if feature and feature[flag] else "todo"  # noqa: E731
    discovery = (project / ".spec-kit" / "discovery" / "architecture.md").is_file()
    out = [Item("discovery", "Discovery del código existente",
                "na" if mode == "greenfield" else ("done" if discovery else "todo"),
                "greenfield" if mode == "greenfield" else (".spec-kit/discovery/architecture.md" if discovery else "")),
           Item("sync", f"Sync de {key} en Spec-Kit", "done" if feature else "todo", feature["dir"] if feature else ""),
           Item("clarify", "Clarify ratificado", "done" if _clarified(project, feature) else "todo"),
           Item("plan", "Plan (plan.md)", has("has_plan")),
           Item("tasks", "Tareas (tasks.md)", has("has_tasks")),
           Item("work-units", "Work units (work-units.json)", has("has_work_units"))]
    if feature:
        pending = set(feature["pending_work_units"])
        out += [Item(f"wu-{wu}", f"Implementar {wu}", "todo" if wu in pending else "done") for wu in feature["units"]]
        for story, counts in sorted(feature["stories"].items()):
            if counts["done"] == counts["total"]:
                final = _review_final(project, story)
                out.append(Item(f"review-{story}", f"Review de {story}", "done" if final in REVIEW_CLOSED else "todo",
                                final or ""))
    if summary is None:
        out.append(Item("jira-done", "Historias en Done (sync-status, en Cursor)", "unverified", reason))
    else:
        out.append(Item("jira-done", "Historias en Done (sync-status, en Cursor)",
                        "done" if summary["stories"] and summary["done"] >= summary["stories"] else "todo",
                        f"{summary['done']} de {summary['stories']}"))
    final = _review_final(project, ref)
    out.append(Item("review-epic", f"Review de cierre de {ref}", "done" if final in REVIEW_CLOSED else "todo", final or ""))
    if summary is None or summary.get("epic_done") is None:
        out.append(Item("epic-closed", f"Épica {key} cerrada (wow close)", "unverified", reason or "jira no lo informa"))
    else:
        out.append(Item("epic-closed", f"Épica {key} cerrada (wow close)", "done" if summary["epic_done"] else "todo"))
    return out


def state(project: Path, cfg: dict, key: str, jira, expected: Optional[int] = None, ref: Optional[str] = None,
          mode: Optional[str] = None, features: Optional[List[dict]] = None) -> dict:
    models = cfg["models"]
    ref = ref or key
    features = speckit.features(project) if features is None else features
    feature = next((f for f in features if f["epic_key"] == key), None)
    out = {"phase": 4, "progress": None, "reason": None, "jira_url": None, "steps": [], "items": []}
    steps: List[dict] = out["steps"]
    summary, reason = None, ""

    def finish(phase):
        out["phase"] = phase
        out["items"] = _items(project, key, ref, feature, mode, summary, reason)
        return out

    if jira is None:
        out["reason"] = reason = "jira not configured"
        return finish("unknown")
    try:
        summary = jira.epic_summary(key)
    except SourceUnavailable as exc:
        out["reason"] = reason = str(exc)
        return finish("unknown")
    out["jira_url"] = summary["url"]
    if not summary["exists"] or summary["stories"] < (expected or 1):
        if expected:
            steps.append(_step(ref, 3, f"complete the stories of {key} in Jira", "product-brain", None,
                               "re-export the epic from Product Brain",
                               f"Jira has {summary['stories']} of {expected} stories"))
        else:
            steps.append(_step(ref, 3, f"add the stories of {key} in Jira", "human", None,
                               f"create them in Jira (or with jk) under {key}", f"{key} has no stories in Jira"))
        return finish(3)

    # Phase 4: Spec-Kit feature synced and planned.
    if feature is None and mode == "brownfield" \
            and not (project / ".spec-kit" / "discovery" / "architecture.md").is_file():
        # Spec-Kit plans brownfield work from its discovery; Product Brain does not need it.
        steps.append(_step(ref, 4, "run Spec-Kit discovery on the existing code", "cursor",
                           models["cursor_reason"], "/spec-kit.discovery",
                           "Spec-Kit plans brownfield epics from .spec-kit/discovery/architecture.md"))
        return finish(4)
    if feature is None:
        steps.append(_step(ref, 4, "sync the epic into Spec-Kit", "cursor", models["cursor_generate"],
                           sk.commands_for("sync", cfg, epic=key)[0], f"no specs/*/spec.md declares **Jira Epic:** {key}"))
        return finish(4)
    if not feature["has_plan"]:
        steps.append(_step(ref, 4, "ratify the plan", "cursor", models["cursor_reason"],
                           sk.commands_for("plan", cfg, feature=feature["dir"])[0], "plan.md is missing"))
        return finish(4)
    if not feature["has_tasks"] or not feature["has_work_units"]:
        steps.append(_step(ref, 4, "ratify tasks and work units", "cursor", models["cursor_reason"],
                           " then ".join(sk.commands_for("tasks", cfg, feature=feature["dir"])),
                           "tasks.md or work-units.json is missing"))
        return finish(4)

    # Phase 5: implementation and per-story independent review.
    out["progress"] = f"{feature['tasks_done']}/{feature['tasks_total']}"
    for wu in feature["pending_work_units"]:
        model, why = estimate.suggest_model(feature.get("units", {}).get(wu, {"id": wu}), cfg)
        steps.append(_step(ref, 5, f"implement {wu}", "cursor", model, f"/spec-kit.implement {wu}",
                           f"{wu} is not checked in tasks.md; model: {why}"))
    for story, counts in sorted(feature["stories"].items()):
        if counts["done"] == counts["total"] and _review_final(project, story) not in REVIEW_CLOSED:
            steps.append(_step(ref, 5, f"review story {story}", "harness", models["reviewer"],
                               f"wow review --set story --ref {story}",
                               "all its tasks are done and it has no approved review"))
    if not steps and feature["tasks_done"] < feature["tasks_total"]:
        # Every unit is done but tasks with no unit (setup, closing checks) are unchecked: name them, never stall.
        unchecked = feature.get("unchecked_tasks") or []
        steps.append(_step(ref, 5, f"finish or check the remaining tasks: {', '.join(unchecked)}", "cursor", None,
                           f"check them in {feature['dir']}/tasks.md once each is done or verified",
                           f"{feature['tasks_total'] - feature['tasks_done']} task(s) unchecked with every work unit done"))
    if steps or feature["tasks_done"] < feature["tasks_total"]:
        return finish(5)

    # Phase 6: Jira closed and epic closure review.
    if summary["done"] < summary["stories"]:
        steps.append(_step(ref, 6, f"close the stories of {key} in Jira", "cursor", None,
                           sk.commands_for("sync-status", cfg, feature=feature["dir"])[0],
                           f"{summary['done']} of {summary['stories']} stories are done in Jira"))
    if _review_final(project, ref) not in REVIEW_CLOSED:
        steps.append(_step(ref, 6, f"review epic {ref}", "harness", models["reviewer"],
                           f"wow review --set epic --ref {ref}", "the epic has no approved closure review"))
    elif not steps and summary.get("epic_done") is False:
        # /sync-status closes only stories; subtasks and the epic stay open unless someone closes them.
        steps.append(_step(ref, 6, f"close the subtasks and the epic {key} in Jira", "terminal", None,
                           f"wow close --epic {ref}", "the closure review is approved but the epic is open in Jira"))
    if _review_final(project, ref) in REVIEW_CLOSED and not (project / "wow" / "reviews" / f"{ref}.standards.json").is_file():
        # Recommended, never blocking: a repo with no golden rules and no documented conventions has nothing to
        # review against, and that must not keep the epic from closing.
        step = _step(ref, 6, "review the epic diff against the repo standards", "harness", models["reviewer"],
                     f"wow review --set standards --ref {ref}", "second axis: golden rules, not the stories")
        step["recommended"] = True
        steps.append(step)
    return finish(6 if any(not s.get("recommended") for s in steps) else "done")
