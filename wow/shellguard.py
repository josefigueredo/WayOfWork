"""Guard for the shell commands an agent runs: Cursor's `beforeShellExecution` hook (`wow hook cursor-shell`).

It blocks three things that destroy or flood a repository and that no review catches in time:
- a destructive command (rm -r/-f, cp, mv, rsync) whose path starts with an unguarded variable, `$SRC/...`: if the
  variable is empty, the command runs against the filesystem root (the IRIS pilot's `cp -R "$SRC"/. <dest>`);
- a destructive command aimed at the filesystem root or the home directory;
- a `git commit` that stages more files or bytes than a reasonable change, the trace of a copy gone wrong.
Anything it cannot parse passes: the guard must never stop ordinary work.
"""
from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path
from typing import List, Optional

MAX_FILES = 2000
MAX_BYTES = 100 * 1024 * 1024

_DESTRUCTIVE = {"rm", "cp", "mv", "rsync"}
_PREFIXES = {"sudo", "command", "nice", "nohup", "time"}
_OPERATORS = {"&&", "||", ";", "|", "&", "(", ")"}
# `$NAME/...` or `${NAME}/...`; `${NAME:?}` and `${NAME:-default}` never expand to nothing and pass.
_UNGUARDED_RE = re.compile(r"^\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))/")
_ROOTS = {"/", "/.", "/*", "~", "~/", "~/*", "$HOME", "${HOME}", "$HOME/", "${HOME}/", "$HOME/*"}


def _segments(command: str) -> List[List[str]]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars="&|;()")
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return []
    segments, current = [], []
    for token in tokens:
        if token in _OPERATORS:
            if current:
                segments.append(current)
            current = []
        else:
            current.append(token)
    if current:
        segments.append(current)
    return segments


def _program(words: List[str]) -> List[str]:
    while words and (words[0] in _PREFIXES or "=" in words[0] and not words[0].startswith("-")):
        words = words[1:]
    return words


def _destructive(words: List[str]) -> bool:
    if not words or Path(words[0]).name not in _DESTRUCTIVE:
        return False
    if Path(words[0]).name == "rm":
        return any(w.startswith("-") and not w.startswith("--") and set(w[1:]) & set("rRf")
                   or w in ("--recursive", "--force") for w in words[1:])
    return True


def _path_reason(words: List[str]) -> Optional[str]:
    for arg in words[1:]:
        if arg.startswith("-"):
            continue
        match = _UNGUARDED_RE.match(arg)
        if match:
            name = match.group(1) or match.group(2)
            return (f"`{words[0]}` uses `{arg}`: if {name} is empty this runs against the filesystem root. "
                    f"Guard it with \"${{{name}:?}}\" so the command fails instead.")
        if arg in _ROOTS:
            return f"`{words[0]}` targets `{arg}`, the filesystem root or the home directory."
    return None


def _staged(cwd: Path) -> Optional[List[str]]:
    proc = subprocess.run(["git", "-C", str(cwd), "diff", "--cached", "--name-only", "--diff-filter=AMR", "-z"],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    return [name for name in proc.stdout.split("\0") if name]


def _commit_reason(words: List[str], cwd: Optional[Path], max_files: int, max_bytes: int) -> Optional[str]:
    if cwd is None or not words or Path(words[0]).name != "git":
        return None
    args, repo = words[1:], cwd
    while args and args[0].startswith("-"):
        if args[0] == "-C" and len(args) > 1:
            repo = (cwd / args[1]).resolve()
            args = args[2:]
        else:
            args = args[1:]
    if not args or args[0] != "commit":
        return None
    staged = _staged(repo)
    if staged is None:
        return None
    if len(staged) > max_files:
        return (f"this commit stages {len(staged)} files (limit {max_files}): check that nothing was copied "
                f"into the repo by mistake before committing.")
    toplevel = subprocess.run(["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
                              capture_output=True, text=True).stdout.strip()
    root = Path(toplevel) if toplevel else repo
    total = sum((root / name).stat().st_size for name in staged if (root / name).is_file())
    if total > max_bytes:
        return (f"this commit stages {total / 1e6:.1f} MB (limit {max_bytes / 1e6:.1f} MB): check that nothing "
                f"was copied into the repo by mistake before committing.")
    return None


def check(command: str, cwd: Optional[Path] = None, max_files: int = MAX_FILES,
          max_bytes: int = MAX_BYTES) -> Optional[str]:
    """Why the command must not run, or None when it may."""
    for segment in _segments(command):
        words = _program(segment)
        if _destructive(words):
            reason = _path_reason(words)
            if reason:
                return reason
        reason = _commit_reason(words, Path(cwd) if cwd else None, max_files, max_bytes)
        if reason:
            return reason
    return None
