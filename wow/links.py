"""Attach Jira, GitHub and repo links to the derived state (spec 7.1)."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import List

from sources import github, speckit

_PLAN_FILES = ("wow/plan/PLAN.md", "wow/plan/manifest.json", "wow/pb/prd.md", "wow/pb/rfc.md",
               "wow/context-pack/facts.md")


def build_links(project: Path, state: dict, prs: List[dict]) -> dict:
    result = copy.deepcopy(state)
    features = speckit.features(project)
    for epic in result["epics"]:
        key = epic.get("jira")
        feature = next((f for f in features if key and f["epic_key"] == key), None)
        keys = ({key} if key else set()) | (set(feature["stories"]) if feature else set())
        files = []
        if feature:
            files += [f"{feature['dir']}/{name}" for name in ("spec.md", "plan.md", "tasks.md")
                      if (project / feature["dir"] / name).is_file()]
        # An epic packet is only linked once the epic is exported (it has a Jira key).
        packet = f"wow/pb/epic-{epic['id']}.md"
        if key and (project / packet).is_file():
            files.append(packet)
        epic["links"] = {"jira": epic.get("jira_url"), "prs": github.link(prs, keys) if keys else [],
                         "files": files}
    result["plan"]["links"] = {"files": [p for p in _PLAN_FILES if (project / p).is_file()]}
    return result
