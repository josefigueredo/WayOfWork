"""Context pack: inventory of repos and docs, and validation of tagged claims (spec 6.2 phase 0)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from sources import repo

CLAIM_FILES = ("facts.md", "metrics.md", "decisions.md", "contracts.md")
_CLAIM_START_RE = re.compile(r"^\s*-\s*(C[0-9]+):")
_CLAIM_FULL_RE = re.compile(r"^\s*-\s*(C[0-9]+):\s*(.+?)\s*\[(MEDIDO|ESTIMACI[ÓO]N|SIN DEFINIR)\]\s*"
                            r"(?:\((?:fuente|source):\s*([^)]+)\))?\s*$")
_CLAIM_FORMAT = "<!-- one claim per line: - C1: <claim> [MEDIDO|ESTIMACIÓN|SIN DEFINIR] (fuente: path:line) -->"
SKELETONS: Dict[str, str] = {
    "facts.md": f"# Hechos\n\n{_CLAIM_FORMAT}\n",
    "metrics.md": f"# Métricas\n\n{_CLAIM_FORMAT}\n",
    "decisions.md": f"# Decisiones y alternativas descartadas\n\n{_CLAIM_FORMAT}\n",
    "contracts.md": f"# Contratos\n\n{_CLAIM_FORMAT}\n",
    "pending-owner.md": "# Decisiones pendientes del owner\n\n"
                        "<!-- one per line: - [ ] <decision>; mark - [x] when decided or accepted as [SIN DEFINIR] -->\n",
}


def children(project: Path) -> List[Path]:
    return [project / rel for rel in repo.child_repos(project)]


def _docs(project: Path, root: Path) -> List[str]:
    candidates = list(root.glob("README*")) + list(root.glob("docs/**/*.md")) + \
        list(root.glob("docs/**/openapi*.y*ml")) + list(root.glob("openapi*.y*ml"))
    return sorted({p.relative_to(project).as_posix() for p in candidates if p.is_file()})[:40]


def scan(project: Path) -> dict:
    kids = children(project)
    docs = _docs(project, project)
    for kid in kids:
        docs += _docs(project, kid)
    base = project / "wow" / "context-pack"
    base.mkdir(parents=True, exist_ok=True)
    created = []
    for name, text in SKELETONS.items():
        path = base / name
        if not path.exists():
            path.write_text(text, encoding="utf-8")
            created.append(f"wow/context-pack/{name}")
    lines = ["# Inventario (generado por `wow context scan`)", "", "## Repos"]
    lines += [f"- {k.name} ({k.relative_to(project).as_posix()})" for k in kids] or ["- (ninguno)"]
    lines += ["", "## Documentos"] + ([f"- {d}" for d in docs] or ["- (ninguno)"]) + [""]
    (base / "inventory.md").write_text("\n".join(lines), encoding="utf-8")
    return {"children": [k.relative_to(project).as_posix() for k in kids], "docs": docs, "created": created}


def _discovery_pairs(project: Path):
    """Verified discovery copies (wow/context-pack/discovery/) and where Spec-Kit keeps each one."""
    verified = project / "wow" / "context-pack" / "discovery"
    for path in sorted(verified.glob("*.md")) if verified.is_dir() else []:
        if path.name == "ERRATA.md":
            target = project / ".spec-kit" / "discovery" / "ERRATA.md"
        elif path.name == "local-constitution.md":
            target = project / "local-constitution.md"
        else:
            target = project / ".spec-kit" / "discovery" / path.name
        yield path, target


def _drifted(project: Path) -> List[Path]:
    return [target for source, target in _discovery_pairs(project)
            if not target.is_file() or target.read_bytes() != source.read_bytes()]


def restore_discovery(project: Path) -> List[str]:
    """Copy the verified discovery back over what a new /spec-kit.discovery wrote; return what changed."""
    restored = []
    for source, target in _discovery_pairs(project):
        if not target.is_file() or target.read_bytes() != source.read_bytes():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            restored.append(target.relative_to(project).as_posix())
    return restored


def check(project: Path) -> List[str]:
    findings: List[str] = []
    for target in _drifted(project):
        rel = target.relative_to(project).as_posix()
        findings.append(f"discovery: {rel} differs from its verified copy in wow/context-pack/discovery/ "
                        f"(a new /spec-kit.discovery overwrote the corrections?): wow context restore puts them back")
    seen: Dict[str, str] = {}
    for name in CLAIM_FILES:
        path = project / "wow" / "context-pack" / name
        if not path.is_file():
            findings.append(f"{name}: missing (run wow context scan)")
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip().startswith("- "):
                continue
            start = _CLAIM_START_RE.match(line)
            if not start:
                findings.append(f"{name}:{number}: not a claim (expected '- C<n>: … [TAG] (fuente: …)')")
                continue
            claim_id = start.group(1)
            if claim_id in seen:
                findings.append(f"{name}:{number}: duplicate id {claim_id} (first at {seen[claim_id]})")
                continue
            seen[claim_id] = f"{name}:{number}"
            full = _CLAIM_FULL_RE.match(line)
            if not full:
                findings.append(f"{name}:{number}: {claim_id} needs a tag [MEDIDO], [ESTIMACIÓN] or [SIN DEFINIR]")
                continue
            tag, source = full.group(3), full.group(4)
            if tag != "SIN DEFINIR" and not source:
                findings.append(f"{name}:{number}: {claim_id} needs a source (fuente: path:line)")
                continue
            if source:
                rel = source.strip().split(":")[0]
                target = (project / rel).resolve()
                if target != project.resolve() and project.resolve() not in target.parents:
                    findings.append(f"{name}:{number}: {claim_id} source outside the project: {rel}")
                elif not target.exists():
                    findings.append(f"{name}:{number}: {claim_id} source not found: {rel}")
    return findings
