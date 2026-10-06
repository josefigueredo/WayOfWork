"""What closes an independent review, in one place: state, both flows, closing and the CLI read it from here.

A review is closed by the reviewer's approval or, after HITL, by a recorded human approval.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

CLOSED = ("approved", "approved_by_human")


def final(project: Path, ref: str) -> Optional[str]:
    path = project / "wow" / "reviews" / f"{ref}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("final")
    except (json.JSONDecodeError, AttributeError):
        return None
