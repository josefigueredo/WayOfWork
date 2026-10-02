"""Repo source: context pack and Product Brain packets under wow/."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

HASH_RE = re.compile(r"manifest-hash=([0-9a-f]{16})")
_UNCHECKED_RE = re.compile(r"^\s*-\s*\[ \]")


def context_pack_status(project: Path) -> dict:
    base = project / "wow" / "context-pack"
    pending = base / "pending-owner.md"
    open_items = 0
    if pending.is_file():
        open_items = sum(1 for line in pending.read_text(encoding="utf-8").splitlines() if _UNCHECKED_RE.match(line))
    return {"facts": (base / "facts.md").is_file(), "pending_file": pending.is_file(), "pending_open": open_items}


def _packet(path: Path, mhash: str) -> str:
    if not path.is_file():
        return "missing"
    match = HASH_RE.search(path.read_text(encoding="utf-8"))
    return "ok" if match and match.group(1) == mhash else "stale"


def packet_status(project: Path, mhash: str, epic_ids: List[str]) -> dict:
    base = project / "wow" / "pb"
    epics: Dict[str, str] = {eid: _packet(base / f"epic-{eid}.md", mhash) for eid in epic_ids}
    return {"prd": _packet(base / "prd.md", mhash), "rfc": _packet(base / "rfc.md", mhash), "epics": epics}


_SUBMODULE_RE = re.compile(r"^\s*path\s*=\s*(.+?)\s*$")


def submodule_paths(project: Path) -> List[str]:
    path = project / ".gitmodules"
    if not path.is_file():
        return []
    return [m.group(1) for m in map(_SUBMODULE_RE.match, path.read_text(encoding="utf-8").splitlines()) if m]
