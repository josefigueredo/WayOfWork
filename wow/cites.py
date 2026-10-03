"""Deterministic citation check: every `path:line` a document cites must exist and be in range.

Citations are read from inline code (`…` in Markdown, <code>…</code> in HTML) of the form path:N, path:N-M or
path:N:col; the path needs an extension, so abbreviations like MAIN:30 are skipped. A bare file name resolves by
name under the root when exactly one file matches. With a commit, files are read at that commit, so a citation
made against a pinned SHA stays checkable after the code moves on.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_SPAN_RE = re.compile(r"`([^`\n]+)`|<code>([^<]+)</code>")
_CITE_RE = re.compile(r"^([A-Za-z0-9_./-]+\.[A-Za-z0-9]+):(\d+)(?:-(\d+))?(?::\d+)?$")
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv"}


def extract(text: str) -> List[Tuple[str, int, int]]:
    found: List[Tuple[str, int, int]] = []
    for match in _SPAN_RE.finditer(text):
        cite = _CITE_RE.match((match.group(1) or match.group(2)).strip())
        if cite:
            start = int(cite.group(2))
            item = (cite.group(1), start, int(cite.group(3) or start))
            if item not in found:
                found.append(item)
    return found


class _Tree:
    """The files under root, either on disk or at a commit."""

    def __init__(self, root: Path, sha: Optional[str]) -> None:
        self.root, self.sha = root, sha
        if sha:
            proc = subprocess.run(["git", "-C", str(root), "ls-tree", "-r", "--name-only", sha],
                                  capture_output=True, text=True)
            if proc.returncode != 0:
                raise ValueError(f"cannot list {sha} in {root}: {proc.stderr.strip()[:200]}")
            self.files = proc.stdout.splitlines()
        else:
            self.files = [p.relative_to(root).as_posix() for p in root.rglob("*")
                          if p.is_file() and not _SKIP_DIRS.intersection(p.relative_to(root).parts)]
        self._set = set(self.files)
        self._text: Dict[str, str] = {}

    def resolve(self, path: str) -> List[str]:
        if path in self._set:
            return [path]
        if "/" in path:
            return [f for f in self.files if f.endswith("/" + path)]
        return sorted(f for f in self.files if f.rsplit("/", 1)[-1] == path)

    def text(self, rel: str) -> str:
        if rel not in self._text:
            if self.sha:
                self._text[rel] = subprocess.run(["git", "-C", str(self.root), "show", f"{self.sha}:{rel}"],
                                                 capture_output=True, text=True, errors="replace").stdout
            else:
                self._text[rel] = (self.root / rel).read_text(encoding="utf-8", errors="replace")
        return self._text[rel]


def _finding(tree: _Tree, path: str, start: int, end: int, aliases: Dict[str, str]) -> Optional[str]:
    label = f"{path}:{start}" + (f"-{end}" if end != start else "")
    head, _, rest = path.partition("/")
    matches = tree.resolve(f"{aliases[head].rstrip('/')}/{rest}" if rest and head in aliases else path)
    if not matches:
        return f"{label}: file not found under the root"
    # Identical copies (a template mirrored for .cursor and .github) say the same thing at the same line.
    if len(matches) > 1 and len({tree.text(m) for m in matches}) > 1:
        shown = ", ".join(matches[:3]) + (", …" if len(matches) > 3 else "")
        return f"{label}: ambiguous name, {len(matches)} files match ({shown}); cite a longer path"
    total = len(tree.text(matches[0]).splitlines())
    if start < 1 or start > end:
        return f"{label}: invalid line range"
    if end > total:
        return f"{label}: line {end} is past the end ({total} lines)"
    return None


def check(text: str, root: Path, sha: Optional[str] = None, aliases: Optional[Dict[str, str]] = None) -> dict:
    tree = _Tree(root, sha)
    citations = extract(text)
    findings = [f for f in (_finding(tree, *c, aliases or {}) for c in citations) if f]
    return {"checked": len(citations), "findings": findings}

