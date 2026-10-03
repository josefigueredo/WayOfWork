"""Anchored review protocol: verdict parsing and round rules (spec 9.1, D6)."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Iterable

MAX_ROUNDS = 3
_SAFE_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SEP = r"\s+[—–-]+\s*"
_VERDICT_RE = re.compile(r"^\s*VERDICT:\s*(APPROVED|CHANGES_REQUIRED)\s*$", re.MULTILINE)
_BLOCKER_RE = re.compile(r"^\s*BLOCKER\s+(\S+)\s+(\S+)" + _SEP + r"(.+?)\s*$")
_WARNING_RE = re.compile(r"^\s*WARNING\s+(\S+)" + _SEP + r"(.+?)\s*$")
_NIT_RE = re.compile(r"^\s*NIT" + _SEP + r"(.+?)\s*$")


class ReviewOutputError(Exception):
    """The reviewer output has no VERDICT line, so no round can be recorded."""


def parse_verdict(text: str) -> dict:
    verdict = _VERDICT_RE.search(text)
    parsed = {"verdict": verdict.group(1) if verdict else None, "blockers": [], "warnings": [], "nits": []}
    for line in text.splitlines():
        blocker = _BLOCKER_RE.match(line)
        if blocker:
            parsed["blockers"].append({"anchor": blocker.group(1), "path_line": blocker.group(2),
                                       "text": blocker.group(3)})
            continue
        warning = _WARNING_RE.match(line)
        if warning:
            parsed["warnings"].append({"path_line": warning.group(1), "text": warning.group(2)})
            continue
        nit = _NIT_RE.match(line)
        if nit:
            parsed["nits"].append(nit.group(1))
    return parsed


def new_summary(ref: str, anchor_set: str) -> dict:
    return {"schema_version": 1, "ref": ref, "anchor_set": anchor_set, "rounds": [], "final": None}


def safe_ref(ref: str) -> bool:
    """A ref becomes a file name: allow only [A-Za-z0-9._-], no leading dot, no '..'."""
    return bool(_SAFE_REF_RE.match(ref)) and ".." not in ref


def _path(project: Path, ref: str) -> Path:
    if not safe_ref(ref):
        raise ValueError(f"unsafe ref {ref!r}: use letters, digits, '.', '_' or '-'")
    return project / "wow" / "reviews" / f"{ref}.json"


def load_summary(project: Path, ref: str, anchor_set: str) -> dict:
    path = _path(project, ref)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "rounds" in data:
                return data
        except json.JSONDecodeError:
            pass
    return new_summary(ref, anchor_set)


def save_summary(project: Path, summary: dict) -> Path:
    path = _path(project, summary["ref"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def next_action(summary: dict, diff_hash: str) -> str:
    if summary["final"] in ("approved", "approved_by_human"):
        return "done"
    if summary["final"] == "hitl":
        return "hitl"
    if summary["final"] == "rejected_by_human":
        return "rejected"
    rounds = summary["rounds"]
    if rounds and rounds[-1]["blockers"] and rounds[-1]["diff_hash"] == diff_hash:
        return "wait_for_changes"
    return "run"


def decide(summary: dict, verdict: str, reason: str, author: str, now: str) -> dict:
    """Record a human verdict on a review the reviewer escalated to HITL. It never stands in for the reviewer:
    it is only possible after HITL, it needs a reason, and it is kept apart from a reviewer approval."""
    if summary["final"] != "hitl":
        raise ValueError(f"{summary['ref']}: a human decision is recorded only after HITL (final is {summary['final']!r})")
    if verdict not in ("approved", "rejected"):
        raise ValueError(f"verdict must be approved or rejected, not {verdict!r}")
    if not reason.strip():
        raise ValueError("a human decision needs a reason")
    result = copy.deepcopy(summary)
    result["decision"] = {"by": "human", "author": author, "verdict": verdict, "reason": reason.strip(), "at": now}
    result["final"] = f"{verdict}_by_human"
    return result


def record_round(summary: dict, parsed: dict, anchors: Iterable[str], diff_hash: str) -> dict:
    if parsed["verdict"] is None:
        raise ReviewOutputError("reviewer output has no 'VERDICT:' line")
    known = set(anchors)
    valid = [b for b in parsed["blockers"] if b["anchor"] in known]
    warnings = list(parsed["warnings"])
    for blocker in parsed["blockers"]:
        if blocker["anchor"] not in known:
            warnings.append({"path_line": blocker["path_line"],
                             "text": f"[downgraded: unknown anchor {blocker['anchor']}] {blocker['text']}"})
    result = copy.deepcopy(summary)
    number = len(result["rounds"]) + 1
    result["rounds"].append({"n": number, "verdict": "CHANGES_REQUIRED" if valid else "APPROVED",
                             "blockers": valid, "warnings": warnings, "nits": list(parsed["nits"]),
                             "diff_hash": diff_hash})
    if not valid:
        result["final"] = "approved"
    elif number >= MAX_ROUNDS:
        result["final"] = "hitl"
    return result
