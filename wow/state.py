"""Derive plan and epic phases plus ranked next steps from the read-only sources (spec 6)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import manifest
import pbcompletion
import flow_sk
import sk
from sources import SourceUnavailable, pbchat, repo, speckit

_WHERE_RANK = {"human": 0, "harness": 1, "product-brain": 1, "terminal": 1, "cursor": 2}
_CHAT_LABEL = {"prd": "PRD", "rfc": "RFC"}
# A review is closed by the reviewer's approval or, after HITL, by a recorded human approval.
REVIEW_CLOSED = ("approved", "approved_by_human")


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
    plan = {"id": None, "phase": 3, "stale_packets": [], "missing": [], "parked": False}
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
                               "greenfield and brownfield change phase 0 and where Spec-Kit discovery fits"))
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
        # A plan whose epics are all draft is parked: nothing goes to Product Brain, not even its PRD or RFC.
        plan["parked"] = not epic_ids
        packets = repo.packet_status(project, manifest.manifest_hash(project), epic_ids)
        # Once exported, Jira rules: a packet already in Product Brain is never asked for again. The PRD and RFC
        # went with the first export; only epics without a Jira key still need theirs.
        export = doc["plan"]["export"]
        pending_ids = [eid for eid in epic_ids if not export["epics"].get(eid)]
        named = [] if plan["parked"] else \
            ([] if export["frozen"] else [("prd", "prd", None), ("rfc", "rfc", None)]) + \
            [(f"epic-{eid}", "epic", eid) for eid in pending_ids]
        for name, kind, eid in named:
            status = packets["epics"][eid] if eid else packets[name]
            if status == "ok":
                check = pbcompletion.check_file(project, name)
                if check and not pbcompletion.ready(check):
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

    exported = {e["jira"] for e in epics_out if e.get("jira")}
    mode = doc["plan"].get("mode") if doc is not None else None
    for key in flow_sk.registered(project):  # epics that reach Spec-Kit without Product Brain (jk, by hand)
        if key in exported:
            continue
        shell = {"id": key, "title": key, "jira": key, "jira_url": None, "phase": 4, "reason": None,
                 "progress": None, "missing": []}
        out = _sk_epic(project, cfg, shell, key, jira, sources, mode=mode)
        epics_out.append(out["epic"])
        steps.extend(out["steps"])

    ranked = sorted(steps, key=lambda s: (_WHERE_RANK[s["where"]], s["phase"]))
    return {"schema_version": 1, "plan": plan, "epics": epics_out, "blockers": blockers,
            "next_steps": ranked[:3], "steps_total": len(steps), "sources": sources}


def _epic_state(project, cfg, doc, epic, features, jira, plan_phase, sources) -> dict:
    """Product Brain's phase 3 while the epic has no Jira key; with a key, the Spec-Kit flow (flow_sk) takes over.

    The two flows meet only at the key: once the epic is in Jira, what Product Brain still lacks (a chat, an audit)
    shows in its own checklist and no longer holds Spec-Kit back.
    """
    models = cfg["models"]
    eid = epic["id"]
    key = doc["plan"]["export"]["epics"].get(eid)
    out = {"id": eid, "title": epic["title"], "jira": key, "jira_url": None,
           "phase": plan_phase, "reason": None, "progress": None, "missing": []}
    steps: List[dict] = []

    def finish(phase):
        out["phase"] = phase
        out["missing"] = [s["action"] for s in steps if not s.get("recommended")]
        return {"epic": out, "steps": steps}

    if key:
        # Product Brain only registers the work: once the epic is in Jira, what its chats still lack is recommended,
        # never blocking. A human rejection is the one exception: someone decided the document is wrong.
        for doc_name in ("prd", "rfc", f"epic-{eid}"):
            label = _CHAT_LABEL.get(doc_name, f"epic {eid}")
            chat = pbchat.chat_status(project, doc_name)
            if not chat["present"]:
                step = _step(eid, 3, f"copy the {label} chat from Product Brain", "product-brain", None,
                             f"save it as wow/pb/chats/{doc_name}.md", "the audit needs the local copy")
            elif chat["audit"] not in REVIEW_CLOSED:
                step = _step(eid, 3, f"audit the {label} chat", "harness", models["reviewer"], "wow-pb-audit",
                             f"audit verdict is {chat['audit']}")
                if chat["audit"] == "rejected_by_human":
                    steps.append(step)
                    return finish(3)
            else:
                continue
            step["recommended"] = True
            steps.append(step)
        result = _sk_epic(project, cfg, out, key, jira, sources, expected=len(epic["tasks"]), ref=eid,
                          mode=doc["plan"].get("mode"), features=features)
        result["steps"] = steps + result["steps"]
        return result
    if plan_phase < 3:
        return finish(plan_phase)

    # Phase 3: PRD, RFC and epic chats closed and audited, then the epic exported.
    for doc_name in ("prd", "rfc", f"epic-{eid}"):
        label = _CHAT_LABEL.get(doc_name, f"epic {eid}")
        chat = pbchat.chat_status(project, doc_name)
        if not chat["present"] or not chat["closed"]:
            steps.append(_step(eid, 3, f"finish the {label} chat in Product Brain", "product-brain",
                               models["product_brain"], f"paste the preamble and wow/pb/{doc_name}.md",
                               f"wow/pb/chats/{doc_name}.md is missing or not closed"))
            return finish(3)
        if chat["audit"] not in REVIEW_CLOSED:  # the owner may accept a document they decide not to correct
            steps.append(_step(eid, 3, f"audit the {label} chat", "harness", models["reviewer"], "wow-pb-audit",
                               f"audit verdict is {chat['audit']}"))
            return finish(3)
    steps.append(_step(eid, 3, f"export epic {eid} to Jira and record its key", "product-brain", None,
                       f"wow plan freeze --epics {eid}=<KEY>", "the manifest has no Jira key for this epic"))
    return finish(3)


def _sk_epic(project, cfg, out, key, jira, sources, expected=None, ref=None, mode=None, features=None) -> dict:
    result = flow_sk.state(project, cfg, key, jira, expected=expected, ref=ref, mode=mode, features=features)
    if result["phase"] == "unknown" and result["reason"] != "jira not configured":
        sources["jira"] = result["reason"]
    out.update({"phase": result["phase"], "reason": result["reason"], "progress": result["progress"],
                "jira_url": result["jira_url"],
                "missing": [s["action"] for s in result["steps"] if not s.get("recommended")]})
    return {"epic": out, "steps": result["steps"]}
