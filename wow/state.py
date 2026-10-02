"""Derive plan and epic phases plus ranked next steps from the read-only sources (spec 6)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import manifest
import pbcompletion
from sources import SourceUnavailable, pbchat, repo, speckit

_WHERE_RANK = {"human": 0, "harness": 1, "product-brain": 1, "terminal": 1, "cursor": 2}
_CHAT_LABEL = {"prd": "PRD", "rfc": "RFC"}


def review_final(project: Path, ref: str) -> Optional[str]:
    path = project / "wow" / "reviews" / f"{ref}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("final")
    except (json.JSONDecodeError, AttributeError):
        return None


def _step(epic, phase, action, where, model, command, why) -> dict:
    return {"epic": epic, "phase": phase, "action": action, "where": where,
            "model": model, "command": command, "why": why}


def compute_state(project: Path, cfg: dict, jira=None) -> dict:
    models = cfg["models"]
    steps: List[dict] = []
    blockers: List[str] = []
    sources = {"jira": "ok" if jira is not None else "not_configured"}
    plan = {"id": None, "phase": 3, "stale_packets": [], "missing": []}
    epics_out: List[dict] = []

    # Phase 0: context pack. Open owner items block phase 0 but planning continues in parallel.
    cp = repo.context_pack_status(project)
    if not cp["facts"] or not cp["pending_file"]:
        plan["phase"] = 0
        steps.append(_step(None, 0, "build the context pack", "harness", models["author"], "wow-context",
                           "wow/context-pack/facts.md and pending-owner.md are required before planning"))
    if cp["pending_open"]:
        plan["phase"] = 0
        blockers.append(f"owner: {cp['pending_open']} decision(s) open in wow/context-pack/pending-owner.md")

    # Phase 1: manifest and readiness.
    doc = None
    try:
        doc = manifest.load(project)
    except manifest.ManifestError as exc:
        plan["phase"] = min(plan["phase"], 1)
        if "not found" in str(exc):
            steps.append(_step(None, 1, "plan the initiative", "harness", models["author"], "wow-plan",
                               "there is no wow/plan/manifest.json yet"))
        else:
            steps.append(_step(None, 1, "fix the manifest", "harness", models["author"], "wow manifest validate",
                               str(exc)))
    if doc is not None:
        errors = manifest.validate(doc)
        if errors:
            plan["phase"] = min(plan["phase"], 1)
            steps.append(_step(None, 1, "fix the manifest", "harness", models["author"], "wow manifest validate",
                               errors[0]))
            doc = None
    if doc is not None:
        plan["id"] = doc["plan"]["id"]
        mode = doc["plan"].get("mode")
        if mode not in manifest.MODES:
            steps.append(_step(None, 1, "set the plan mode", "harness", models["author"],
                               "wow plan init --mode greenfield|brownfield (or edit plan.mode)",
                               "greenfield and brownfield change phase 0 and the packet prompts"))
        elif mode == "brownfield" and not (project / ".spec-kit" / "discovery" / "architecture.md").is_file():
            steps.append(_step(None, 0, "run Spec-Kit discovery on the existing code", "cursor",
                               models["cursor_reason"], "/spec-kit.discovery",
                               "brownfield plans cite the real architecture from .spec-kit/discovery/architecture.md"))
        lint = manifest.lint(doc)
        if lint:
            plan["phase"] = min(plan["phase"], 1)
            steps.append(_step(None, 1, "complete the plan", "harness", models["author"], "wow-plan",
                               f"{len(lint)} lint finding(s), first: {lint[0]}"))
        elif doc["plan"]["readiness"]["verdict"] != "approved":
            plan["phase"] = min(plan["phase"], 1)
            steps.append(_step(None, 1, "run the readiness review", "harness", models["reviewer"],
                               "wow review --set readiness --ref plan",
                               f"readiness verdict is {doc['plan']['readiness']['verdict']}"))
        # Phase 2: packets carry the current manifest hash. Draft epics are not sent to Product Brain.
        epic_ids = [e["id"] for e in doc["epics"] if e.get("status") != "draft"]
        packets = repo.packet_status(project, manifest.manifest_hash(project), epic_ids)
        named = [("prd", "prd", None), ("rfc", "rfc", None)] + \
                [(f"epic-{eid}", "epic", eid) for eid in epic_ids]
        for name, kind, eid in named:
            status = packets["epics"][eid] if eid else packets[name]
            if status == "ok":
                check = pbcompletion.check_file(project, name)
                if check and (check["percentage"] < 100 or check["errors"]):
                    plan["phase"] = min(plan["phase"], 2)
                    target = f"epic --id {eid}" if eid else kind
                    steps.append(_step(None, 2, f"complete the {name} packet", "harness", models["author"],
                                       f"wow-pack, then wow pack check {target}",
                                       f"predicted completion {check['percentage']}%, {len(check['errors'])} error(s)"))
                continue
            if status == "stale":
                plan["stale_packets"].append(name)
            plan["phase"] = min(plan["phase"], 2)
            command = f"wow pack {kind}" + (f" --id {eid}" if eid else "")
            verb = "regenerate" if status == "stale" else "generate"
            steps.append(_step(None, 2, f"{verb} the {name} packet", "harness", models["author"], command,
                               f"wow/pb/{name}.md is {status}"))

    plan["missing"] = [s["action"] for s in steps if s["epic"] is None]

    if doc is not None:
        features = speckit.features(project)
        for epic in doc["epics"]:
            if epic.get("status") == "draft":
                epics_out.append({"id": epic["id"], "title": epic["title"], "jira": None, "jira_url": None,
                                  "phase": "draft", "reason": "draft: not sent to Product Brain",
                                  "progress": None, "missing": []})
                continue
            out = _epic_state(project, cfg, doc, epic, features, jira, plan["phase"], sources)
            epics_out.append(out["epic"])
            steps.extend(out["steps"])

    ranked = sorted(steps, key=lambda s: (_WHERE_RANK[s["where"]], s["phase"]))
    return {"schema_version": 1, "plan": plan, "epics": epics_out, "blockers": blockers,
            "next_steps": ranked[:3], "steps_total": len(steps), "sources": sources}


def _epic_state(project, cfg, doc, epic, features, jira, plan_phase, sources) -> dict:
    models = cfg["models"]
    eid = epic["id"]
    key = doc["plan"]["export"]["epics"].get(eid)
    out = {"id": eid, "title": epic["title"], "jira": key, "jira_url": None,
           "phase": plan_phase, "reason": None, "progress": None, "missing": []}
    steps: List[dict] = []

    def finish(phase):
        out["phase"] = phase
        out["missing"] = [s["action"] for s in steps]
        return {"epic": out, "steps": steps}

    if plan_phase < 3:
        return finish(plan_phase)

    # Phase 3: PRD, RFC and epic chats closed and audited, epic exported with all stories.
    for doc_name in ("prd", "rfc", f"epic-{eid}"):
        label = _CHAT_LABEL.get(doc_name, f"epic {eid}")
        chat = pbchat.chat_status(project, doc_name)
        if not chat["present"] or not chat["closed"]:
            steps.append(_step(eid, 3, f"finish the {label} chat in Product Brain", "product-brain",
                               models["product_brain"], f"paste the preamble and wow/pb/{doc_name}.md",
                               f"wow/pb/chats/{doc_name}.md is missing or not closed"))
            return finish(3)
        if chat["audit"] != "approved":
            steps.append(_step(eid, 3, f"audit the {label} chat", "harness", models["reviewer"], "wow-pb-audit",
                               f"audit verdict is {chat['audit']}"))
            return finish(3)
    if not key:
        steps.append(_step(eid, 3, f"export epic {eid} to Jira and record its key", "product-brain", None,
                           f"wow plan freeze --epics {eid}=<KEY>", "the manifest has no Jira key for this epic"))
        return finish(3)
    if jira is None:
        out["reason"] = "jira not configured"
        return finish("unknown")
    try:
        summary = jira.epic_summary(key)
    except SourceUnavailable as exc:
        sources["jira"] = str(exc)
        out["reason"] = str(exc)
        return finish("unknown")
    out["jira_url"] = summary["url"]
    expected = len(epic["tasks"])
    if not summary["exists"] or summary["stories"] < expected:
        steps.append(_step(eid, 3, f"complete the stories of {key} in Jira", "product-brain", None,
                           "re-export the epic from Product Brain",
                           f"Jira has {summary['stories']} of {expected} stories"))
        return finish(3)

    # Phase 4: Spec-Kit feature synced and planned.
    feature = next((f for f in features if f["epic_key"] == key), None)
    if feature is None:
        steps.append(_step(eid, 4, "sync the epic into Spec-Kit", "cursor", models["cursor_generate"],
                           f"wow sk cmd sync --epic {key}", f"no specs/*/spec.md declares **Jira Epic:** {key}"))
        return finish(4)
    if not feature["has_plan"]:
        steps.append(_step(eid, 4, "ratify the plan", "cursor", models["cursor_reason"],
                           f"wow sk cmd plan --feature {feature['dir']}", "plan.md is missing"))
        return finish(4)
    if not feature["has_tasks"] or not feature["has_work_units"]:
        steps.append(_step(eid, 4, "ratify tasks and work units", "cursor", models["cursor_reason"],
                           f"wow sk cmd tasks --feature {feature['dir']}", "tasks.md or work-units.json is missing"))
        return finish(4)

    # Phase 5: implementation and per-story independent review.
    out["progress"] = f"{feature['tasks_done']}/{feature['tasks_total']}"
    for wu in feature["pending_work_units"]:
        steps.append(_step(eid, 5, f"implement {wu}", "cursor", models["cursor_generate"], f"wow run-wu {wu}",
                           f"{wu} is not checked in tasks.md"))
    for story, counts in sorted(feature["stories"].items()):
        if counts["done"] == counts["total"] and review_final(project, story) != "approved":
            steps.append(_step(eid, 5, f"review story {story}", "harness", models["reviewer"],
                               f"wow review --set story --ref {story}",
                               "all its tasks are done and it has no approved review"))
    if steps or feature["tasks_done"] < feature["tasks_total"]:
        return finish(5)

    # Phase 6: Jira closed and epic closure review.
    if summary["done"] < summary["stories"]:
        steps.append(_step(eid, 6, f"close the stories of {key} in Jira", "terminal", None,
                           f"spec-kit sync-status {feature['dir']} --dry-run",
                           f"{summary['done']} of {summary['stories']} stories are done in Jira"))
    if review_final(project, eid) != "approved":
        steps.append(_step(eid, 6, f"review epic {eid}", "harness", models["reviewer"],
                           f"wow review --set epic --ref {eid}", "the epic has no approved closure review"))
    return finish(6 if steps else "done")
