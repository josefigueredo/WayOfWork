"""Product Brain base templates vendored from josefigueredo/acme-agent@9b19a89 (reference/product-brain/README.md).

Field extraction and grouping mirror detector.ts (PLACEHOLDER_PATTERN) and field-groups.ts (detectFieldGroups).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

TEMPLATE_ID = "pb-9b19a89"
KINDS = ("prd", "rfc")
PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}|\{\s*([a-zA-Z0-9_.-]+)\s*\}")
_NUMERIC_RE = re.compile(r"^(.+?)_(\d+)(?:_(.+))?$")
_ALPHA_RE = re.compile(r"^(.+?)_([a-z])(?:_(.+))?$")
_DIR = Path(__file__).resolve().parent / "templates"


def load(kind: str) -> str:
    if kind not in KINDS:
        raise ValueError(f"unknown template kind {kind!r}; expected one of {KINDS}")
    return (_DIR / f"pb-{kind}.md").read_text(encoding="utf-8")


def fields(text: str) -> List[str]:
    found: List[str] = []
    for match in PLACEHOLDER_RE.finditer(text):
        name = (match.group(1) or match.group(2) or "").strip()
        if name and name not in found:
            found.append(name)
    return found


def groups(names: List[str]) -> Dict[str, dict]:
    numeric: Dict[Tuple[str, str], list] = {}
    alpha: Dict[Tuple[str, str], list] = {}
    for name in names:
        match = _NUMERIC_RE.match(name)
        if match:
            numeric.setdefault((match.group(1), match.group(3) or ""), []).append(
                (match.group(1), int(match.group(2)), match.group(3), name))
            continue
        match = _ALPHA_RE.match(name)
        if match:
            alpha.setdefault((match.group(1), match.group(3) or ""), []).append(
                (match.group(1), match.group(2), match.group(3), name))
    result: Dict[str, dict] = {}
    for index_type, buckets in (("numeric", numeric), ("alpha", alpha)):
        for entries in buckets.values():
            if len({entry[1] for entry in entries}) < 2:
                continue
            prefix = entries[0][0]
            if index_type == "alpha" and result.get(prefix, {}).get("index_type") == "numeric":
                continue
            group = result.setdefault(prefix, {"index_type": index_type, "fields": {}})
            for _, index, sub, name in entries:
                group["fields"][name] = (index, sub)
    return result


def units(kind: str) -> Tuple[List[str], Dict[str, dict]]:
    names = fields(load(kind))
    grouped = groups(names)
    members = {name for group in grouped.values() for name in group["fields"]}
    return [name for name in names if name not in members], grouped


def extract_upstream(source_text: str, const_name: str) -> str:
    marker = f"export const {const_name} = `"
    start = source_text.index(marker) + len(marker)
    return source_text[start:source_text.index("`;", start)].replace("\\`", "`")
