"""Independent reviewer CLIs: command templates, dry run and selection (spec D7)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Mapping, Optional, Set, Tuple

DEFAULT_COMMANDS = {
    # --json streams events on stdout (the turn's token usage among them); the answer still arrives through -o.
    "codex": {"argv": ["codex", "exec", "-C", "{cwd}", "-s", "read-only", "--ephemeral", "--skip-git-repo-check",
                        "--json", "-o", "{out}", "-"],
              "stdin": True, "output": "file"},
    "copilot": {"argv": ["copilot", "-s", "-p", "{prompt}"], "stdin": False, "output": "stdout"},
    # Every default runs read-only: claude in plan mode, cursor-agent in ask mode, gemini with plan approval.
    "gemini": {"argv": ["gemini", "-o", "text", "--approval-mode", "plan", "-p", "{prompt}"],
               "stdin": False, "output": "stdout"},
    "cursor-agent": {"argv": ["cursor-agent", "-p", "--trust", "--mode", "ask", "--output-format", "text", "{prompt}"],
                     "stdin": False, "output": "stdout"},
    "claude": {"argv": ["claude", "--print", "--permission-mode", "plan", "--output-format", "text"],
               "stdin": True, "output": "stdout"},
}
# What each host leaves in the environment of the commands it runs (measured: Claude Code 2.1.296, codex 0.159.3,
# cursor-agent 2026.10.01; gemini's is read from the 0.46.0 bundle). Children inherit them, so a nested session shows
# several markers; WOW_HOST names the author explicitly, comma-separated, for hosts without one.
HOST_MARKERS = {"CLAUDECODE": "claude", "CODEX_THREAD_ID": "codex", "CURSOR_AGENT": "cursor-agent",
                "GEMINI_CLI": "gemini"}
_DRY_RUN_PROMPT = "Reply with exactly OK and nothing else."


class NoReviewer(Exception):
    """No configured reviewer passed the dry run."""


class ReviewerFailed(Exception):
    """The reviewer process exited with a non-zero code."""


def command_spec(cfg: dict, name: str) -> Optional[dict]:
    return (cfg.get("reviewer_commands") or {}).get(name) or DEFAULT_COMMANDS.get(name)


_USAGE_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")
_MODEL_RE = re.compile(r'^\s*model\s*=\s*"([^"]+)"', re.M)


def _usage_from_events(stdout: str) -> Optional[dict]:
    """Sum the usage of every `turn.completed` event a JSON-streaming reviewer printed; None if there were none."""
    total: Optional[dict] = None
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            total = total or {key: 0 for key in _USAGE_KEYS}
            for key in _USAGE_KEYS:
                total[key] += int(event["usage"].get(key) or 0)
    return total


def codex_model(config_path: Path = Path.home() / ".codex" / "config.toml") -> Optional[str]:
    """The model codex exec uses: in --json mode it is not printed, so read it from codex's own config."""
    try:
        match = _MODEL_RE.search(Path(config_path).read_text(encoding="utf-8"))
    except OSError:
        return None
    return match.group(1) if match else None


def run_backend_with_usage(spec: dict, prompt: str, cwd: Path, runner: Callable = subprocess.run,
                           which: Callable = shutil.which, timeout: int = 1800) -> Tuple[str, Optional[dict]]:
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
            return Path(out).read_text(encoding="utf-8"), _usage_from_events(proc.stdout or "")
        return proc.stdout, None
    finally:
        Path(out).unlink(missing_ok=True)


def run_backend(spec: dict, prompt: str, cwd: Path, runner: Callable = subprocess.run,
                which: Callable = shutil.which, timeout: int = 1800) -> str:
    return run_backend_with_usage(spec, prompt, cwd, runner, which, timeout)[0]


def dry_run_ok(spec: dict, cwd: Path, runner: Callable = subprocess.run, which: Callable = shutil.which) -> bool:
    try:
        return run_backend(spec, _DRY_RUN_PROMPT, cwd, runner, which, timeout=300).strip() == "OK"
    except Exception:  # noqa: BLE001 — any failure means "not available"
        return False


def author_hosts(env: Mapping[str, str]) -> Set[str]:
    """The hosts that may have written the work under review; none of them may review it."""
    hosts = {host for marker, host in HOST_MARKERS.items() if env.get(marker)}
    hosts.update(name.strip() for name in env.get("WOW_HOST", "").split(",") if name.strip())
    return hosts


def pick_reviewer(cfg: dict, cwd: Path, runner: Callable = subprocess.run,
                  which: Callable = shutil.which, env: Optional[Mapping[str, str]] = None) -> Tuple[str, dict]:
    authors = author_hosts(os.environ if env is None else env)
    tried, skipped = [], []
    for name in cfg.get("reviewers", []):
        if name in authors:
            skipped.append(name)
            continue
        spec = command_spec(cfg, name)
        if spec is None:
            continue
        tried.append(name)
        if dry_run_ok(spec, cwd, runner, which):
            return name, spec
    detail = f"tried: {', '.join(tried) or 'none'}"
    if skipped:
        detail += f"; skipped as author: {', '.join(skipped)}"
    raise NoReviewer(f"no reviewer available ({detail})")
