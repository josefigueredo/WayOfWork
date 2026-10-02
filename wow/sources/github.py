"""GitHub pull requests through the gh CLI (read only). Errors never include gh's stderr."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, List, Optional, Set

from sources import SourceUnavailable

KEY_RE = re.compile(r"\b[A-Z][A-Z0-9]*-\d+\b")
_FAILING = {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE"}
_PENDING = {"PENDING", "QUEUED", "IN_PROGRESS", "EXPECTED", "WAITING", ""}


def checks_state(rollup: Optional[list]) -> str:
    if not rollup:
        return "none"
    states = {str(c.get("conclusion") or c.get("state") or c.get("status") or "").upper() for c in rollup}
    if states & _FAILING:
        return "failing"
    if states & _PENDING:
        return "pending"
    return "passing"


def pull_requests(repo_dir: Path, runner: Callable = subprocess.run, which: Callable = shutil.which) -> List[dict]:
    if which("gh") is None:
        raise SourceUnavailable("github: gh not installed")
    argv = ["gh", "pr", "list", "--state", "all", "--limit", "50",
            "--json", "number,title,state,url,headRefName,statusCheckRollup"]
    try:
        proc = runner(argv, cwd=str(repo_dir), capture_output=True, text=True, timeout=20)
        if proc.returncode != 0:
            raise ValueError
        data = json.loads(proc.stdout)
        if not isinstance(data, list):
            raise ValueError
    except (ValueError, OSError, subprocess.TimeoutExpired):
        raise SourceUnavailable(f"github: gh pr list failed in {repo_dir.name}")
    return [{"repo": repo_dir.name, "number": pr.get("number"), "title": pr.get("title", ""),
             "state": pr.get("state"), "url": pr.get("url"), "branch": pr.get("headRefName", ""),
             "checks": checks_state(pr.get("statusCheckRollup"))} for pr in data]


def link(prs: List[dict], keys: Set[str]) -> List[dict]:
    return [pr for pr in prs if keys & set(KEY_RE.findall(f"{pr.get('title', '')} {pr.get('branch', '')}"))]
