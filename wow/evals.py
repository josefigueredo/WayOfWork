"""Reviewer evals: run a JSON dataset of self-contained cases through a real reviewer and say honestly what happened.

A case is the content a reviewer sees (anchors + body) and what it must find. Each case ends as pass, fail, or
could not run; a case that could not run is never counted as passed. Run by hand: it calls a real model.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, List

import packets
import review as review_mod

SETS = ("story", "epic", "readiness", "standards", "claims", "critique")
_EXPECT_KEYS = ("verdict", "blockers", "min_warnings")


class EvalError(Exception):
    """The dataset cannot be run as written."""


def load(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvalError(f"cannot read {path}: {exc}") from exc
    validate(data)
    return data


def validate(data: dict) -> None:
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not data.get("name"):
        raise EvalError("a dataset needs schema_version 1 and a name")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise EvalError("a dataset needs at least one case")
    seen = set()
    for case in cases:
        cid = case.get("id")
        if not cid or cid in seen:
            raise EvalError(f"case ids must be present and unique (got {cid!r})")
        seen.add(cid)
        if case.get("set") not in SETS:
            raise EvalError(f"case {cid}: set must be one of {', '.join(SETS)}")
        if not isinstance(case.get("content"), str) or not case["content"].strip():
            raise EvalError(f"case {cid}: content is empty")
        if case["set"] != "critique" and not case.get("anchors"):
            raise EvalError(f"case {cid}: an anchored set needs anchors")
        expect = case.get("expect") or {}
        if not any(key in expect for key in _EXPECT_KEYS):
            raise EvalError(f"case {cid}: expect needs {', '.join(_EXPECT_KEYS)} (at least one)")


def prompt(case: dict) -> str:
    return packets.build_prompt({"anchor_set": case["set"], "ref": case["id"], "anchors": case.get("anchors") or {},
                                 "body": case["content"], "source": f"eval case {case['id']}"})


def judge(expect: dict, parsed: dict, critique: bool = False) -> List[str]:
    """What the reviewer missed; empty means the case passed. A critique reads any BLOCKER as a warning."""
    misses = []
    if "verdict" in expect and parsed["verdict"] != expect["verdict"]:
        misses.append(f"verdict {parsed['verdict']}, expected {expect['verdict']}")
    found = {b["anchor"] for b in parsed["blockers"]}
    misses += [f"no BLOCKER on {anchor}" for anchor in expect.get("blockers", []) if anchor not in found]
    warnings = len(parsed["warnings"]) + (len(parsed["blockers"]) if critique else 0)
    if "min_warnings" in expect and warnings < expect["min_warnings"]:
        misses.append(f"{warnings} warnings, expected at least {expect['min_warnings']}")
    return misses


def run(data: dict, ask: Callable[[str], str]) -> List[Dict]:
    """ask(prompt) -> the reviewer's raw text, or a reviewers.Reply with its usage and model; any exception it raises makes that case 'could not run'."""
    results = []
    for case in data["cases"]:
        try:
            reply = ask(prompt(case))
        except Exception as exc:  # noqa: BLE001 — the case is reported, never guessed
            results.append({"id": case["id"], "status": "could not run", "detail": str(exc)[:300]})
            continue
        text, used, model = (reply, None, None) if isinstance(reply, str) else (reply.text, reply.usage, reply.model)
        parsed = review_mod.parse_verdict(text)
        if case["set"] != "critique" and parsed["verdict"] is None:
            results.append({"id": case["id"], "status": "could not run", "detail": "no VERDICT line in the output",
                            "output": text})
            continue
        misses = judge(case["expect"], parsed, critique=case["set"] == "critique")
        results.append({"id": case["id"], "status": "fail" if misses else "pass", "detail": "; ".join(misses),
                        "output": text, "usage": used, "model": model})
    return results
