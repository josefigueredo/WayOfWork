"""WoW's own writes to Jira, one JSON line each in harness/jira-writes.jsonl.

Jira's changelog shows the account, not the tool: with one token shared by WoW, other tools and the person, a change
cannot be attributed. This log records every write WoW made (what, to which issue, from which command, when), so a
change can at least be ruled in or out as WoW's.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Callable, Optional


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def journal(project: Path, command: str, now: Optional[Callable[[], str]] = None) -> Callable[[dict], None]:
    """A writer for JiraClient(journal=...). It never raises: a log that cannot be written must not undo the write."""
    clock = now or _utc_now

    def write(entry: dict) -> None:
        try:
            path = project / "harness" / "jira-writes.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            record = {"ts": clock(), "tool": "wow", "command": command, **entry}
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass

    return write
