"""A flow's checklist: items derived from evidence, plus manual ones that count only with written evidence.

An item is done, todo, not applicable (na) or unverified (its source could not be read: it never counts as done).
The derived section is rewritten on every run; the manual section is kept verbatim from the previous file.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

import tmpl

MARK = {"done": "[x]", "todo": "[ ]", "na": "[-]", "unverified": "[?]"}
PREFIX = {"done": "", "todo": "", "na": "no aplica: ", "unverified": "sin verificar: "}
_MANUAL = re.compile(r"^- \[([ xX])\]\s+(.*?)(?:\s+—\s+evidencia:\s*(.*))?$")


@dataclass
class Item:
    id: str
    label: str
    state: str
    evidence: str = ""


def percent(items: List[Item]) -> int:
    counted = [i for i in items if i.state != "na"]
    return round(100 * sum(i.state == "done" for i in counted) / len(counted)) if counted else 0


def manual_section(text: str) -> str:
    """The item lines under '## Manual', verbatim."""
    _, _, tail = (text or "").partition("\n## Manual\n")
    return "\n".join(line for line in tail.splitlines() if line.startswith("- [")).strip()


def manual_items(text: str) -> List[Item]:
    items = []
    for n, line in enumerate(manual_section(text).splitlines()):
        match = _MANUAL.match(line)
        if match:
            ticked, label, evidence = match.group(1).lower() == "x", match.group(2), (match.group(3) or "").strip()
            items.append(Item(f"manual-{n}", label, "done" if ticked and evidence else "todo", evidence))
    return items


def unproven(text: str) -> List[str]:
    """Manual items ticked without evidence: shown to the user, never counted."""
    return [m.group(2) for m in map(_MANUAL.match, manual_section(text).splitlines())
            if m and m.group(1).lower() == "x" and not (m.group(3) or "").strip()]


def _line(item: Item) -> str:
    note = PREFIX[item.state] + item.evidence if item.evidence or PREFIX[item.state] else ""
    return f"- {MARK[item.state]} {item.label}" + (f" — {note}" if note else "")


def render(title: str, derived: List[Item], manual: str) -> str:
    """The checklist file; the percent counts the derived items and the manual ones read back from `manual`."""
    everything = derived + manual_items("\n## Manual\n" + manual)
    counted = [i for i in everything if i.state != "na"]
    return tmpl.render(tmpl.load("checklist.md"), {
        "title": title, "percent": str(percent(everything)), "done": str(sum(i.state == "done" for i in counted)),
        "total": str(len(counted)), "derived": "\n".join(_line(i) for i in derived) or "- [-] Nada que verificar",
        "manual": manual}).rstrip("\n") + "\n"
