"""Independent reviewer CLIs: command templates, dry run and selection (spec D7)."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Optional, Tuple

DEFAULT_COMMANDS = {
    "codex": {"argv": ["codex", "exec", "-C", "{cwd}", "-s", "read-only", "--ephemeral", "-o", "{out}", "-"],
              "stdin": True, "output": "file"},
    "copilot": {"argv": ["copilot", "-s", "-p", "{prompt}"], "stdin": False, "output": "stdout"},
}
EXCLUDED = {"claude", "cursor"}
_DRY_RUN_PROMPT = "Reply with exactly OK and nothing else."


class NoReviewer(Exception):
    """No configured reviewer passed the dry run."""


class ReviewerFailed(Exception):
    """The reviewer process exited with a non-zero code."""


def command_spec(cfg: dict, name: str) -> Optional[dict]:
    return (cfg.get("reviewer_commands") or {}).get(name) or DEFAULT_COMMANDS.get(name)


def run_backend(spec: dict, prompt: str, cwd: Path, runner: Callable = subprocess.run,
                which: Callable = shutil.which, timeout: int = 1800) -> str:
    if which(spec["argv"][0]) is None:
        raise FileNotFoundError(spec["argv"][0])
    fd, out = tempfile.mkstemp(prefix="wow-review-", suffix=".md")
    os.close(fd)
    try:
        argv = [a.replace("{cwd}", str(cwd)).replace("{out}", out).replace("{prompt}", prompt) for a in spec["argv"]]
        proc = runner(argv, input=prompt if spec.get("stdin") else None, capture_output=True, text=True,
                      timeout=timeout, cwd=str(cwd))
        if proc.returncode != 0:
            raise ReviewerFailed(f"{spec['argv'][0]} exited with {proc.returncode}")
        if spec.get("output") == "file":
            return Path(out).read_text(encoding="utf-8")
        return proc.stdout
    finally:
        Path(out).unlink(missing_ok=True)


def dry_run_ok(spec: dict, cwd: Path, runner: Callable = subprocess.run, which: Callable = shutil.which) -> bool:
    try:
        return run_backend(spec, _DRY_RUN_PROMPT, cwd, runner, which, timeout=300).strip() == "OK"
    except Exception:  # noqa: BLE001 — any failure means "not available"
        return False


def pick_reviewer(cfg: dict, cwd: Path, runner: Callable = subprocess.run,
                  which: Callable = shutil.which) -> Tuple[str, dict]:
    tried = []
    for name in cfg.get("reviewers", []):
        if name in EXCLUDED:
            continue
        spec = command_spec(cfg, name)
        if spec is None:
            continue
        tried.append(name)
        if dry_run_ok(spec, cwd, runner, which):
            return name, spec
    raise NoReviewer(f"no reviewer available (tried: {', '.join(tried) or 'none'})")
