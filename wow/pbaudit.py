"""Audit a local copy of a Product Brain chat against its packet and the context pack (spec 9.3).

Corrections are Spanish on purpose: they are pasted back into the Product Brain chat.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

import pack
import review
import reviewers
from sources import pbchat

KNOWN_INVENTIONS = [
    ("marketplace", r"\bmarketplace\b"),
    ("comprador/vendedor", r"\bcomprador(?:es)?\b|\bvendedor(?:es)?\b"),
    ("API Gateway", r"\bapi[ -]?gateway\b"),
    ("Okta", r"\bokta\b"),
    ("OAuth", r"\boauth\b"),
    ("SLA", r"\bSLAs?\b"),
    ("circuit breaker", r"\bcircuit[ -]?breakers?\b"),
    ("Kong", r"\bkong\b"),
]
_NEGATION_RE = re.compile(r"\b(no hay|no es|no existe|no usa|no aplica|inexistente|sin)\b", re.IGNORECASE)
_CLAUSE_RE = re.compile(r"[;.!?]")
_CHECK_RE = re.compile(r"[✅✔]")
_CITATION_RE = re.compile(r"\(|fuente|source|secci[oó]n|§", re.IGNORECASE)
_COMPLETION_RE = re.compile(r"(?:llega al|documento al|completitud[^0-9\n]{0,20})\s*(\d{1,3})\s*%", re.IGNORECASE)
_ITEM_RE = re.compile(r"^\s*(?:\d+[.)]|[-*])\s+(.+?)\s*$")


AUTHORITATIVE_RE = re.compile(r"\*\*Completitud del documento:\*\*\s*(\d{1,3})\s*%")


def _supporting_text(text: str) -> str:
    """Text that can support a term: no headings and no negated clauses ("No aplica: no hay API Gateway")."""
    kept = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        kept += [c for c in _CLAUSE_RE.split(line.replace("|", ".")) if not _NEGATION_RE.search(c)]
    return "\n".join(kept)


def open_questions(text: str) -> List[str]:
    lines = text.splitlines()
    heads = [i for i, line in enumerate(lines) if "preguntas abiertas" in line.lower() and len(line) < 80]
    if not heads:
        return []
    items: List[str] = []
    for line in lines[heads[-1] + 1:]:
        if not line.strip():
            continue
        item = _ITEM_RE.match(line)
        if item:
            items.append(item.group(1))
        elif line[:1] in (" ", "\t") and items:
            items[-1] = f"{items[-1]} {line.strip()}"
        else:
            break
    return items


def _affirmed(regex: re.Pattern, line: str) -> bool:
    """True if the term appears in a clause without a negation before it ("no hay X; agregar Y" flags Y)."""
    for clause in _CLAUSE_RE.split(line):
        for match in regex.finditer(clause):
            if not _NEGATION_RE.search(clause[:match.start()]):
                return True
    return False


def _preamble_lines() -> set:
    return {line.strip() for line in pack.PREAMBLE.splitlines() if line.strip()}


def _allowed_text(project: Path, doc: str) -> str:
    parts = []
    packet = project / "wow" / "pb" / f"{doc}.md"
    if packet.is_file():
        parts.append(packet.read_text(encoding="utf-8"))
    for path in sorted((project / "wow" / "context-pack").glob("*.md")):
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _corrections(missing: List[str], inventions: List[dict], unsupported: List[dict]) -> str:
    if not (missing or inventions or unsupported):
        return ""
    lines = ["Correcciones (pegalas en el chat de Product Brain):"]
    lines += [f"- Conservá el criterio {anchor} tal como venía en el paquete (regla 6)." for anchor in missing]
    lines += [f"- Quitá «{i['term']}» (línea {i['line']}): no figura en el material (regla 4). "
              f"Si es una decisión pendiente, movela a Preguntas abiertas." for i in inventions]
    lines += [f"- El ítem «{c['text']}» figura como cumplido sin citar dónde se cumple (regla 7): "
              f"citá la sección o marcalo como pendiente." for c in unsupported]
    return "\n".join(lines)


_SEPARATOR_RE = re.compile(r"^\|?\s*:?-{3,}")


def _doc_lines(text: str) -> List[tuple]:
    """(section, normalized line) for each content line: table padding, blanks, separators and comments out."""
    lines, section = [], ""
    for raw in re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).splitlines():
        line = raw.strip()
        if not line or _SEPARATOR_RE.match(line):
            continue
        if line.startswith("|"):
            line = "| " + " | ".join(c.strip() for c in line.strip("|").split("|")) + " |"
        else:
            line = re.sub(r"\s+", " ", line)
        if line.startswith("#"):
            section = line.lstrip("#").strip()
        lines.append((section, line))
    return lines


def doc_changes(project: Path, doc: str) -> Optional[List[dict]]:
    """What Product Brain added or removed against the packet, from the document copied out of its panel
    (wow/pb/chats/<doc>.final.md). None when there is no copy: the chat alone does not carry the document."""
    final = project / "wow" / "pb" / "chats" / f"{doc}.final.md"
    packet = project / "wow" / "pb" / f"{doc}.md"
    if not final.is_file() or not packet.is_file():
        return None
    old, new = _doc_lines(packet.read_text(encoding="utf-8")), _doc_lines(final.read_text(encoding="utf-8"))
    changes: List[dict] = []
    matcher = difflib.SequenceMatcher(a=[l for _, l in old], b=[l for _, l in new], autojunk=False)
    for tag, a1, a2, b1, b2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        changes += [{"op": "-", "section": s, "text": l} for s, l in old[a1:a2]]
        changes += [{"op": "+", "section": s, "text": l} for s, l in new[b1:b2]]
    return changes


_SECTION_HEAD_RE = re.compile(r"^#{1,3}\s")


def _md_sections(text: str) -> dict:
    """Heading (levels 1-3) -> its block, deeper headings included (#### A. stays inside its API section)."""
    sections, current, body = {}, None, []
    for line in re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).splitlines():
        if _SECTION_HEAD_RE.match(line):
            if current is not None:
                sections[current] = "\n".join(body).strip("\n")
            current, body = line.strip(), [line]
        elif current is not None:
            body.append(line)
    if current is not None:
        sections[current] = "\n".join(body).strip("\n")
    return sections


def editor_fixes(project: Path, doc: str) -> List[dict]:
    """Sections Product Brain left with template placeholders although the packet filled them. Its merge appends a
    list it cannot match by name after the template rows (field-groups.ts mergeGroupArrays), so in the IRIS pilot the
    API block landed as an uncounted "D" while A-C stayed empty. The deterministic fix is the one done by hand in the
    PRISM pilot: paste the packet's section in Product Brain's document editor."""
    final = project / "wow" / "pb" / "chats" / f"{doc}.final.md"
    packet = project / "wow" / "pb" / f"{doc}.md"
    if not final.is_file() or not packet.is_file():
        return []
    ours = _md_sections(packet.read_text(encoding="utf-8"))
    fixes = []
    for heading, block in _md_sections(final.read_text(encoding="utf-8")).items():
        mine = ours.get(heading)
        if mine and "{{" in block and "{{" not in mine:
            fixes.append({"section": heading, "replace_with": mine,
                          "reason": "Product Brain left template placeholders here (its merge appended the content "
                                    "after the template rows, where it does not count)"})
    return fixes


def audit(project: Path, doc: str, extra_inventions: Optional[List[dict]] = None) -> dict:
    chat_path = project / "wow" / "pb" / "chats" / f"{doc}.md"
    if not chat_path.is_file():
        raise FileNotFoundError(chat_path)
    text = chat_path.read_text(encoding="utf-8")
    preamble = _preamble_lines()
    lines = [(n, line) for n, line in enumerate(text.splitlines(), 1) if line.strip() not in preamble]
    parsed = pbchat.parse_chat("\n".join(line for _, line in lines))

    packet = project / "wow" / "pb" / f"{doc}.md"
    expected = sorted(set(pbchat.ANCHOR_RE.findall(packet.read_text(encoding="utf-8")))) if packet.is_file() else []
    missing = sorted(set(expected) - set(parsed["anchors"]))

    allowed = _supporting_text(_allowed_text(project, doc))
    inventions: List[dict] = []
    for term, pattern in KNOWN_INVENTIONS:
        regex = re.compile(pattern, re.IGNORECASE)
        if regex.search(allowed):
            continue
        for number, line in lines:
            # A heading is the template's fixed section name ("### API Gateway"), not an affirmation.
            if not line.lstrip().startswith("#") and _affirmed(regex, line):
                inventions.append({"term": term, "line": number, "text": line.strip()[:160], "source": "known-list"})
                break
    inventions += list(extra_inventions or [])

    unsupported = [{"line": n, "text": line.strip()[:160]} for n, line in lines
                   if _CHECK_RE.search(line) and not _CITATION_RE.search(line)]
    authoritative = [int(m) for m in AUTHORITATIVE_RE.findall(text) if int(m) <= 100]
    percents = authoritative or [int(m) for m in _COMPLETION_RE.findall(text) if int(m) <= 100]
    fixes = editor_fixes(project, doc)
    inputs = _inputs_fingerprint(project, doc)
    previous = _previous_audit(project, doc)
    same = previous is not None and previous.get("inputs", inputs) == inputs
    if same and not extra_inventions:
        # An audit without --deep does not erase what the deep reviewer found in this same material.
        inventions += [i for i in previous.get("inventions", []) if i.get("source") == "reviewer" and i not in inventions]
    verdict = "approved" if not (missing or inventions or unsupported or fixes) else "changes_required"
    result = {"schema_version": 1, "doc": doc, "verdict": verdict, "closed": parsed["closed"],
              "completion_pct": percents[-1] if percents else None, "open_questions": open_questions(text),
              "expected_anchors": expected, "missing_anchors": missing, "unsupported_checks": unsupported,
              "inventions": inventions, "corrections_to_paste": _corrections(missing, inventions, unsupported),
              "pb_changes": doc_changes(project, doc), "editor_fixes": fixes, "inputs": inputs}
    decision = (previous or {}).get("decision")
    if decision and verdict == "changes_required":
        if same:
            result["decision"] = decision
            result["verdict"] = f"{decision['verdict']}_by_human"
        else:
            result["decision_dropped"] = {**decision, "why": "the chat, the panel copy or the packet changed "
                                                             "after the decision; decide again on the new material"}
    return result


def _inputs_fingerprint(project: Path, doc: str) -> str:
    """What the audit read: the chat copy, the panel copy and the packet. A human decision and the deep reviewer's
    findings hold only while these stay the same."""
    digest = hashlib.sha256()
    for path in (project / "wow" / "pb" / "chats" / f"{doc}.md", project / "wow" / "pb" / "chats" / f"{doc}.final.md",
                 project / "wow" / "pb" / f"{doc}.md"):
        digest.update(path.name.encode() + b"\0" + (path.read_bytes() if path.is_file() else b"") + b"\0")
    return digest.hexdigest()


def _previous_audit(project: Path, doc: str) -> Optional[dict]:
    path = project / "wow" / "pb" / "chats" / f"{doc}.audit.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    except (OSError, json.JSONDecodeError):
        return None


_INVENTION_RE = re.compile(r"^\s*INVENTION\s+(\d+)\s+[—–-]+\s*(.+?)\s+[—–-]+\s*(.+?)\s*$")

_DEEP_PROMPT = """You are an independent auditor. CONTEXT is the only source of truth.
List every statement in CHAT that asserts a fact, component, provider, number, owner or deadline
that does not appear in CONTEXT. Ignore statements that only repeat CONTEXT or ask questions.

Output format, exactly, with no other text:
VERDICT: APPROVED | CHANGES_REQUIRED
INVENTION <chat-line-number> — <short quote> — <why it is not supported>

--- CONTEXT ---
{context}

--- CHAT (numbered) ---
{chat}
"""


def build_deep_prompt(project: Path, doc: str) -> str:
    text = (project / "wow" / "pb" / "chats" / f"{doc}.md").read_text(encoding="utf-8")
    preamble = _preamble_lines()
    numbered = "\n".join(f"{n}: {line}" for n, line in enumerate(text.splitlines(), 1)
                         if line.strip() not in preamble)
    return _DEEP_PROMPT.format(context=_allowed_text(project, doc) or "(empty)", chat=numbered)


def parse_inventions(text: str) -> List[dict]:
    if review.parse_verdict(text)["verdict"] is None:
        raise review.ReviewOutputError("reviewer output has no 'VERDICT:' line")
    found = []
    for line in text.splitlines():
        match = _INVENTION_RE.match(line)
        if match:
            found.append({"term": match.group(2)[:80], "line": int(match.group(1)),
                          "text": match.group(3), "source": "reviewer"})
    return found


def deep_inventions(project: Path, doc: str, cfg: dict, runner=subprocess.run, which=shutil.which) -> List[dict]:
    _, spec = reviewers.pick_reviewer(cfg, project, runner, which)
    return parse_inventions(reviewers.run_backend(spec, build_deep_prompt(project, doc), project, runner, which))


def decide(project: Path, doc: str, verdict: str, reason: str, author: str, now: str) -> dict:
    """Record a human verdict on an audit whose document the owner decides not to correct in Product Brain (its editor
    could; the owner accepts the divergence). Only over an existing changes_required audit, with a reason; the findings stay
    on record and the verdict says it came from a human, never from the audit."""
    if verdict not in ("approved", "rejected"):
        raise ValueError(f"{doc}: the human verdict is approved or rejected, not {verdict!r}")
    if not reason or not reason.strip():
        raise ValueError(f"{doc}: a human decision needs a reason")
    path = project / "wow" / "pb" / "chats" / f"{doc}.audit.json"
    if not path.is_file():
        raise ValueError(f"{doc}: run wow pbchat audit {doc} first; a human decision only answers an existing audit")
    result = json.loads(path.read_text(encoding="utf-8"))
    if result.get("verdict") != "changes_required":
        raise ValueError(f"{doc}: a human decision only answers a changes_required audit "
                         f"(the audit is {result.get('verdict')!r})")
    result["decision"] = {"by": "human", "author": author, "verdict": verdict, "reason": reason.strip(),
                          "at": now, "overrides": result["verdict"]}
    result["verdict"] = f"{verdict}_by_human"
    write_audit(project, result)
    return result


def write_audit(project: Path, result: dict) -> Path:
    path = project / "wow" / "pb" / "chats" / f"{result['doc']}.audit.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
