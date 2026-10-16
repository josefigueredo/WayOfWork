"""wow sk run|send|quit: Spec-Kit commands sent to Cursor through the run-in-cursor skill (ric).

ric drives an interactive cursor-agent in tmux, the one way measured to fire every Cursor hook, so Spec-Kit's
telemetry records the run as it would a command typed in Cursor. wow adds Spec-Kit's rule: only /spec-kit.*
commands, and never /spec-kit.sync-status, which writes to Jira and stays with the user in Cursor.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import List, Optional

DENY = r"spec-kit\.sync-status"


def ric_path() -> Path:
    return Path(os.environ.get("WOW_RIC") or Path.home() / ".agents" / "skills" / "run-in-cursor" / "ric.py")


def refuse_reply(text: str) -> Optional[str]:
    """A reply in a running session: free text, but a reply starting with / runs as a slash command."""
    if re.search(DENY, text.strip(), re.IGNORECASE):
        return "/spec-kit.sync-status writes to Jira: run it in Cursor yourself"
    return None


def refuse(command: str) -> Optional[str]:
    text = command.strip()
    if refuse_reply(text):
        return refuse_reply(text)
    if not text.lower().startswith("/spec-kit."):
        return "wow sk run only sends /spec-kit.* commands; use run-in-cursor for anything else"
    return None


def argv(action: str, args: List[str], project: Path, model: Optional[str] = None) -> List[str]:
    """Options first and `--` before the positionals: a reply such as "-1" must not read as an option.
    `model` picks the Cursor model for a new session (`run` only); without it Cursor uses its default."""
    deny = ["--deny", DENY] if action in ("run", "send") else []
    chosen = ["--model", model] if model and action == "run" else []
    return [sys.executable, str(ric_path()), action, "--workspace", str(project), *deny, *chosen, "--", *args]
