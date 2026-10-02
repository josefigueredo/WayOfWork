"""Extra evidence the dashboard needs: Product Brain chat status, review summaries and pricing (spec 7.1, 8)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import pbcompletion
from sources import pbchat

PB_KEYS = ("present", "closed", "audit", "completion_pct", "inventions", "missing_anchors", "open_questions",
           "packet_pct", "packet_errors")


def _count(value) -> int:
    return len(value) if isinstance(value, list) else 0


def pb_status(project: Path, epic_ids: List[str]) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for doc in ["prd", "rfc"] + [f"epic-{eid}" for eid in epic_ids]:
        chat = pbchat.chat_status(project, doc)
        entry = {key: None for key in PB_KEYS}
        entry.update({"present": chat["present"], "closed": chat["closed"], "audit": chat["audit"]})
        path = project / "wow" / "pb" / "chats" / f"{doc}.audit.json"
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = None
            if isinstance(data, dict):
                entry["completion_pct"] = data.get("completion_pct")
                entry["inventions"] = _count(data.get("inventions"))
                entry["missing_anchors"] = _count(data.get("missing_anchors"))
                entry["open_questions"] = _count(data.get("open_questions"))
        check = pbcompletion.check_file(project, doc)
        entry["packet_pct"] = check["percentage"] if check else None
        entry["packet_errors"] = len(check["errors"]) if check else None
        out[doc] = entry
    return out


def review_summaries(project: Path) -> List[dict]:
    base = project / "wow" / "reviews"
    rows: List[dict] = []
    if not base.is_dir():
        return rows
    for path in sorted(base.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict) or not isinstance(data.get("rounds"), list):
            continue
        rounds = [r for r in data["rounds"] if isinstance(r, dict)]
        rows.append({"ref": data.get("ref", path.stem), "anchor_set": data.get("anchor_set"),
                     "rounds": len(rounds), "final": data.get("final"),
                     "first_pass": bool(rounds) and rounds[0].get("verdict") == "APPROVED",
                     "blockers": sum(_count(r.get("blockers")) for r in rounds)})
    return rows


def pricing(cfg: dict) -> dict:
    table = cfg.get("pricing") or {}
    return {"as_of": table.get("as_of"), "per_mtok": dict(table.get("per_mtok") or {})}
