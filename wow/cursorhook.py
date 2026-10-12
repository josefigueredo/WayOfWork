"""Cursor `stop` hook: keep each agent turn's model and tokens in the WoW repo it worked on.

Cursor runs every hook registered for an event, so this one runs beside Spec-Kit's telemetry hook and changes
nothing it sends. Spec-Kit's own local log leaves out the workspace (a client decision) and lives in /tmp; this
one writes per repo, only where a `wow/` directory exists, and never stores the user's email or transcript path.
"""
from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path
from typing import List

KEPT = ("conversation_id", "generation_id", "model", "model_id", "input_tokens", "output_tokens",
        "cache_read_tokens", "cache_write_tokens", "status", "loop_count", "cursor_version")


def _wow_root(path: Path):
    """The nearest directory holding a WoW plan; else the nearest one with a wow/ directory. A child repo of a
    workspace can carry wow/sk/ (the Spec-Kit drafts Cursor reads) while the plan, and wow, live above it."""
    candidates = (path, *path.parents)
    for candidate in candidates:
        if (candidate / "wow" / "plan" / "manifest.json").is_file():
            return candidate
    for candidate in candidates:
        if (candidate / "wow").is_dir():
            return candidate
    return None


def record_turn(payload: dict, now: str) -> List[Path]:
    if not isinstance(payload, dict) or payload.get("hook_event_name") != "stop":
        return []
    turn = {"ts": now, **{key: payload.get(key) for key in KEPT}}
    written: List[Path] = []
    for raw in payload.get("workspace_roots") or []:
        root = _wow_root(Path(str(raw)))
        if root is None:
            continue
        path = root / "harness" / "cursor-turns" / f"{now[:10]}.jsonl"
        if path in written:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(turn, ensure_ascii=False) + "\n")
        written.append(path)
    return written


def install(hooks_file: Path, command: str) -> "list[tuple[str, bool]]":
    """Add WoW's hooks to Cursor's hooks.json once, keeping everything else: `stop` records each turn's tokens and
    `beforeShellExecution` runs the shell guard. Returns each hook's event with True if this call added it."""
    data = {"version": 1, "hooks": {}}
    if hooks_file.is_file():
        data = json.loads(hooks_file.read_text(encoding="utf-8") or "{}")
    data.setdefault("version", 1)
    hooks = data.setdefault("hooks", {})
    results = []
    for event, sub, cmd in (("stop", "cursor-stop", command),
                            ("beforeShellExecution", "cursor-shell", command.replace("cursor-stop", "cursor-shell"))):
        entries = hooks.setdefault(event, [])
        added = not any(f"hook {sub}" in (entry.get("command") or "") for entry in entries)
        if added:
            entries.append({"command": cmd})
        results.append((event, added))
    if any(added for _, added in results):
        hooks_file.parent.mkdir(parents=True, exist_ok=True)
        hooks_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return results


def default_command() -> str:
    wow_entry = Path(__file__).resolve().parent / "wow"
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(wow_entry))} hook cursor-stop"
