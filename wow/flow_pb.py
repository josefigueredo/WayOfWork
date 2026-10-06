"""The Product Brain flow as a checklist: context, plan, packets, chats, export and the Jira repair.

Every item reads the same sources and applies the same rules as state.compute_state, so the checklist and the next
steps never disagree. The flow ends when each epic is exported with all its stories and its fields repaired; what
Spec-Kit does with the epic belongs to the other flow (flow_sk).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Tuple

import manifest
import pbcompletion
from checklist import Item
from sources import SourceUnavailable, pbchat, repo
from state import REVIEW_CLOSED

_LABEL = {"prd": "PRD", "rfc": "RFC"}


def _jira_summary(jira, key: str) -> Tuple[Optional[dict], str]:
    if jira is None:
        return None, "jira no configurado"
    try:
        return jira.epic_summary(key), ""
    except SourceUnavailable as exc:
        return None, str(exc)


def _fixed(project: Path, story_keys: List[str]) -> bool:
    """Whether `wow jira fix-fields --apply` wrote to any story of the epic (harness/jira-writes.jsonl)."""
    path = project / "harness" / "jira-writes.jsonl"
    if not path.is_file():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(entry.get("command", "")).startswith("jira fix-fields") and entry.get("key") in story_keys:
            return True
    return False


def items(project: Path, cfg: dict, jira) -> List[Item]:
    cp = repo.context_pack_status(project)
    out = [Item("context", "Context pack", "done" if cp["facts"] and cp["pending_file"] else "todo",
                "wow/context-pack/facts.md"),
           Item("owner", "Decisiones del owner cerradas", "done" if cp["pending_file"] and not cp["pending_open"]
                else "todo", f"{cp['pending_open']} abiertas" if cp["pending_open"] else "")]
    try:
        doc = manifest.load(project)
        problems = manifest.validate(doc) or manifest.lint(doc)
    except manifest.ManifestError as exc:
        doc, problems = None, [str(exc)]
    if doc is None or problems:
        out.append(Item("manifest", "Plan (wow/plan/manifest.json) válido y completo", "todo",
                        problems[0] if problems else ""))
        return out
    out.append(Item("manifest", "Plan (wow/plan/manifest.json) válido y completo", "done", doc["plan"]["id"]))
    verdict = doc["plan"]["readiness"]["verdict"]
    out.append(Item("readiness", "Readiness aprobado", "done" if verdict == "approved" else "todo", verdict))

    export = doc["plan"]["export"]
    epics = [e for e in doc["epics"] if e.get("status") != "draft"]
    mhash = manifest.manifest_hash(project)
    packets = repo.packet_status(project, mhash, [e["id"] for e in epics])

    def packet(item_id: str, name: str, status: str, exported: bool) -> Item:
        label = f"Paquete {_LABEL.get(name, name)} al 100%"
        if exported:  # once in Jira, Product Brain never asks for this packet again
            return Item(item_id, label, "done", "ya exportado")
        check = pbcompletion.check_file(project, name) if status == "ok" else None
        ready = status == "ok" and (check is None or pbcompletion.ready(check))
        note = f"wow/pb/{name}.md {check['percentage']}%" if check else f"wow/pb/{name}.md {status}"
        return Item(item_id, label, "done" if ready else "todo", note)

    out.append(packet("packet-prd", "prd", packets["prd"], export["frozen"]))
    out.append(packet("packet-rfc", "rfc", packets["rfc"], export["frozen"]))
    for epic in epics:
        out.append(packet(f"packet-{epic['id']}", f"epic-{epic['id']}", packets["epics"][epic["id"]],
                          bool(export["epics"].get(epic["id"]))))

    def chat(item_id: str, name: str, label: str, key: Optional[str]) -> Item:
        status = pbchat.chat_status(project, name)
        finished = status["present"] and (status["closed"] or bool(key))
        audited = status["audit"] in REVIEW_CLOSED
        note = "" if finished and audited else ("falta el chat" if not finished else f"auditoría: {status['audit']}")
        return Item(item_id, f"Chat {label} cerrado y auditado", "done" if finished and audited else "todo", note)

    first_key = next((export["epics"].get(e["id"]) for e in epics if export["epics"].get(e["id"])), None)
    out.append(chat("chat-prd", "prd", "PRD", first_key))
    out.append(chat("chat-rfc", "rfc", "RFC", first_key))
    for epic in epics:
        eid, key = epic["id"], export["epics"].get(epic["id"])
        out.append(chat(f"chat-{eid}", f"epic-{eid}", f"de la épica {eid}", key))
        out.append(Item(f"export-{eid}", f"Épica {eid} exportada a Jira", "done" if key else "todo", key or ""))
        if not key:
            continue
        found, reason = _jira_summary(jira, key)
        expected = len(epic["tasks"])
        if found is None:
            out.append(Item(f"stories-{eid}", f"Historias de {key} completas en Jira", "unverified", reason))
            out.append(Item(f"fix-fields-{eid}", f"Campos de {key} corregidos (wow jira fix-fields)", "unverified",
                            reason))
            continue
        complete = found["exists"] and found["stories"] >= expected
        out.append(Item(f"stories-{eid}", f"Historias de {key} completas en Jira", "done" if complete else "todo",
                        f"{found['stories']} de {expected}"))
        label = f"Campos de {key} corregidos (wow jira fix-fields)"
        if not (project / "harness" / "jira-writes.jsonl").is_file():
            # No log at all (it exists since 2026-10-05): nothing says whether a repair ran before it, so say how to
            # check instead of calling it pending. The dry run lists what is still wrong.
            out.append(Item(f"fix-fields-{eid}", label, "unverified",
                            f"sin registro de escrituras; revisalo con wow jira fix-fields --epic {eid} (simulación)"))
            continue
        fixed = _fixed(project, found.get("story_keys") or [])
        out.append(Item(f"fix-fields-{eid}", label, "done" if fixed else "todo",
                        "harness/jira-writes.jsonl" if fixed else ""))
    return out
