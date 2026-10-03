"""Bake progress.json snapshots into the offline dashboard so the summary opens without a drop (one file)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Tuple

TEMPLATE = Path(__file__).resolve().parent.parent / "dashboard" / "wow-dashboard.html"
_BLOCK_RE = re.compile(r'(<script type="application/json" id="wow-embedded">)(.*?)(</script>)', re.S)


def embed(template: str, docs: List[Tuple[str, dict]]) -> str:
    """Put [{name, doc}] into the wow-embedded data block. '</' is escaped so no value can close the script."""
    payload = json.dumps([{"name": name, "doc": doc} for name, doc in docs], ensure_ascii=False).replace("</", "<\\/")
    result, count = _BLOCK_RE.subn(lambda m: m.group(1) + payload + m.group(3), template, count=1)
    if count != 1:
        raise ValueError("the dashboard template has no wow-embedded block")
    return result
