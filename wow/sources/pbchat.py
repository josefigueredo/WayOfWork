"""Local copies of Product Brain chats (spec D4)."""
from __future__ import annotations

import json
import re
from pathlib import Path

CLOSED_RE = re.compile(r"100\s*%|\b(?:dalo|damos|doy|lo doy)\s+por\s+cerrad[oa]|\bpor\s+cerrad[oa]", re.IGNORECASE)
ANCHOR_RE = re.compile(r"\b(AC[0-9]+|E[0-9]+\.C[0-9]+)\b")


def parse_chat(text: str) -> dict:
    return {"closed": bool(CLOSED_RE.search(text)), "anchors": sorted(set(ANCHOR_RE.findall(text)))}


def chat_status(project: Path, doc: str) -> dict:
    base = project / "wow" / "pb" / "chats"
    chat = base / f"{doc}.md"
    if not chat.is_file():
        return {"present": False, "closed": False, "audit": None}
    parsed = parse_chat(chat.read_text(encoding="utf-8"))
    audit_path = base / f"{doc}.audit.json"
    audit = None
    if audit_path.is_file():
        try:
            audit = json.loads(audit_path.read_text(encoding="utf-8")).get("verdict")
        except (json.JSONDecodeError, AttributeError):
            audit = "unknown"
    return {"present": True, "closed": parsed["closed"], "audit": audit}
