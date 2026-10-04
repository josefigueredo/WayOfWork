"""Repo source: context pack and Product Brain packets under wow/."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

import pbtemplate

HASH_RE = re.compile(r"manifest-hash=([0-9a-f]{16})")
TEMPLATE_RE = re.compile(r"template=(pb-[0-9a-f]{7})")
# `- [ ]` open (blocks the plan) · `- [~]` absorbed into the plan as a task with a default (does not block, still
# undecided) · `- [x]` decided or accepted as [SIN DEFINIR].
_PENDING_RE = re.compile(r"^\s*-\s*\[[ ~]\]\s*(.+?)\s*$")
_UNCHECKED_RE = re.compile(r"^\s*-\s*\[ \]")
_ABSORBED_RE = re.compile(r"^\s*-\s*\[~\]")
_CLAIM_RE = re.compile(r"^\s*-\s*C[0-9]+:", re.MULTILINE)


def context_pack_status(project: Path) -> dict:
    base = project / "wow" / "context-pack"
    pending = base / "pending-owner.md"
    open_items = absorbed = 0
    if pending.is_file():
        lines = pending.read_text(encoding="utf-8").splitlines()
        open_items = sum(1 for line in lines if _UNCHECKED_RE.match(line))
        absorbed = sum(1 for line in lines if _ABSORBED_RE.match(line))
    facts = base / "facts.md"
    has_claims = facts.is_file() and bool(_CLAIM_RE.search(facts.read_text(encoding="utf-8")))
    return {"facts": has_claims, "pending_file": pending.is_file(), "pending_open": open_items,
            "pending_absorbed": absorbed}


def _packet(path: Path, mhash: str) -> str:
    if not path.is_file():
        return "missing"
    text = path.read_text(encoding="utf-8")
    match = HASH_RE.search(text)
    template = TEMPLATE_RE.search(text)
    fresh = match and match.group(1) == mhash and template and template.group(1) == pbtemplate.TEMPLATE_ID
    return "ok" if fresh else "stale"


def pending_items(project: Path) -> List[str]:
    path = project / "wow" / "context-pack" / "pending-owner.md"
    if not path.is_file():
        return []
    return [m.group(1) for m in map(_PENDING_RE.match, path.read_text(encoding="utf-8").splitlines()) if m]


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


_REPO_SKIP = {".git", "node_modules", ".terraform", ".venv", "venv", "dist", "build", ".history", "__pycache__",
              "wow", ".wow", "specs", ".spec-kit"}


def child_repos(project: Path, max_depth: int = 3) -> List[str]:
    """Git repositories under the project (multi-repo workspaces), as relative paths.

    Walks up to max_depth levels, does not descend into a repository once found, skips tool and editor
    folders (.history, node_modules, .terraform…), and adds existing submodule paths. The root is excluded.
    """
    found = {p for p in submodule_paths(project) if (project / p).exists()}

    def walk(directory: Path, depth: int) -> None:
        if depth > max_depth:
            return
        for item in sorted(directory.iterdir()):
            if not item.is_dir() or item.is_symlink() or item.name in _REPO_SKIP:
                continue
            if (item / ".git").exists():
                found.add(item.relative_to(project).as_posix())
                continue
            walk(item, depth + 1)

    walk(project, 1)
    return sorted(found)
