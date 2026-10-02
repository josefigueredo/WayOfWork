"""Shared test helpers: import path for the flat wow modules and temp projects."""
from __future__ import annotations

import io
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent.parent
WOW_DIR = ROOT / "wow"
if str(WOW_DIR) not in sys.path:
    sys.path.insert(0, str(WOW_DIR))

_TEMP_DIRS = []


def make_project() -> Path:
    """Return a fresh empty project directory that lives until the process exits."""
    tmp = tempfile.TemporaryDirectory()
    _TEMP_DIRS.append(tmp)
    return Path(tmp.name)


def write(project: Path, rel: str, text: str) -> Path:
    path = project / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def run_cli(args: List[str]) -> Tuple[int, str, str]:
    import cli

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(args)
    return code, out.getvalue(), err.getvalue()
