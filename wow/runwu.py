"""Measured Cursor runs: wrap cursor-agent and keep only usage numbers (spec 9.4)."""
from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, List, Optional, Tuple

KEEP_RESULT_KEYS = ("type", "subtype", "is_error", "duration_ms", "duration_api_ms", "usage")


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_command(wu: str, model: str, worktree: bool) -> List[str]:
    cmd = ["cursor-agent", "-p", f"/spec-kit.implement {wu} --max-iterations 5", "--model", model,
           "--trust", "--force", "--output-format", "json"]
    if worktree:
        cmd += ["--worktree", f"wu-{wu}"]
    return cmd


def run(project: Path, wu: str, model: str, epic: Optional[str] = None, worktree: bool = False,
        runner: Callable = subprocess.run, which: Callable = shutil.which,
        now: Callable[[], str] = _utc_now) -> Tuple[int, Path]:
    if which("cursor-agent") is None:
        raise FileNotFoundError("cursor-agent")
    env = dict(os.environ, TMPDIR=tempfile.mkdtemp(prefix="wow-run-"))
    started = now()
    proc = runner(build_command(wu, model, worktree), cwd=str(project), env=env, capture_output=True, text=True)
    ended = now()
    try:
        data = json.loads(proc.stdout)
        result = {k: data[k] for k in KEEP_RESULT_KEYS if k in data} if isinstance(data, dict) else None
    except (json.JSONDecodeError, TypeError):
        result = None
    record = {"schema_version": 1, "work_unit": wu, "ref": f"{epic}/{wu}" if epic else wu, "model": model,
              "started_at": started, "ended_at": ended, "exit_code": proc.returncode, "result": result}
    stamp = ended.replace("-", "").replace(":", "")
    path = project / "harness" / "runs" / f"{wu}-{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return proc.returncode, path
