"""Every commit or GitHub URL a document hands out must exist and be reachable on its remote.

A commit is written as `<name> @ <sha>`; it must be in a repo of the workspace AND on the default branch of that
repo's GitHub remote. Being on GitHub is not enough: a squash-merged, deleted branch leaves commits GitHub still
serves by SHA but no branch contains (the IRIS pilot's BFF fd025ca), and those can be garbage-collected.
GitHub URLs (blob/tree/commit) are checked on their own repo. Deterministic; the remote check uses `gh`.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from sources import repo as repo_src

_SHA_RE = re.compile(r"@\s*([0-9a-f]{7,40})\b")
_URL_RE = re.compile(r"https://github\.com/([\w.-]+/[\w.-]+?)/(?:blob|tree|commit|commits)/([\w.-]+)")
_REMOTE_RE = re.compile(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?$")


def extract(text: str) -> List[Tuple[str, Optional[str], str]]:
    found = [(m.start(), ("sha", None, m.group(1))) for m in _SHA_RE.finditer(text)]
    found += [(m.start(), ("url", m.group(1), m.group(2))) for m in _URL_RE.finditer(text)]
    out: List[Tuple[str, Optional[str], str]] = []
    for _, item in sorted(found):
        if item not in out:
            out.append(item)
    return out


_BARE_RE = re.compile(r"(?<![#\w/@.-])([0-9a-f]{7,40})(?![\w.-])")


def unchecked(text: str) -> List[str]:
    """Hex tokens that look like commits but are neither `name @ sha` nor a GitHub URL, so check() cannot verify
    them. A hash needs a digit and a letter: words such as "decade" and plain numbers are not reported."""
    checked = {ref for _, _, ref in extract(text)}
    found: List[str] = []
    for token in _BARE_RE.findall(text):
        if token in checked or token in found:
            continue
        if re.search(r"[0-9]", token) and re.search(r"[a-f]", token):
            found.append(token)
    return found


def gh_has(owner_repo: str, ref: str) -> bool:
    """The ref is the default branch or one of its ancestors on GitHub (compare status identical or ahead)."""
    if shutil.which("gh") is None:
        return False
    default = subprocess.run(["gh", "api", f"repos/{owner_repo}", "-q", ".default_branch"],
                             capture_output=True, text=True)
    if default.returncode != 0 or not default.stdout.strip():
        return False
    proc = subprocess.run(["gh", "api", f"repos/{owner_repo}/compare/{ref}...{default.stdout.strip()}", "-q", ".status"],
                          capture_output=True, text=True)
    return proc.returncode == 0 and proc.stdout.strip() in ("identical", "ahead")


def _git(repo: Path, *args: str) -> Optional[str]:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


def _repos(project: Path) -> List[Path]:
    roots = [project] if _git(project, "rev-parse", "--git-dir") is not None else []
    return roots + [project / rel for rel in repo_src.child_repos(project)]


def check(text: str, project: Path, on_remote: Callable[[str, str], bool] = gh_has) -> List[str]:
    findings: List[str] = []
    repos = _repos(project)
    for kind, owner_repo, ref in extract(text):
        if kind == "url":
            if not on_remote(owner_repo, ref):
                findings.append(f"https://github.com/{owner_repo} @ {ref}: not on the default branch, or not accessible")
            continue
        holders = []
        for repo in repos:
            full = _git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
            if full:
                holders.append((repo, full))
        if not holders:
            findings.append(f"{ref}: commit not found in any repo of the workspace")
            continue
        verdicts = []
        for repo, full in holders:
            remote = _REMOTE_RE.search(_git(repo, "remote", "get-url", "origin") or "")
            name = repo.relative_to(project).as_posix() if repo != project else project.name
            if remote is None:
                verdicts.append(f"{ref}: commit in {name}, which has no GitHub origin to verify it on")
            elif on_remote(remote.group(1), full):
                verdicts = []
                break
            else:
                verdicts.append(f"{ref}: commit in {name} but not on the default branch of {remote.group(1)} "
                                f"(local only, or a squash-merged/deleted branch): cite a commit on origin's default branch")
        findings += verdicts[:1]
    return findings
