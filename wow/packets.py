"""Anchors and review content for each anchor set (spec 9.1)."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Callable, Dict, Optional

import manifest

READINESS: Dict[str, str] = {
    "R1": "every task has at least one verifiable acceptance criterion",
    "R2": "depends_on forms a DAG over existing task ids",
    "R3": "the Brief has no blocking open question",
    "R4": "every epic has done_when criteria",
    "R5": "every task has estimate, priority and labels",
}
_AC_RE = re.compile(r"\b(AC[0-9]+):\s*(.+?)\s*$")
# /spec-kit.sync writes "1. **Given** …, **When** …, **Then** … (AC1)": the id trails, in parentheses.
_AC_TRAILING_RE = re.compile(r"^\s*(?:\d+[.)]|[-*])?\s*(.+?)\s*\((AC[0-9]+)\)\s*$")
_CLAIM_RE = re.compile(r"^\s*(?:[-*]\s*)?\**(C[0-9]+)\**\s*[:.)]\s*(.+?)\s*$")
_HEADER_RE = re.compile(r"^(#+)\s")


class PacketError(Exception):
    """The packet cannot be built (no anchors, no diff, git failure)."""


def diff_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def git_diff(repo: Path, base: str, runner: Callable = subprocess.run) -> str:
    proc = runner(["git", "-C", str(repo), "diff", base], capture_output=True, text=True)
    if proc.returncode != 0:
        raise PacketError(f"git diff {base} failed in {repo}: {proc.stderr.strip()[:200]}")
    if not proc.stdout.strip():
        raise PacketError(f"empty diff against {base} in {repo}")
    return proc.stdout


def ci_evidence(repo: Path, runner: Callable = subprocess.run) -> str:
    """The CI runs GitHub recorded for HEAD: criteria about CI or deploy are judged on this, not on the diff alone
    (two of the pilot's three HITL escalations were "the evidence lives in GitHub Actions")."""
    head = runner(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True)
    sha = head.stdout.strip() if head.returncode == 0 else ""
    if not sha:
        return "\n\n--- CI evidence unavailable: no HEAD commit ---\n"
    try:
        proc = runner(["gh", "run", "list", "--commit", sha, "--limit", "20",
                       "--json", "name,status,conclusion,url"], capture_output=True, text=True, cwd=str(repo))
    except (FileNotFoundError, OSError) as exc:
        return f"\n\n--- CI evidence unavailable: {exc} ---\n"
    if proc.returncode != 0:
        return f"\n\n--- CI evidence unavailable: {proc.stderr.strip()[:200]} ---\n"
    try:
        runs = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return "\n\n--- CI evidence unavailable: gh returned no JSON ---\n"
    lines = [f"{r.get('name')}: {r.get('status')}/{r.get('conclusion') or '-'} {r.get('url')}" for r in runs]
    return f"\n\n--- CI runs for HEAD {sha[:12]} ---\n" + ("\n".join(lines) or "(no runs for this commit)") + "\n"


def _story_anchors(project: Path, key: str) -> Dict[str, str]:
    anchors: Dict[str, str] = {}
    for spec in sorted((project / "specs").glob("*/spec.md")):
        level = None
        for line in spec.read_text(encoding="utf-8").splitlines():
            header = _HEADER_RE.match(line)
            if header:
                if level is not None and len(header.group(1)) <= level:
                    level = None
                if key in line:
                    level = len(header.group(1))
                continue
            if level is not None:
                match = _AC_RE.search(line)
                if match:
                    anchors.setdefault(match.group(1), match.group(2))
                    continue
                trailing = _AC_TRAILING_RE.match(line)
                if trailing:
                    anchors.setdefault(trailing.group(2), trailing.group(1).replace("**", ""))
    return anchors


def story_packet(project: Path, key: str, repo: Path, base: str, runner: Callable = subprocess.run,
                 ci: Optional[Callable[[Path], str]] = None) -> dict:
    anchors = _story_anchors(project, key)
    if not anchors:
        raise PacketError(f"no acceptance criteria with AC ids found for {key} in specs/*/spec.md")
    body = git_diff(repo, base, runner) + (ci(repo) if ci else "")
    return {"anchor_set": "story", "ref": key, "anchors": anchors, "body": body, "cwd": repo}


def epic_packet(project: Path, epic_id: str, repo: Path, base: str, runner: Callable = subprocess.run,
                ci: Optional[Callable[[Path], str]] = None) -> dict:
    doc = manifest.load(project)
    epic = next((e for e in doc["epics"] if e["id"] == epic_id), None)
    if epic is None:
        raise PacketError(f"epic {epic_id} not found in the manifest")
    anchors = {item.split(":", 1)[0]: item.split(":", 1)[1].strip() for item in epic["done_when"]}
    if not anchors:
        raise PacketError(f"epic {epic_id} has no done_when criteria")
    body = git_diff(repo, base, runner) + (ci(repo) if ci else "")
    return {"anchor_set": "epic", "ref": epic_id, "anchors": anchors, "body": body, "cwd": repo}


_STANDARD_DOCS = ("CONTRIBUTING.md", "CODING_STANDARDS.md", "AGENTS.md", "CLAUDE.md")


def _golden_rules(*roots: Path) -> Dict[str, str]:
    """Spec-Kit golden rules installed in .cursor/rules (`spec-kit rules install`): name -> its MUST lines."""
    found: Dict[str, str] = {}
    for root in roots:
        for path in sorted((root / ".cursor" / "rules").glob("*golden_rules*.mdc")):
            musts = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
                     if line.strip().startswith("MUST")]
            if musts and path.stem not in found:
                found[path.stem] = " ".join(musts)
    return found


def standards_packet(project: Path, ref: str, repo: Path, base: str, runner: Callable = subprocess.run) -> dict:
    """Second review axis: the diff against the repo's standards, not against the story (the story axis does that).
    Anchors are the installed golden rules; without them, the conventions the repo documents."""
    rules = _golden_rules(repo, project)
    body = git_diff(repo, base, runner)
    if rules:
        anchors = {f"G{n}": f"{name}: {musts}" for n, (name, musts) in enumerate(sorted(rules.items()), 1)}
    else:
        docs = [name for name in _STANDARD_DOCS if (repo / name).is_file()]
        if not docs:
            raise PacketError(f"no standards to review against in {repo}: install Spec-Kit golden rules "
                              f"(spec-kit rules install) or document conventions in CONTRIBUTING.md")
        anchors = {"DOC": "the conventions documented in " + ", ".join(docs)}
        body += "".join(f"\n\n--- documented standards: {name} ---\n" + (repo / name).read_text(encoding="utf-8")
                        for name in docs)
    return {"anchor_set": "standards", "ref": ref, "anchors": anchors, "body": body, "cwd": repo}


def readiness_packet(project: Path) -> dict:
    doc = manifest.load(project)
    # plan.readiness is review state written by every round: excluding it keeps the diff hash stable.
    doc = dict(doc, plan={k: v for k, v in doc["plan"].items() if k != "readiness"})
    plan_md = project / "wow" / "plan" / "PLAN.md"
    body = (plan_md.read_text(encoding="utf-8") if plan_md.is_file() else "(no PLAN.md)") + \
        "\n\n--- manifest.json ---\n" + json.dumps(doc, indent=2, ensure_ascii=False)
    return {"anchor_set": "readiness", "ref": "plan", "anchors": dict(READINESS), "body": body, "cwd": project}


def claims_packet(doc: Path, repo: Path) -> dict:
    text = doc.read_text(encoding="utf-8")
    anchors: Dict[str, str] = {}
    for line in text.splitlines():
        match = _CLAIM_RE.match(line)
        if match:
            anchors.setdefault(match.group(1), match.group(2))
    if not anchors:
        raise PacketError(f"no claim ids (C1, C2, …) found in {doc}")
    return {"anchor_set": "claims", "ref": doc.stem, "anchors": anchors, "body": text, "cwd": repo}


_PROMPT = """You are an independent reviewer. Review the CONTENT below ONLY against these anchors:
{anchors}

{task}

Output format, exactly, with no other text:
VERDICT: APPROVED | CHANGES_REQUIRED
BLOCKER <anchor-id> <path:line> — <what fails and why it breaks the anchor>
WARNING <path:line> — <...>
NIT — <...>

A finding that breaks no listed anchor is a WARNING or a NIT, never a BLOCKER.
Do not modify any file.

--- CONTENT ({anchor_set} {ref}) ---
{body}
"""

_TASKS = {
    "story": "The content is the diff of one Work Unit. Check that it satisfies each acceptance criterion. "
             "When a CI section follows the diff, judge criteria about CI, gates or deploy on it.",
    "epic": "The content is the cumulative diff of an epic. Check each done_when criterion. "
            "When a CI section follows the diff, judge criteria about CI, gates or deploy on it.",
    "readiness": "The content is a plan (Brief + manifest). Check each readiness criterion.",
    "claims": "The content is a document of claims. Verify each claim against the code in the current "
              "directory; a false or unsupported claim is a BLOCKER on its id.",
    # Smell baseline adapted from mattpocock/skills code-review (MIT), after Fowler, Refactoring ch. 3.
    "standards": "The content is a diff. Check it against each standard anchor; a broken MUST is a BLOCKER on that "
                 "anchor. Do not check whether it implements the story: another review does that.\n"
                 "Also flag these code smells, always as WARNING (a judgement call, never a BLOCKER), and drop any "
                 "the anchors endorse: a golden rule overrides the baseline. Mysterious Name, Duplicated Code, "
                 "Feature Envy, Data Clumps, Primitive Obsession, Repeated Switches, Shotgun Surgery, Divergent "
                 "Change, Speculative Generality, Message Chains, Middle Man, Refused Bequest. "
                 "Skip what linters or formatters already enforce.",
}


def build_prompt(packet: dict) -> str:
    anchors = "\n".join(f"- {key}: {text}" for key, text in packet["anchors"].items())
    return _PROMPT.format(anchors=anchors, task=_TASKS[packet["anchor_set"]], anchor_set=packet["anchor_set"],
                          ref=packet["ref"], body=packet["body"])
