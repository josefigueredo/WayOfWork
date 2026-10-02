# WayOfWork · Plan 3: lado Product Brain — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Completar el lado Product Brain de `wow`: paquetes PRD/RFC/épica generados desde el manifiesto (`wow pack`), auditoría de las copias de chats de PB (`wow pbchat audit`, con modo profundo vía revisor independiente), el context pack (`wow context scan|check`), la fuente GitHub con links en el snapshot, el guard de escritura del manifiesto (`wow plan guard`) y las skills `wow-pack`, `wow-pb-audit`, `wow-context` y `wow-plan`.

**Architecture:** Módulos planos de `wow/` (Planes 1 y 2 ya implementados). Cada módulo nuevo tiene una responsabilidad: `pack.py` (render determinista de paquetes), `pbaudit.py` (auditoría de chat), `contextpack.py` (inventario y validación de afirmaciones), `sources/github.py` (lectura de PRs con `gh`), `links.py` (enlaces en el snapshot). Procesos externos (`gh`, revisores) con `runner`/`which` inyectables.

**Tech Stack:** Python 3.9+ stdlib.

**Spec:** `docs/superpowers/specs/2026-10-01-wayofwork-design.md` (secciones 5.2, 7.1, 9, 9.2, 9.3, 10, 11). Planes previos: `2026-10-01-wow-core-guide.md`, `2026-10-02-wow-review-usage-sk.md`.

## Global Constraints

- Python compatible con **3.9** (`/usr/bin/python3`) y Homebrew; `from __future__ import annotations`; solo stdlib; tests con `unittest`, sin red ni modelos reales.
- Código, comentarios, CLI, schemas y `SKILL.md` en **inglés**. El **contenido de los paquetes y de las correcciones para pegar en PB está en castellano**: es documentación humana que se pega en un chat de PB en castellano (regla D10 del spec).
- Exit codes: `0` OK · `1` hallazgos · `2` no pude evaluar.
- `wow` no escribe en Jira, Confluence, GitHub ni artefactos de Spec-Kit. Escrituras nuevas permitidas: `wow/pb/*.md`, `wow/pb/chats/*.audit.json`, `wow/context-pack/*.md` (esqueletos e inventario), `wow/progress.json`.
- `wow pack` nunca pisa un paquete existente sin `--force` (perdería lo que Opus completó).
- Los nombres de documento de chat (`prd`, `rfc`, `epic-E1`) se validan con `review.safe_ref` antes de usarse en rutas.
- Commits: Conventional Commits sin atribución de IA, uno por tarea, en `main`. **El commit va solo si ambas suites salen con exit 0** (no gatear con `rg`).
- Suite: `python3 -m unittest discover -s tests` y `/usr/bin/python3 -m unittest discover -s tests`.

## Review Focus

1. **El preámbulo pegado en el chat contiene "API Gateway", "Okta/OAuth", "comprador/vendedor" y "SLAs"** → la auditoría no lo marca como invento. Test en Task 2.
2. **El operador corrige a PB en el chat ("no hay API Gateway")** → una frase negativa no cuenta como invento. Test en Task 2.
3. **`wow pack` sobre un paquete ya completado por Opus** → sale con `1` sin tocarlo, salvo `--force`. Test en Task 1.
4. **`gh` no instalado, sin auth o carpeta sin remoto** → `sources.github` queda con el motivo y el snapshot se escribe igual; con al menos un repo leído queda `partial: …`. Test en Task 5.
5. **Afirmación del context pack que cita un archivo inexistente** → `wow context check` lo reporta y sale con `1`. Test en Task 4.

---

## File Structure

```
wow/pack.py              render PRD/RFC/épica + preámbulo — Task 1
wow/pbaudit.py           auditoría de copia de chat (determinista + profunda) — Tasks 2, 3
wow/contextpack.py       scan (inventario + esqueletos) y check de afirmaciones — Task 4
wow/sources/repo.py      (modificar) submodule_paths — Task 4
wow/sources/github.py    PRs vía gh — Task 5
wow/links.py             enlaces por épica y plan — Task 5
wow/cli.py               (modificar) pack, pbchat audit, context, plan guard, snapshot+github — Tasks 1–6
schemas/pbchat-audit.schema.json   Task 2
skills/wow-pack/SKILL.md · wow-pb-audit · wow-context · wow-plan   Task 6
tests/test_pack.py · test_pbaudit.py · test_contextpack.py · test_github.py · test_links.py
tests/test_cli.py        (modificar)
README.md                (modificar) Task 6
```

---

### Task 1: `pack.py` y `wow pack`

**Files:**
- Create: `wow/pack.py`, `tests/test_pack.py`
- Modify: `wow/cli.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `manifest.load/validate/manifest_hash` (Plan 1), `repo.HASH_RE` (Plan 1).
- Produces:
  - `pack.PREAMBLE: str` (las 7 reglas, igual que en `way-of-work.html`)
  - `pack.UNDEFINED = "[SIN DEFINIR]"`
  - `pack.parse_brief(text: str) -> dict` → claves `Goal`, `Decisions`, `Constraints`, `Non-goals`, `Open questions` (valores `""` si faltan), leídas de las viñetas `- Clave: valor` bajo `## Brief`.
  - `pack.render_prd(doc: dict, brief: dict, mhash: str) -> str`
  - `pack.render_rfc(doc: dict, brief: dict, mhash: str) -> str`
  - `pack.render_epic(doc: dict, epic_id: str, mhash: str) -> str` (épica desconocida → `ValueError`)
  - Cada render empieza con `<!-- wow: manifest-hash=<mhash> · generated by `wow pack …` -->` (lo reconoce `repo.HASH_RE`) y marca lo narrativo con `<!-- wow:fill <qué completar> -->`.
  - `pack.write_packet(project: Path, name: str, text: str, force: bool = False) -> Path` (existe y no `force` → `FileExistsError`)
  - `pack.ensure_preamble(project: Path) -> Path` (escribe `wow/pb/preamble.md` si falta)
  - CLI: `wow pack {prd,rfc,epic} [--id E1] [--force] [--project DIR]`. Manifiesto ausente o inválido → `2`; `epic` sin `--id` o con id desconocido → `2`; paquete existente sin `--force` → `1`; si no, imprime `wrote wow/pb/<name>.md` y `0`.

- [ ] **Step 1: Escribir el test que falla**

`tests/test_pack.py`:

```python
from __future__ import annotations

import unittest

from helpers import make_project, write
import config
import manifest
import pack
import state
from sources import repo
from test_manifest import valid_doc

BRIEF = """# Plan
## Brief
- Goal: Curar casos en IRIS v2
- Decisions: D1 una sola máquina de estados · D2 BFF como frontera
- Constraints: costo del juez ≤ USD 100
- Non-goals: migrar datos históricos
- Open questions: none
## Other
- Goal: ignored
"""


class BriefTest(unittest.TestCase):
    def test_parse_brief_only_reads_brief_section(self):
        brief = pack.parse_brief(BRIEF)
        self.assertEqual(brief["Goal"], "Curar casos en IRIS v2")
        self.assertEqual(brief["Non-goals"], "migrar datos históricos")
        self.assertEqual(brief["Open questions"], "none")

    def test_missing_brief_gives_empty_values(self):
        self.assertEqual(pack.parse_brief("nothing")["Goal"], "")


class RenderTest(unittest.TestCase):
    def test_epic_packet_maps_tasks_to_stories(self):
        text = pack.render_epic(valid_doc(), "E1", "0123456789abcdef")
        self.assertEqual(repo.HASH_RE.search(text).group(1), "0123456789abcdef")
        self.assertIn("# Épica E1 — Curation", text)
        self.assertIn("- E1.C1: analysts can curate", text)
        self.assertIn("### H2 — API (tarea 1.2)", text)
        self.assertIn("- Story points: 2   ·   Prioridad: media   ·   Depende de: H1", text)
        self.assertIn("  - AC1: endpoint returns 200", text)
        self.assertIn("<!-- wow:fill", text)

    def test_epic_undefined_values_and_unknown_epic(self):
        doc = valid_doc()
        doc["epics"][0]["tasks"][0].update({"estimate": None, "priority": None, "labels": []})
        text = pack.render_epic(doc, "E1", "0123456789abcdef")
        self.assertIn("- Story points: [SIN DEFINIR]   ·   Prioridad: [SIN DEFINIR]   ·   Depende de: —", text)
        with self.assertRaises(ValueError):
            pack.render_epic(doc, "E9", "0123456789abcdef")

    def test_prd_and_rfc_use_brief(self):
        brief = pack.parse_brief(BRIEF)
        prd = pack.render_prd(valid_doc(), brief, "0123456789abcdef")
        self.assertIn("## Resumen\nCurar casos en IRIS v2", prd)
        self.assertIn("### Fuera de alcance\nmigrar datos históricos", prd)
        self.assertIn("## Preguntas abiertas\nNinguna.", prd)
        self.assertIn("- Autor: [SIN DEFINIR]", prd)
        rfc = pack.render_rfc(valid_doc(), brief, "0123456789abcdef")
        self.assertIn("- D1 una sola máquina de estados", rfc)
        self.assertIn("- D2 BFF como frontera", rfc)
        self.assertIn("### E1 — Curation", rfc)


class WriteTest(unittest.TestCase):
    def test_refuses_overwrite_without_force(self):
        project = make_project()
        pack.write_packet(project, "prd", "v1")
        with self.assertRaises(FileExistsError):
            pack.write_packet(project, "prd", "v2")
        pack.write_packet(project, "prd", "v2", force=True)
        self.assertEqual((project / "wow/pb/prd.md").read_text(encoding="utf-8"), "v2")

    def test_preamble_written_once(self):
        project = make_project()
        path = pack.ensure_preamble(project)
        self.assertIn("[SIN DEFINIR]", path.read_text(encoding="utf-8"))
        path.write_text("edited", encoding="utf-8")
        pack.ensure_preamble(project)
        self.assertEqual(path.read_text(encoding="utf-8"), "edited")


class StateIntegrationTest(unittest.TestCase):
    def test_packed_project_reaches_phase_3(self):
        project = make_project()
        write(project, "wow/context-pack/facts.md", "x")
        write(project, "wow/context-pack/pending-owner.md", "")
        doc = valid_doc()
        doc["plan"]["readiness"] = {"verdict": "approved", "rounds": 1}
        manifest.save(project, doc)
        write(project, "wow/plan/PLAN.md", BRIEF)
        mhash = manifest.manifest_hash(project)
        brief = pack.parse_brief(BRIEF)
        pack.write_packet(project, "prd", pack.render_prd(doc, brief, mhash))
        pack.write_packet(project, "rfc", pack.render_rfc(doc, brief, mhash))
        pack.write_packet(project, "epic-E1", pack.render_epic(doc, "E1", mhash))
        self.assertEqual(state.compute_state(project, config.DEFAULTS)["plan"]["phase"], 3)


if __name__ == "__main__":
    unittest.main()
```

Agregar a `tests/test_cli.py`:

```python
class PackCommandTest(unittest.TestCase):
    def test_pack_epic_writes_and_refuses_second_time(self):
        project = make_project()
        _manifest.save(project, valid_doc())
        args = ["pack", "epic", "--id", "E1", "--project", str(project)]
        code, out, _ = run_cli(args)
        self.assertEqual(code, 0)
        self.assertIn("wrote wow/pb/epic-E1.md", out)
        self.assertTrue((project / "wow/pb/preamble.md").is_file())
        self.assertEqual(run_cli(args)[0], 1)
        self.assertEqual(run_cli(args + ["--force"])[0], 0)

    def test_pack_epic_needs_valid_id_and_manifest(self):
        project = make_project()
        self.assertEqual(run_cli(["pack", "prd", "--project", str(project)])[0], 2)
        _manifest.save(project, valid_doc())
        self.assertEqual(run_cli(["pack", "epic", "--project", str(project)])[0], 2)
        self.assertEqual(run_cli(["pack", "epic", "--id", "E9", "--project", str(project)])[0], 2)
```

- [ ] **Step 2: Correr y verificar que falla** — ERROR `No module named 'pack'`.

- [ ] **Step 3: Implementar `wow/pack.py`**

```python
"""Product Brain packets rendered from the upstream manifest and Brief (spec 9, 9.3).

Packet text is Spanish on purpose: it is pasted into Product Brain chats (spec D10).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

PREAMBLE = """Reglas para este documento (aplicalas en todas las secciones):
1. Usá solo la información de este chat y de los documentos que adjunto. Si un dato no está,
   escribí [SIN DEFINIR] y agregalo a "Preguntas abiertas". No lo completes con ejemplos genéricos.
2. Conservá las etiquetas [MEDIDO], [ESTIMACIÓN] y [SIN DEFINIR] tal como vienen.
3. Si una sección de la plantilla no aplica a este dominio (por ejemplo comprador/vendedor),
   escribí "No aplica: <motivo>" en vez de adaptarla.
4. No agregues componentes, proveedores, SLAs, North Star con targets, plazos ni owners que no
   figuren en el material (no hay API Gateway; la autenticación no es Okta/OAuth).
5. Las decisiones pendientes del owner van a "Preguntas abiertas", no se resuelven por inferencia.
6. Conservá los ids de los criterios (AC1, E1.C1…) tal como vienen.
7. Antes de dar una sección por completa, listá las afirmaciones que no tienen fuente en el material.
   No marques un ítem del checklist como cumplido sin citar dónde se cumple.
"""

UNDEFINED = "[SIN DEFINIR]"
PRIORITY_ES = {"high": "alta", "medium": "media", "low": "baja"}
_BRIEF_KEYS = ("Goal", "Decisions", "Constraints", "Non-goals", "Open questions")
_BULLET_RE = re.compile(r"^\s*-\s*([A-Za-z -]+?):\s*(.*)$")


def parse_brief(text: str) -> Dict[str, str]:
    brief = {key: "" for key in _BRIEF_KEYS}
    inside = False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line.strip().lower() == "## brief"
            continue
        match = _BULLET_RE.match(line) if inside else None
        if match and match.group(1).strip() in brief:
            brief[match.group(1).strip()] = match.group(2).strip()
    return brief


def _header(mhash: str, command: str) -> str:
    return f"<!-- wow: manifest-hash={mhash} · generated by `{command}` -->"


def _fill(what: str) -> str:
    return f"<!-- wow:fill {what} -->"


def _or_undefined(value: str) -> str:
    return value if value and value.strip().lower() not in ("none", "ninguna") else UNDEFINED


def _questions(brief: Dict[str, str]) -> str:
    value = brief["Open questions"].strip()
    return "Ninguna." if not value or value.lower() in ("none", "ninguna") else value


def render_prd(doc: dict, brief: Dict[str, str], mhash: str) -> str:
    plan = doc["plan"]
    lines: List[str] = [
        _header(mhash, "wow pack prd"), f"# PRD — {plan['title']}", "",
        "## Resumen", _or_undefined(brief["Goal"]), "",
        "## Contexto y problema", _fill("qué duele hoy, a quién y qué pasa si no se resuelve"), "",
        "## Usuarios objetivo", _fill("quién lo usa y en qué contexto"), "",
        "## Alcance", "### Dentro de alcance"]
    lines += [f"- {epic['id']}: {epic['title']}" for epic in doc["epics"]]
    lines += ["", "### Fuera de alcance", _or_undefined(brief["Non-goals"]), "",
              "## Objetivos y métricas de éxito",
              _fill("métricas numéricas con [MEDIDO], [ESTIMACIÓN] o [SIN DEFINIR]"), "",
              "## Visión y estrategia", _fill("período de roadmap y objetivos; [SIN DEFINIR] si el owner no decidió"), "",
              "## Metadata", f"- Iniciativa: {plan['id']}", f"- Autor: {UNDEFINED}", f"- Vertical: {UNDEFINED}",
              f"- Prioridad: {UNDEFINED}", "",
              "## Supuestos", _fill("qué se da por cierto sin haberlo verificado"), "",
              "## Requerimientos no funcionales", _fill("performance, seguridad, compliance, disponibilidad"), "",
              "## Requerimientos clave"]
    lines += [f"- {item}" for epic in doc["epics"] for item in epic["done_when"]] or [f"- {UNDEFINED}"]
    lines += ["", "## Riesgos y dependencias", _fill("riesgos con mitigación y dependencias externas"), "",
              "## Preguntas abiertas", _questions(brief), ""]
    return "\n".join(lines)


def render_rfc(doc: dict, brief: Dict[str, str], mhash: str) -> str:
    plan = doc["plan"]
    decisions = [d.strip() for d in brief["Decisions"].split("·") if d.strip()]
    lines: List[str] = [
        _header(mhash, "wow pack rfc"), f"# RFC — {plan['title']}", "",
        "## Contexto", _or_undefined(brief["Goal"]), "", f"Restricciones: {_or_undefined(brief['Constraints'])}", "",
        "## Stack", _fill("repos, lenguajes, almacenamiento y despliegue reales"), "",
        "## Arquitectura", _fill("componentes y flujo; solo lo que existe en el código"), "",
        "## Detalles", _fill("endpoints, límites, timeouts y observabilidad"), "",
        "## Decisiones"]
    lines += [f"- {d}" for d in decisions] or [f"- {UNDEFINED}"]
    lines += ["", "## Alternativas descartadas", _fill("cada alternativa con su motivo de descarte"), "",
              "## Plan de implementación"]
    for epic in doc["epics"]:
        lines.append(f"### {epic['id']} — {epic['title']}")
        lines += [f"- {task['id']} {task['title']}" for task in epic["tasks"]]
    lines += ["", "## Transversales", _fill("seguridad, observabilidad, rollout y rollback"), "",
              "## APIs y contratos", _fill("contratos reales; marcar lo no declarado"), "",
              "## Preguntas abiertas", _questions(brief), ""]
    return "\n".join(lines)


def render_epic(doc: dict, epic_id: str, mhash: str) -> str:
    epic = next((e for e in doc["epics"] if e["id"] == epic_id), None)
    if epic is None:
        raise ValueError(f"epic {epic_id} not found in the manifest")
    stories = {task["id"]: f"H{n}" for n, task in enumerate(epic["tasks"], 1)}
    labels = sorted({label for task in epic["tasks"] for label in task["labels"]})
    lines: List[str] = [
        _header(mhash, f"wow pack epic --id {epic_id}"), f"# Épica {epic_id} — {epic['title']}",
        f"Iniciativa: {doc['plan']['id']} · Labels: {', '.join(labels) or UNDEFINED}", "",
        "## Objetivo", _fill("qué resuelve esta épica, en una frase"), "",
        "## Criterios de cierre (done_when)"]
    lines += [f"- {item}" for item in epic["done_when"]] or [f"- {UNDEFINED}"]
    lines += ["", "## Historias"]
    for task in epic["tasks"]:
        deps = ", ".join(stories.get(d, f"{d} (otra épica)") for d in task["depends_on"]) or "—"
        points = task["estimate"] if task["estimate"] is not None else UNDEFINED
        priority = PRIORITY_ES.get(task["priority"], UNDEFINED)
        lines += [f"### {stories[task['id']]} — {task['title']} (tarea {task['id']})",
                  f"- Story points: {points}   ·   Prioridad: {priority}   ·   Depende de: {deps}",
                  f"- Labels: {', '.join(task['labels']) or UNDEFINED}",
                  "- Criterios de aceptación:"]
        lines += [f"  - {item}" for item in task["acceptance"]] or [f"  - {UNDEFINED}"]
        lines += ["- Tasks:"] + ([f"  - {s}" for s in task["subtasks"]] or ["  - (sin subtareas)"]) + [""]
    lines += ["## Fuera de alcance de esta épica", _fill("qué no entra en esta épica"), ""]
    return "\n".join(lines)


def write_packet(project: Path, name: str, text: str, force: bool = False) -> Path:
    path = project / "wow" / "pb" / f"{name}.md"
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def ensure_preamble(project: Path) -> Path:
    path = project / "wow" / "pb" / "preamble.md"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(PREAMBLE, encoding="utf-8")
    return path
```

En `wow/cli.py`: `import pack`, más:

```python
def _cmd_pack(args) -> int:
    project = _project(args)
    try:
        doc = manifest.load(project)
    except manifest.ManifestError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    errors = manifest.validate(doc)
    if errors:
        sys.stderr.write("wow: manifest is invalid; run wow manifest validate\n")
        return exitcodes.CANNOT_EVALUATE
    plan_md = project / "wow" / "plan" / "PLAN.md"
    brief = pack.parse_brief(plan_md.read_text(encoding="utf-8") if plan_md.is_file() else "")
    mhash = manifest.manifest_hash(project)
    try:
        if args.kind == "epic":
            if not args.id:
                sys.stderr.write("wow: pack epic needs --id E<n>\n")
                return exitcodes.CANNOT_EVALUATE
            name, text = f"epic-{args.id}", pack.render_epic(doc, args.id, mhash)
        elif args.kind == "prd":
            name, text = "prd", pack.render_prd(doc, brief, mhash)
        else:
            name, text = "rfc", pack.render_rfc(doc, brief, mhash)
    except ValueError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    try:
        pack.write_packet(project, name, text, force=args.force)
    except FileExistsError:
        sys.stderr.write(f"wow: wow/pb/{name}.md exists; --force overwrites it (filled sections are lost)\n")
        return exitcodes.FINDINGS
    pack.ensure_preamble(project)
    print(f"wrote wow/pb/{name}.md")
    return exitcodes.OK
```

En `build_parser`:

```python
    pk = with_project(sub.add_parser("pack", help="render Product Brain packets from the manifest"))
    pk.add_argument("kind", choices=["prd", "rfc", "epic"])
    pk.add_argument("--id", default=None, help="epic id for kind 'epic'")
    pk.add_argument("--force", action="store_true", help="overwrite an existing packet")
    pk.set_defaults(handler=_cmd_pack)
```

- [ ] **Step 4: Correr ambas suites** — exit 0 en las dos.

- [ ] **Step 5: Commit (solo con ambas suites en 0)**

```bash
python3 -m unittest discover -s tests && /usr/bin/python3 -m unittest discover -s tests && \
git add wow/pack.py wow/cli.py tests/test_pack.py tests/test_cli.py && \
git commit -m "feat(pack): render Product Brain packets from the manifest and Brief"
```

---

### Task 2: `pbaudit.py` (auditoría determinista) y `wow pbchat audit`

**Files:**
- Create: `wow/pbaudit.py`, `schemas/pbchat-audit.schema.json`, `tests/test_pbaudit.py`
- Modify: `wow/cli.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `pbchat.parse_chat`, `pbchat.ANCHOR_RE` (Plan 1), `pack.PREAMBLE` (Task 1), `review.safe_ref` (Plan 2).
- Produces:
  - `pbaudit.KNOWN_INVENTIONS: list[tuple[str, str]]` — semilla del spec 9.3: marketplace, comprador/vendedor, API Gateway, Okta, OAuth, SLA.
  - `pbaudit.open_questions(text: str) -> list[str]` (ítems numerados o con viñeta bajo la **última** línea corta que contiene "Preguntas abiertas"; continúan las líneas indentadas; corta en el primer texto no-ítem).
  - `pbaudit.audit(project: Path, doc: str, extra_inventions: list | None = None) -> dict` con el contrato `pbchat-audit`: `{"schema_version": 1, "doc", "verdict": "approved"|"changes_required", "closed", "completion_pct", "open_questions", "expected_anchors", "missing_anchors", "unsupported_checks", "inventions", "corrections_to_paste"}`. Reglas:
    - Se ignoran las líneas del chat idénticas (sin espacios) a líneas de `PREAMBLE`.
    - Un término conocido es invento si aparece en el chat y **no** aparece en el paquete (`wow/pb/<doc>.md`) ni en `wow/context-pack/*.md`; las líneas con negación (`no hay`, `no es`, `no existe`, `no usa`, `inexistente`, `sin`) no cuentan.
    - `expected_anchors` = anclas `ACn`/`En.Cn` del paquete; `missing_anchors` = las que no aparecen en el chat.
    - `unsupported_checks` = líneas con `✅`/`✔` sin cita (`(`, `fuente`, `source`, `sección`, `§`).
    - `completion_pct` = último número de "llega al N%", "documento al N%" o "completitud … N%"; `null` si no hay.
    - `verdict = "approved"` si no hay anclas faltantes, inventos ni checks sin cita.
    - `corrections_to_paste` (castellano) cita la regla del preámbulo de cada hallazgo; vacío si está aprobado.
    - Chat ausente → `FileNotFoundError`.
  - `pbaudit.write_audit(project: Path, result: dict) -> Path` (`wow/pb/chats/<doc>.audit.json`)
  - CLI: `wow pbchat audit DOC [--project DIR]`: doc inseguro → `2`; chat ausente → `2`; escribe el audit, imprime `verdict: …` y las correcciones; `0` aprobado, `1` cambios.

- [ ] **Step 1: Escribir `schemas/pbchat-audit.schema.json`**

```json
{
  "type": "object",
  "required": ["schema_version", "doc", "verdict", "closed", "completion_pct", "open_questions",
               "expected_anchors", "missing_anchors", "unsupported_checks", "inventions", "corrections_to_paste"],
  "properties": {
    "schema_version": {"type": "integer", "enum": [1]},
    "doc": {"type": "string"},
    "verdict": {"type": "string", "enum": ["approved", "changes_required"]},
    "closed": {"type": "boolean"},
    "completion_pct": {"type": ["integer", "null"], "minimum": 0, "maximum": 100},
    "open_questions": {"type": "array", "items": {"type": "string"}},
    "expected_anchors": {"type": "array", "items": {"type": "string"}},
    "missing_anchors": {"type": "array", "items": {"type": "string"}},
    "unsupported_checks": {"type": "array", "items": {"type": "object", "required": ["line", "text"]}},
    "inventions": {"type": "array", "items": {"type": "object", "required": ["term", "line", "text", "source"]}},
    "corrections_to_paste": {"type": "string"}
  }
}
```

- [ ] **Step 2: Escribir el test que falla**

`tests/test_pbaudit.py`:

```python
from __future__ import annotations

import json
import unittest

from helpers import make_project, write
import pack
import pbaudit
import schema

PACKET = "<!-- wow: manifest-hash=0123456789abcdef -->\n### H1\n  - AC1: schema exists\n  - AC2: audit row\n- E1.C1: done\n"
CHAT = pack.PREAMBLE + """
Product Brain: Completé el documento. El PRD llega al 100%.
- AC1: schema exists
- E1.C1: done
La plataforma funciona como un marketplace con comprador y vendedor.
Jose: no hay API Gateway, corregilo.
✅ Los KPIs están documentados.
✅ El alcance está explícito (sección Alcance).

## 15. Preguntas abiertas

1. ¿Se incorpora la etapa de plan
   a la máquina de estados?
2. ¿Qué North Star define el owner?

Product Brain: ¿Querés profundizar?
"""


def setup(chat=CHAT, context=""):
    project = make_project()
    write(project, "wow/pb/prd.md", PACKET)
    write(project, "wow/pb/chats/prd.md", chat)
    if context:
        write(project, "wow/context-pack/facts.md", context)
    return project


class AuditTest(unittest.TestCase):
    def test_full_audit(self):
        result = pbaudit.audit(setup(), "prd")
        self.assertEqual(schema.validate(result, schema.load_schema("pbchat-audit")), [])
        self.assertEqual(result["verdict"], "changes_required")
        self.assertTrue(result["closed"])
        self.assertEqual(result["completion_pct"], 100)
        self.assertEqual(result["expected_anchors"], ["AC1", "AC2", "E1.C1"])
        self.assertEqual(result["missing_anchors"], ["AC2"])
        self.assertEqual([i["term"] for i in result["inventions"]], ["marketplace", "comprador/vendedor"])
        self.assertEqual([c["text"] for c in result["unsupported_checks"]], ["✅ Los KPIs están documentados."])
        self.assertEqual(result["open_questions"],
                         ["¿Se incorpora la etapa de plan a la máquina de estados?", "¿Qué North Star define el owner?"])
        self.assertIn("AC2", result["corrections_to_paste"])
        self.assertIn("regla 4", result["corrections_to_paste"])

    def test_preamble_and_negations_are_not_inventions(self):
        result = pbaudit.audit(setup(chat=pack.PREAMBLE + "\nJose: no hay API Gateway y no es Okta.\n"), "prd")
        self.assertEqual(result["inventions"], [])

    def test_terms_in_context_pack_are_allowed(self):
        project = setup(context="- C1: IRIS es un marketplace interno con comprador y vendedor [MEDIDO] (fuente: README.md)\n")
        self.assertEqual(pbaudit.audit(project, "prd")["inventions"], [])

    def test_clean_chat_is_approved_without_corrections(self):
        chat = "Product Brain: llega al 100%\n- AC1: x\n- AC2: y\n- E1.C1: z\n"
        result = pbaudit.audit(setup(chat=chat), "prd")
        self.assertEqual((result["verdict"], result["corrections_to_paste"]), ("approved", ""))

    def test_missing_chat_raises_and_write_audit(self):
        project = make_project()
        with self.assertRaises(FileNotFoundError):
            pbaudit.audit(project, "rfc")
        result = pbaudit.audit(setup(), "prd")
        path = pbaudit.write_audit(make_project(), result)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["doc"], "prd")


if __name__ == "__main__":
    unittest.main()
```

Agregar a `tests/test_cli.py`:

```python
class PbchatAuditCommandTest(unittest.TestCase):
    def test_audit_codes_and_file(self):
        project = make_project()
        write(project, "wow/pb/chats/prd.md", "llega al 100%\n✅ Todo listo.\n")
        code, out, _ = run_cli(["pbchat", "audit", "prd", "--project", str(project)])
        self.assertEqual(code, 1)
        self.assertIn("verdict: changes_required", out)
        self.assertTrue((project / "wow/pb/chats/prd.audit.json").is_file())
        self.assertEqual(run_cli(["pbchat", "audit", "rfc", "--project", str(project)])[0], 2)
        self.assertEqual(run_cli(["pbchat", "audit", "../x", "--project", str(project)])[0], 2)
```

- [ ] **Step 3: Correr y verificar que falla** — ERROR `No module named 'pbaudit'`.

- [ ] **Step 4: Implementar `wow/pbaudit.py` y el subcomando**

```python
"""Audit a local copy of a Product Brain chat against its packet and the context pack (spec 9.3).

Corrections are Spanish on purpose: they are pasted back into the Product Brain chat.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional

import pack
from sources import pbchat

KNOWN_INVENTIONS = [
    ("marketplace", r"\bmarketplace\b"),
    ("comprador/vendedor", r"\bcomprador(?:es)?\b|\bvendedor(?:es)?\b"),
    ("API Gateway", r"\bapi[ -]?gateway\b"),
    ("Okta", r"\bokta\b"),
    ("OAuth", r"\boauth\b"),
    ("SLA", r"\bSLAs?\b"),
]
_NEGATION_RE = re.compile(r"\b(no hay|no es|no existe|no usa|inexistente|sin)\b", re.IGNORECASE)
_CHECK_RE = re.compile(r"[✅✔]")
_CITATION_RE = re.compile(r"\(|fuente|source|secci[oó]n|§", re.IGNORECASE)
_COMPLETION_RE = re.compile(r"(?:llega al|documento al|completitud[^0-9\n]{0,20})\s*(\d{1,3})\s*%", re.IGNORECASE)
_ITEM_RE = re.compile(r"^\s*(?:\d+[.)]|[-*])\s+(.+?)\s*$")


def open_questions(text: str) -> List[str]:
    lines = text.splitlines()
    heads = [i for i, line in enumerate(lines) if "preguntas abiertas" in line.lower() and len(line) < 80]
    if not heads:
        return []
    items: List[str] = []
    for line in lines[heads[-1] + 1:]:
        if not line.strip():
            continue
        item = _ITEM_RE.match(line)
        if item:
            items.append(item.group(1))
        elif line[:1] in (" ", "\t") and items:
            items[-1] = f"{items[-1]} {line.strip()}"
        else:
            break
    return items


def _allowed_text(project: Path, doc: str) -> str:
    parts = []
    packet = project / "wow" / "pb" / f"{doc}.md"
    if packet.is_file():
        parts.append(packet.read_text(encoding="utf-8"))
    for path in sorted((project / "wow" / "context-pack").glob("*.md")):
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _corrections(missing: List[str], inventions: List[dict], unsupported: List[dict]) -> str:
    if not (missing or inventions or unsupported):
        return ""
    lines = ["Correcciones (pegalas en el chat de Product Brain):"]
    lines += [f"- Conservá el criterio {anchor} tal como venía en el paquete (regla 6)." for anchor in missing]
    lines += [f"- Quitá «{i['term']}» (línea {i['line']}): no figura en el material (regla 4). "
              f"Si es una decisión pendiente, movela a Preguntas abiertas." for i in inventions]
    lines += [f"- El ítem «{c['text']}» figura como cumplido sin citar dónde se cumple (regla 7): "
              f"citá la sección o marcalo como pendiente." for c in unsupported]
    return "\n".join(lines)


def audit(project: Path, doc: str, extra_inventions: Optional[List[dict]] = None) -> dict:
    chat_path = project / "wow" / "pb" / "chats" / f"{doc}.md"
    if not chat_path.is_file():
        raise FileNotFoundError(chat_path)
    text = chat_path.read_text(encoding="utf-8")
    preamble = {line.strip() for line in pack.PREAMBLE.splitlines() if line.strip()}
    lines = [(n, line) for n, line in enumerate(text.splitlines(), 1) if line.strip() not in preamble]
    parsed = pbchat.parse_chat("\n".join(line for _, line in lines))

    packet = project / "wow" / "pb" / f"{doc}.md"
    expected = sorted(set(pbchat.ANCHOR_RE.findall(packet.read_text(encoding="utf-8")))) if packet.is_file() else []
    missing = sorted(set(expected) - set(parsed["anchors"]))

    allowed = _allowed_text(project, doc)
    inventions: List[dict] = []
    for term, pattern in KNOWN_INVENTIONS:
        regex = re.compile(pattern, re.IGNORECASE)
        if regex.search(allowed):
            continue
        for number, line in lines:
            if regex.search(line) and not _NEGATION_RE.search(line):
                inventions.append({"term": term, "line": number, "text": line.strip()[:160], "source": "known-list"})
                break
    inventions += list(extra_inventions or [])

    unsupported = [{"line": n, "text": line.strip()[:160]} for n, line in lines
                   if _CHECK_RE.search(line) and not _CITATION_RE.search(line)]
    percents = [int(m) for m in _COMPLETION_RE.findall(text) if int(m) <= 100]
    verdict = "approved" if not (missing or inventions or unsupported) else "changes_required"
    return {"schema_version": 1, "doc": doc, "verdict": verdict, "closed": parsed["closed"],
            "completion_pct": percents[-1] if percents else None, "open_questions": open_questions(text),
            "expected_anchors": expected, "missing_anchors": missing, "unsupported_checks": unsupported,
            "inventions": inventions, "corrections_to_paste": _corrections(missing, inventions, unsupported)}


def write_audit(project: Path, result: dict) -> Path:
    path = project / "wow" / "pb" / "chats" / f"{result['doc']}.audit.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
```

En `wow/cli.py`: `import pbaudit`, más:

```python
def _cmd_pbchat_audit(args) -> int:
    project = _project(args)
    if not review_mod.safe_ref(args.doc):
        sys.stderr.write(f"wow: unsafe document name {args.doc!r}\n")
        return exitcodes.CANNOT_EVALUATE
    try:
        result = pbaudit.audit(project, args.doc)
    except FileNotFoundError:
        sys.stderr.write(f"wow: wow/pb/chats/{args.doc}.md not found; copy the Product Brain chat there first\n")
        return exitcodes.CANNOT_EVALUATE
    pbaudit.write_audit(project, result)
    print(f"verdict: {result['verdict']}")
    if result["corrections_to_paste"]:
        print(result["corrections_to_paste"])
    return exitcodes.OK if result["verdict"] == "approved" else exitcodes.FINDINGS
```

```python
    pc = sub.add_parser("pbchat", help="audit local copies of Product Brain chats")
    pcsub = pc.add_subparsers(dest="pbchat_command", parser_class=_Parser)
    pa = with_project(pcsub.add_parser("audit"))
    pa.add_argument("doc", help="prd | rfc | epic-E<n>")
    pa.set_defaults(handler=_cmd_pbchat_audit)
```

- [ ] **Step 5: Correr ambas suites** — exit 0.

- [ ] **Step 6: Commit (solo con ambas suites en 0)**

```bash
python3 -m unittest discover -s tests && /usr/bin/python3 -m unittest discover -s tests && \
git add wow/pbaudit.py wow/cli.py schemas/pbchat-audit.schema.json tests/test_pbaudit.py tests/test_cli.py && \
git commit -m "feat(pb-audit): audit Product Brain chat copies against packet and context pack"
```

---

### Task 3: auditoría profunda con revisor independiente (`--deep`)

**Files:**
- Modify: `wow/pbaudit.py`, `wow/cli.py`, `tests/test_pbaudit.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `reviewers.pick_reviewer/run_backend/NoReviewer/ReviewerFailed` (Plan 2), `review.parse_verdict/ReviewOutputError` (Plan 2).
- Produces:
  - `pbaudit.build_deep_prompt(project: Path, doc: str) -> str` (contexto = paquete + context pack; chat numerado sin preámbulo)
  - `pbaudit.parse_inventions(text: str) -> list[dict]` — líneas `INVENTION <n> — <cita> — <motivo>` → `{"term": cita[:80], "line": n, "text": motivo, "source": "reviewer"}`. Sin `VERDICT:` → `review.ReviewOutputError`.
  - `pbaudit.deep_inventions(project: Path, doc: str, cfg: dict, runner=subprocess.run, which=shutil.which) -> list[dict]`
  - CLI: `wow pbchat audit DOC --deep` agrega los inventos del revisor. Sin revisor, falla del revisor o salida sin `VERDICT:` → `2` (no escribe el audit).

- [ ] **Step 1: Escribir el test que falla**

Agregar a `tests/test_pbaudit.py`:

```python
class DeepAuditTest(unittest.TestCase):
    def test_parse_inventions_and_verdict_required(self):
        text = "VERDICT: CHANGES_REQUIRED\nINVENTION 12 — North Star del 30% — no figura en el contexto\n"
        self.assertEqual(pbaudit.parse_inventions(text), [
            {"term": "North Star del 30%", "line": 12, "text": "no figura en el contexto", "source": "reviewer"}])
        import review
        with self.assertRaises(review.ReviewOutputError):
            pbaudit.parse_inventions("no verdict here")

    def test_prompt_excludes_preamble_and_numbers_chat(self):
        prompt = pbaudit.build_deep_prompt(setup(), "prd")
        self.assertNotIn("Reglas para este documento", prompt.split("--- CHAT")[1])
        self.assertIn("marketplace", prompt)
        self.assertRegex(prompt, r"\n\d+: ")
```

Agregar a `tests/test_cli.py`:

```python
class PbchatDeepAuditCommandTest(unittest.TestCase):
    def test_deep_audit_adds_reviewer_inventions(self):
        project, _ = _review_project("VERDICT: CHANGES_REQUIRED\nINVENTION 1 — SLA 99.9% — no está en el contexto\n")
        write(project, "wow/pb/chats/prd.md", "llega al 100%\n")
        code, out, _ = run_cli(["pbchat", "audit", "prd", "--deep", "--project", str(project)])
        self.assertEqual(code, 1)
        saved = _json.loads((project / "wow/pb/chats/prd.audit.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["inventions"][0]["source"], "reviewer")

    def test_deep_audit_without_reviewer_exits_2(self):
        project, _ = _review_project("VERDICT: APPROVED\n")
        write(project, ".wow/config.json", _json.dumps({"reviewers": ["claude"]}))
        write(project, "wow/pb/chats/prd.md", "llega al 100%\n")
        self.assertEqual(run_cli(["pbchat", "audit", "prd", "--deep", "--project", str(project)])[0], 2)
        self.assertFalse((project / "wow/pb/chats/prd.audit.json").exists())
```

- [ ] **Step 2: Correr y verificar que falla** — `AttributeError: module 'pbaudit' has no attribute 'parse_inventions'` y `unrecognized arguments: --deep`.

- [ ] **Step 3: Implementar**

Agregar a `wow/pbaudit.py` (imports `shutil`, `subprocess`, `import review`, `import reviewers`):

```python
_INVENTION_RE = re.compile(r"^\s*INVENTION\s+(\d+)\s+[—–-]+\s*(.+?)\s+[—–-]+\s*(.+?)\s*$")

_DEEP_PROMPT = """You are an independent auditor. CONTEXT is the only source of truth.
List every statement in CHAT that asserts a fact, component, provider, number, owner or deadline
that does not appear in CONTEXT. Ignore statements that only repeat CONTEXT or ask questions.

Output format, exactly, with no other text:
VERDICT: APPROVED | CHANGES_REQUIRED
INVENTION <chat-line-number> — <short quote> — <why it is not supported>

--- CONTEXT ---
{context}

--- CHAT (numbered) ---
{chat}
"""


def build_deep_prompt(project: Path, doc: str) -> str:
    text = (project / "wow" / "pb" / "chats" / f"{doc}.md").read_text(encoding="utf-8")
    preamble = {line.strip() for line in pack.PREAMBLE.splitlines() if line.strip()}
    numbered = "\n".join(f"{n}: {line}" for n, line in enumerate(text.splitlines(), 1)
                         if line.strip() not in preamble)
    return _DEEP_PROMPT.format(context=_allowed_text(project, doc) or "(empty)", chat=numbered)


def parse_inventions(text: str) -> List[dict]:
    if review.parse_verdict(text)["verdict"] is None:
        raise review.ReviewOutputError("reviewer output has no 'VERDICT:' line")
    found = []
    for line in text.splitlines():
        match = _INVENTION_RE.match(line)
        if match:
            found.append({"term": match.group(2)[:80], "line": int(match.group(1)),
                          "text": match.group(3), "source": "reviewer"})
    return found


def deep_inventions(project: Path, doc: str, cfg: dict, runner=subprocess.run, which=shutil.which) -> List[dict]:
    _, spec = reviewers.pick_reviewer(cfg, project, runner, which)
    return parse_inventions(reviewers.run_backend(spec, build_deep_prompt(project, doc), project, runner, which))
```

En `wow/cli.py`, reemplazar el cuerpo de `_cmd_pbchat_audit` desde `try:` por:

```python
    extra = []
    if args.deep:
        try:
            extra = pbaudit.deep_inventions(project, args.doc, config.load_config(project))
        except FileNotFoundError:
            sys.stderr.write(f"wow: wow/pb/chats/{args.doc}.md not found or reviewer CLI missing\n")
            return exitcodes.CANNOT_EVALUATE
        except (reviewers.NoReviewer, reviewers.ReviewerFailed, review_mod.ReviewOutputError,
                config.ConfigError, OSError) as exc:
            sys.stderr.write(f"wow: deep audit failed: {exc}\n")
            return exitcodes.CANNOT_EVALUATE
    try:
        result = pbaudit.audit(project, args.doc, extra_inventions=extra)
    except FileNotFoundError:
        sys.stderr.write(f"wow: wow/pb/chats/{args.doc}.md not found; copy the Product Brain chat there first\n")
        return exitcodes.CANNOT_EVALUATE
    pbaudit.write_audit(project, result)
    print(f"verdict: {result['verdict']}")
    if result["corrections_to_paste"]:
        print(result["corrections_to_paste"])
    return exitcodes.OK if result["verdict"] == "approved" else exitcodes.FINDINGS
```

y en el parser: `pa.add_argument("--deep", action="store_true", help="also ask an independent reviewer")`.

- [ ] **Step 4: Correr ambas suites** — exit 0.

- [ ] **Step 5: Commit (solo con ambas suites en 0)**

```bash
python3 -m unittest discover -s tests && /usr/bin/python3 -m unittest discover -s tests && \
git add wow/pbaudit.py wow/cli.py tests/test_pbaudit.py tests/test_cli.py && \
git commit -m "feat(pb-audit): add a deep audit through an independent reviewer"
```

---

### Task 4: `contextpack.py` y `wow context scan|check`

**Files:**
- Create: `wow/contextpack.py`, `tests/test_contextpack.py`
- Modify: `wow/sources/repo.py`, `wow/cli.py`, `tests/test_repo.py`, `tests/test_cli.py`

**Interfaces:**
- Produces:
  - `repo.submodule_paths(project: Path) -> list[str]` (valores `path = …` de `.gitmodules`, en orden)
  - `contextpack.CLAIM_FILES = ("facts.md", "metrics.md", "decisions.md", "contracts.md")`
  - `contextpack.children(project: Path) -> list[Path]` (submódulos existentes + carpetas de primer nivel con `.git`, sin `wow`, `.wow`, `specs`, `.spec-kit`, `node_modules`)
  - `contextpack.scan(project: Path) -> dict` → `{"children": [str], "docs": [str], "created": [str]}`; escribe `wow/context-pack/inventory.md` (se regenera siempre) y crea los esqueletos faltantes de `CLAIM_FILES` y `pending-owner.md` (nunca pisa uno existente).
  - `contextpack.check(project: Path) -> list[str]`: valida cada viñeta `- …` de `CLAIM_FILES` con el formato `- C<n>: <afirmación> [MEDIDO|ESTIMACIÓN|SIN DEFINIR] (fuente: ruta[:línea])`. La fuente es obligatoria salvo con `[SIN DEFINIR]`, debe existir relativa al proyecto y los ids son únicos entre archivos. Archivo faltante también es hallazgo.
  - CLI: `wow context scan` imprime `children`, `docs`, `created` y sale `0`; `wow context check` imprime un hallazgo por línea, `1` si hay, `0` si no.

- [ ] **Step 1: Escribir el test que falla**

`tests/test_contextpack.py`:

```python
from __future__ import annotations

import unittest

from helpers import make_project, write
import contextpack


class ScanTest(unittest.TestCase):
    def test_scan_inventories_children_docs_and_creates_skeletons_once(self):
        project = make_project()
        write(project, ".gitmodules", '[submodule "api"]\n\tpath = backend-api\n\turl = x\n')
        write(project, "backend-api/.git", "gitdir: ../.git/modules/api\n")
        write(project, "backend-api/README.md", "# API\n")
        write(project, "backend-api/docs/adr/0001-dynamo.md", "# ADR\n")
        write(project, "mfe/.git/HEAD", "ref: refs/heads/main\n")
        write(project, "wow/context-pack/facts.md", "# mine\n")
        result = contextpack.scan(project)
        self.assertEqual(result["children"], ["backend-api", "mfe"])
        self.assertIn("backend-api/docs/adr/0001-dynamo.md", result["docs"])
        self.assertNotIn("wow/context-pack/facts.md", result["created"])
        self.assertIn("wow/context-pack/pending-owner.md", result["created"])
        self.assertEqual((project / "wow/context-pack/facts.md").read_text(encoding="utf-8"), "# mine\n")
        self.assertIn("backend-api", (project / "wow/context-pack/inventory.md").read_text(encoding="utf-8"))


class CheckTest(unittest.TestCase):
    def test_check_reports_each_problem(self):
        project = make_project()
        write(project, "README.md", "x")
        contextpack.scan(project)
        write(project, "wow/context-pack/facts.md",
              "# Hechos\n"
              "- C1: auth contra Nucleus [MEDIDO] (fuente: README.md:3)\n"
              "- C2: sin tag (fuente: README.md)\n"
              "- C3: sin fuente [MEDIDO]\n"
              "- C4: fuente rota [ESTIMACIÓN] (fuente: missing.py:1)\n"
              "- C5: pendiente [SIN DEFINIR]\n"
              "- texto suelto\n")
        write(project, "wow/context-pack/metrics.md", "- C1: duplicado [MEDIDO] (source: README.md)\n")
        findings = contextpack.check(project)
        self.assertEqual(findings, [
            "facts.md:3: C2 needs a tag [MEDIDO], [ESTIMACIÓN] or [SIN DEFINIR]",
            "facts.md:4: C3 needs a source (fuente: path:line)",
            "facts.md:5: C4 source not found: missing.py",
            "facts.md:7: not a claim (expected '- C<n>: … [TAG] (fuente: …)')",
            "metrics.md:1: duplicate id C1 (first at facts.md:2)",
        ])

    def test_missing_files_are_findings(self):
        self.assertEqual(len(contextpack.check(make_project())), 4)
```

Agregar a `tests/test_repo.py`:

```python
class SubmoduleTest(unittest.TestCase):
    def test_submodule_paths(self):
        project = make_project()
        write(project, ".gitmodules", '[submodule "a"]\n\tpath = mfe-x\n[submodule "b"]\n  path = bff-x\n')
        self.assertEqual(repo.submodule_paths(project), ["mfe-x", "bff-x"])
        self.assertEqual(repo.submodule_paths(make_project()), [])
```

Agregar a `tests/test_cli.py`:

```python
class ContextCommandTest(unittest.TestCase):
    def test_scan_then_check_codes(self):
        project = make_project()
        self.assertEqual(run_cli(["context", "scan", "--project", str(project)])[0], 0)
        self.assertEqual(run_cli(["context", "check", "--project", str(project)])[0], 0)
        write(project, "wow/context-pack/facts.md", "- C1: x [MEDIDO]\n")
        code, out, _ = run_cli(["context", "check", "--project", str(project)])
        self.assertEqual(code, 1)
        self.assertIn("C1 needs a source", out)
```

- [ ] **Step 2: Correr y verificar que falla** — ERROR `No module named 'contextpack'`.

- [ ] **Step 3: Implementar**

`wow/sources/repo.py`, agregar:

```python
_SUBMODULE_RE = re.compile(r"^\s*path\s*=\s*(.+?)\s*$")


def submodule_paths(project: Path) -> List[str]:
    path = project / ".gitmodules"
    if not path.is_file():
        return []
    return [m.group(1) for m in map(_SUBMODULE_RE.match, path.read_text(encoding="utf-8").splitlines()) if m]
```

`wow/contextpack.py`:

```python
"""Context pack: inventory of repos and docs, and validation of tagged claims (spec 6.2 phase 0)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from sources import repo

CLAIM_FILES = ("facts.md", "metrics.md", "decisions.md", "contracts.md")
_SKIP = {"wow", ".wow", "specs", ".spec-kit", "node_modules", ".git"}
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
    found = {project / p for p in repo.submodule_paths(project) if (project / p).exists()}
    for item in project.iterdir():
        if item.is_dir() and item.name not in _SKIP and (item / ".git").exists():
            found.add(item)
    return sorted(found, key=lambda p: p.name)


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
    return {"children": [k.name for k in kids], "docs": docs, "created": created}


def check(project: Path) -> List[str]:
    findings: List[str] = []
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
                if not (project / rel).exists():
                    findings.append(f"{name}:{number}: {claim_id} source not found: {rel}")
    return findings
```

En `wow/cli.py`: `import contextpack`, más:

```python
def _cmd_context_scan(args) -> int:
    result = contextpack.scan(_project(args))
    print(f"children: {', '.join(result['children']) or '-'}")
    print(f"docs: {len(result['docs'])}")
    for path in result["created"]:
        print(f"created {path}")
    return exitcodes.OK


def _cmd_context_check(args) -> int:
    findings = contextpack.check(_project(args))
    for line in findings:
        print(line)
    return exitcodes.FINDINGS if findings else exitcodes.OK
```

```python
    cx = sub.add_parser("context", help="inventory and validate the context pack")
    cxsub = cx.add_subparsers(dest="context_command", parser_class=_Parser)
    with_project(cxsub.add_parser("scan")).set_defaults(handler=_cmd_context_scan)
    with_project(cxsub.add_parser("check")).set_defaults(handler=_cmd_context_check)
```

Nota: el test `test_check_reports_each_problem` espera que el duplicado de `metrics.md` diga `first at facts.md:2` (la línea 2 de `facts.md` es `C1`).

- [ ] **Step 4: Correr ambas suites** — exit 0.

- [ ] **Step 5: Commit (solo con ambas suites en 0)**

```bash
python3 -m unittest discover -s tests && /usr/bin/python3 -m unittest discover -s tests && \
git add wow/contextpack.py wow/sources/repo.py wow/cli.py tests/test_contextpack.py tests/test_repo.py tests/test_cli.py && \
git commit -m "feat(context): scan repos and docs and check tagged claims"
```

---

### Task 5: fuente GitHub y links en el snapshot

**Files:**
- Create: `wow/sources/github.py`, `wow/links.py`, `tests/test_github.py`, `tests/test_links.py`
- Modify: `wow/cli.py`, `wow/config.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `repo.submodule_paths` (Task 4), `speckit.features` (Plan 1), `SourceUnavailable` (Plan 1).
- Produces:
  - `github.KEY_RE = re.compile(r"\b[A-Z][A-Z0-9]*-\d+\b")`
  - `github.checks_state(rollup: list | None) -> str` ∈ `{"passing", "failing", "pending", "none"}`
  - `github.pull_requests(repo_dir: Path, runner=subprocess.run, which=shutil.which) -> list[dict]` → `[{"repo", "number", "title", "state", "url", "branch", "checks"}]`. Ejecuta `gh pr list --state all --limit 50 --json number,title,state,url,headRefName,statusCheckRollup` en `repo_dir` con timeout de 20 s. Sin `gh` → `SourceUnavailable("github: gh not installed")`; exit distinto de 0 o JSON inválido → `SourceUnavailable(f"github: gh pr list failed in {repo_dir.name}")` (sin stderr, que puede tener datos de la cuenta).
  - `github.link(prs: list, keys: set[str]) -> list[dict]` (PRs cuyo título o rama contiene alguna key)
  - `links.build_links(project: Path, state: dict, prs: list) -> dict` (copia de `state`): cada épica recibe `links = {"jira": jira_url, "prs": [...], "files": [...]}` (keys = key de la épica + keys de historias de su feature; files = `spec.md`, `plan.md`, `tasks.md` existentes de la feature + `wow/pb/epic-<id>.md`), y el plan recibe `links = {"files": [...]}` entre `wow/plan/PLAN.md`, `wow/plan/manifest.json`, `wow/pb/prd.md`, `wow/pb/rfc.md`, `wow/context-pack/facts.md` existentes.
  - `config.DEFAULTS["github"] = {"enabled": True}` (hoy no existe la clave). Los tests de CLI que corren `snapshot` la desactivan para no invocar `gh` real.
  - CLI `wow snapshot`: si `cfg["github"]["enabled"]` es falso → `sources.github = "disabled"`. Si no, lee PRs del proyecto y de cada submódulo existente; `sources.github` = `"ok"` si todos leyeron, `"partial: <errores>"` si alguno, el primer error si ninguno. Después aplica `links.build_links`.

- [ ] **Step 1: Escribir el test que falla**

`tests/test_github.py`:

```python
from __future__ import annotations

import json
import subprocess
import unittest

from helpers import make_project
from sources import SourceUnavailable, github

PRS = [{"number": 7, "title": "IRIS-41 curate endpoint", "state": "OPEN", "url": "https://gh/x/7",
        "headRefName": "feat/IRIS-41", "statusCheckRollup": [{"conclusion": "SUCCESS"}]},
       {"number": 8, "title": "chore: deps", "state": "MERGED", "url": "https://gh/x/8",
        "headRefName": "deps", "statusCheckRollup": [{"conclusion": "FAILURE"}]}]


def runner(stdout, code=0):
    return lambda argv, cwd=None, capture_output=None, text=None, timeout=None: \
        subprocess.CompletedProcess(argv, code, stdout, "token=secret")


class GithubTest(unittest.TestCase):
    def test_pull_requests_and_link(self):
        prs = github.pull_requests(make_project(), runner(json.dumps(PRS)), which=lambda n: "/bin/gh")
        self.assertEqual([(p["number"], p["checks"]) for p in prs], [(7, "passing"), (8, "failing")])
        self.assertEqual([p["number"] for p in github.link(prs, {"IRIS-41"})], [7])

    def test_unavailable_without_secrets(self):
        with self.assertRaises(SourceUnavailable):
            github.pull_requests(make_project(), runner("[]"), which=lambda n: None)
        with self.assertRaises(SourceUnavailable) as ctx:
            github.pull_requests(make_project(), runner("", code=1), which=lambda n: "/bin/gh")
        self.assertNotIn("secret", str(ctx.exception))

    def test_checks_state(self):
        self.assertEqual(github.checks_state(None), "none")
        self.assertEqual(github.checks_state([{"status": "IN_PROGRESS"}]), "pending")
        self.assertEqual(github.checks_state([{"state": "SUCCESS"}, {"conclusion": "SUCCESS"}]), "passing")
```

`tests/test_links.py`:

```python
from __future__ import annotations

import unittest

from helpers import make_project, write
import links


class LinksTest(unittest.TestCase):
    def test_epic_and_plan_links(self):
        project = make_project()
        write(project, "specs/001-x/spec.md", "**Jira Epic:** IRIS-40\n")
        write(project, "specs/001-x/tasks.md", "- [ ] T1 a\n  - jira: IRIS-41\n")
        write(project, "wow/pb/epic-E1.md", "x")
        write(project, "wow/plan/PLAN.md", "x")
        state = {"plan": {"id": "p"}, "epics": [{"id": "E1", "jira": "IRIS-40", "jira_url": "https://j/IRIS-40"},
                                                {"id": "E2", "jira": None, "jira_url": None}]}
        prs = [{"number": 7, "title": "IRIS-41 x", "branch": "b"}, {"number": 9, "title": "other", "branch": "c"}]
        out = links.build_links(project, state, prs)
        e1 = out["epics"][0]["links"]
        self.assertEqual(e1["jira"], "https://j/IRIS-40")
        self.assertEqual([p["number"] for p in e1["prs"]], [7])
        self.assertEqual(e1["files"], ["specs/001-x/spec.md", "specs/001-x/tasks.md", "wow/pb/epic-E1.md"])
        self.assertEqual(out["epics"][1]["links"], {"jira": None, "prs": [], "files": []})
        self.assertEqual(out["plan"]["links"], {"files": ["wow/plan/PLAN.md"]})
        self.assertNotIn("links", state["plan"])
```

En `tests/test_cli.py`, agregar `"github": {"enabled": False}` a la config que escriben `SnapshotCommandTest` y `UsageCommandTest` (junto a `"usage": …`), y este test:

```python
class SnapshotGithubDisabledTest(unittest.TestCase):
    def test_disabled_github_is_reported(self):
        project = make_project()
        write(project, ".wow/config.json", _json.dumps({"github": {"enabled": False},
                                                        "usage": {"claude_root": str(project / "c"),
                                                                  "codex_root": str(project / "x")}}))
        self.assertEqual(run_cli(["snapshot", "--project", str(project)])[0], 0)
        saved = _json.loads((project / "wow/progress.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["current"]["sources"]["github"], "disabled")
        self.assertIn("links", saved["current"]["plan"])
```

- [ ] **Step 2: Correr y verificar que falla** — ERROR `cannot import name 'github'` / `No module named 'links'`.

- [ ] **Step 3: Implementar**

`wow/sources/github.py`:

```python
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
    except (ValueError, OSError, subprocess.TimeoutExpired):
        raise SourceUnavailable(f"github: gh pr list failed in {repo_dir.name}")
    return [{"repo": repo_dir.name, "number": pr.get("number"), "title": pr.get("title", ""),
             "state": pr.get("state"), "url": pr.get("url"), "branch": pr.get("headRefName", ""),
             "checks": checks_state(pr.get("statusCheckRollup"))} for pr in data]


def link(prs: List[dict], keys: Set[str]) -> List[dict]:
    return [pr for pr in prs if keys & set(KEY_RE.findall(f"{pr.get('title', '')} {pr.get('branch', '')}"))]
```

Nota: `json.JSONDecodeError` hereda de `ValueError`, así que queda cubierto por el `except`.

`wow/links.py`:

```python
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
        packet = f"wow/pb/epic-{epic['id']}.md"
        if (project / packet).is_file() and key:
            files.append(packet)
        epic["links"] = {"jira": epic.get("jira_url"), "prs": github.link(prs, keys) if keys else [],
                         "files": files}
    result["plan"]["links"] = {"files": [p for p in _PLAN_FILES if (project / p).is_file()]}
    return result
```

Nota: el packet de una épica sin key de Jira no se lista, porque todavía no está exportada (en el test, E2 sale con `files: []`).

En `wow/cli.py`: `import links` y `from sources import SourceUnavailable, github, repo as repo_src`, más:

```python
def _github_prs(project: Path, cfg: dict):
    if not (cfg.get("github") or {}).get("enabled", True):
        return [], "disabled"
    prs, errors, ok = [], [], 0
    for directory in [project] + [project / p for p in repo_src.submodule_paths(project) if (project / p).exists()]:
        try:
            prs += github.pull_requests(directory)
            ok += 1
        except SourceUnavailable as exc:
            errors.append(str(exc))
    if not errors:
        return prs, "ok"
    return prs, ("partial: " + "; ".join(errors)) if ok else errors[0]
```

En `_cmd_snapshot`, después de `result = state_mod.compute_state(...)`:

```python
    prs, github_status = _github_prs(project, cfg)
    result["sources"]["github"] = github_status
    result = links.build_links(project, result, prs)
```

- [ ] **Step 4: Correr ambas suites** — exit 0.

- [ ] **Step 5: Commit (solo con ambas suites en 0)**

```bash
python3 -m unittest discover -s tests && /usr/bin/python3 -m unittest discover -s tests && \
git add wow/sources/github.py wow/links.py wow/cli.py wow/config.py tests/test_github.py tests/test_links.py tests/test_cli.py && \
git commit -m "feat(snapshot): link epics to Jira, GitHub pull requests and repo files"
```

---

### Task 6: `wow plan guard`, las cuatro skills y README

**Files:**
- Create: `skills/wow-plan/SKILL.md`, `skills/wow-pack/SKILL.md`, `skills/wow-pb-audit/SKILL.md`, `skills/wow-context/SKILL.md`
- Modify: `wow/cli.py`, `tests/test_cli.py`, `README.md`

**Interfaces:**
- Consumes: `manifest.ensure_writable/FrozenError` (Plan 1).
- Produces:
  - CLI `wow plan guard [--reopen REASON] [--project DIR]`: manifiesto ausente → `2`; congelado sin motivo → imprime el mensaje de `FrozenError` y `1`; si no, imprime `writable` y `0`.
  - Las 7 skills cumplen el contrato: `name` igual a su carpeta, ≤ 80 líneas, y todo `` `wow <sub>`` citado existe como subcomando del CLI.

- [ ] **Step 1: Escribir el test que falla**

Agregar a `tests/test_cli.py`:

```python
import argparse as _argparse  # noqa: E402


class PlanGuardCommandTest(unittest.TestCase):
    def test_guard_codes(self):
        project = make_project()
        self.assertEqual(run_cli(["plan", "guard", "--project", str(project)])[0], 2)
        _manifest.save(project, valid_doc())
        self.assertEqual(run_cli(["plan", "guard", "--project", str(project)])[0], 0)
        run_cli(["plan", "freeze", "--epics", "E1=IRIS-40", "--project", str(project)])
        code, out, _ = run_cli(["plan", "guard", "--project", str(project)])
        self.assertEqual(code, 1)
        self.assertIn("/spec-kit.amend", out)
        self.assertEqual(run_cli(["plan", "guard", "--reopen", "scope", "--project", str(project)])[0], 0)


class AllSkillsContractTest(unittest.TestCase):
    def test_every_skill_is_small_named_and_cites_real_commands(self):
        import cli
        parser = cli.build_parser()
        subs = next(a for a in parser._actions if isinstance(a, _argparse._SubParsersAction)).choices
        names = []
        for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
            text = path.read_text(encoding="utf-8")
            front = _re.match(r"^---\nname: (.+)\ndescription: (.+)\n---\n", text)
            self.assertIsNotNone(front, path)
            self.assertEqual(front.group(1), path.parent.name)
            self.assertLessEqual(len(text.splitlines()), 80, path)
            for command in _re.findall(r"`wow ([a-z-]+)", text):
                self.assertIn(command, subs, f"{path}: wow {command}")
            names.append(path.parent.name)
        self.assertEqual(names, ["wow-context", "wow-guide", "wow-pack", "wow-pb-audit", "wow-plan",
                                 "wow-review", "wow-sk-prep"])
```

- [ ] **Step 2: Correr y verificar que falla** — `invalid choice: 'guard'` y la lista de skills incompleta.

- [ ] **Step 3: Implementar `wow plan guard`**

```python
def _cmd_plan_guard(args) -> int:
    try:
        doc = manifest.load(_project(args))
    except manifest.ManifestError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    try:
        manifest.ensure_writable(doc, args.reopen)
    except manifest.FrozenError as exc:
        print(str(exc))
        return exitcodes.FINDINGS
    print("writable")
    return exitcodes.OK
```

En `build_parser`, dentro del bloque `plan`:

```python
    gd = with_project(psub.add_parser("guard"))
    gd.add_argument("--reopen", default=None, help="reason to edit a frozen manifest")
    gd.set_defaults(handler=_cmd_plan_guard)
```

- [ ] **Step 4: Escribir las skills**

`skills/wow-plan/SKILL.md`:

```markdown
---
name: wow-plan
description: Turn an initiative into a Brief and an upstream kanban (epics, tasks with acceptance criteria, estimates, priority, labels) in wow/plan/, ready for readiness review and Product Brain packets. Use when starting an initiative, when the user says "plan this", or when wow-guide recommends wow-plan.
---

# wow-plan

## Steps

1. Run `wow plan guard`. Exit 1 means the manifest is frozen: stop and explain the scope-change path
   (Product Brain Artifact Engine + /spec-kit.amend). Exit 2 means there is no manifest yet:
   run `wow plan init <NNNN-name> --title "<title>"`.
2. Clarify with the user ONE question at a time (use a brainstorming skill if the host has one).
   Record answers in `wow/plan/PLAN.md` under `## Brief` as bullets:
   `- Goal:`, `- Decisions: D1 … · D2 …`, `- Constraints:`, `- Non-goals:`, `- Open questions:`.
   Owner decisions you cannot get go to Open questions; never invent them.
3. Do not decompose while a blocking open question remains.
4. Edit `wow/plan/manifest.json`: epics with `done_when` ("E1.C1: …"), tasks with `acceptance`
   ("AC1: …"), `depends_on`, `subtasks`, `estimate` (story points), `priority` (high|medium|low), `labels`.
5. Run `wow manifest validate` and `wow manifest lint` until both exit 0.
6. Hand off to readiness: `wow review --set readiness --ref plan`. Never set `plan.readiness` yourself.

## Rules

- Acceptance criteria must be verifiable; vague ones fail readiness R1.
- Keep task ids stable once packets exist: renaming breaks the AC anchors used in later reviews.
```

`skills/wow-pack/SKILL.md`:

```markdown
---
name: wow-pack
description: Generate the Product Brain packets (PRD, RFC and one per epic) from the upstream manifest and Brief, then fill only their narrative sections from the context pack. Use before any Product Brain chat or when wow-guide recommends `wow pack`.
---

# wow-pack

## Steps

1. Run `wow pack prd`, `wow pack rfc` and `wow pack epic --id E<n>` for each epic.
   Exit 1 means the packet already exists: only use `--force` if you accept losing filled sections.
2. Fill ONLY the `<!-- wow:fill … -->` markers, using facts from `wow/context-pack/` with their tags
   [MEDIDO], [ESTIMACIÓN] or [SIN DEFINIR]. Never edit generated lines (stories, AC ids, story points,
   the manifest-hash header): regenerate instead.
3. RFC: write it as engineering manager / tech lead, with discarded alternatives and their reasons.
   If you cite context claims by id (C1, C2…), verify the RFC with
   `wow review --set claims --ref rfc --doc wow/pb/rfc.md`.
4. Tell the user to paste `wow/pb/preamble.md` first, then the packet, using model 3.1 Pro.

## Rules

- Anything not in the context pack is [SIN DEFINIR], never a plausible guess.
- Packets are Spanish: they are pasted into Product Brain.
```

`skills/wow-pb-audit/SKILL.md`:

```markdown
---
name: wow-pb-audit
description: Audit the local copy of a Product Brain chat (PRD, RFC or epic) against its packet and the context pack, and produce corrections to paste back into the chat. Use after each Product Brain chat, or when wow-guide recommends wow-pb-audit.
---

# wow-pb-audit

## Steps

1. The user copies the full chat into `wow/pb/chats/<doc>.md` (`prd`, `rfc` or `epic-E<n>`).
2. Run `wow pbchat audit <doc> --deep`. The deep mode asks an independent reviewer (Codex) for
   unsupported statements; without a reviewer it exits 2, then run it without `--deep` and say so.
3. Exit 1: show the corrections block verbatim so the user pastes it into Product Brain, then wait
   for the user to update the chat copy and audit again.
4. Exit 0: the chat is approved; the audit file `wow/pb/chats/<doc>.audit.json` records it.

## Rules

- Never edit an `.audit.json` by hand and never mark a chat approved yourself.
- A closed chat (100%) with a failing audit is still not done: Product Brain checklists are not evidence.
```

`skills/wow-context/SKILL.md`:

```markdown
---
name: wow-context
description: Build the context pack (facts, metrics, decisions, contracts, owner decisions) from the real repositories, with every claim tagged and sourced, then verify it with an independent reviewer. Use at the start of an initiative, when the repo changed, or when wow-guide recommends wow-context.
---

# wow-context

## Steps

1. Run `wow context scan`: it inventories child repos and docs into `wow/context-pack/inventory.md`
   and creates missing skeleton files.
2. Read the code and docs it lists. Write claims, one per line, in facts.md, metrics.md,
   decisions.md and contracts.md:
   `- C<n>: <claim> [MEDIDO|ESTIMACIÓN|SIN DEFINIR] (fuente: path:line)`.
3. List owner decisions in `pending-owner.md` as `- [ ] <decision>`; the user marks them `[x]`.
4. Run `wow context check` until it exits 0.
5. Verify the facts with an independent reviewer:
   `wow review --set claims --ref facts --doc wow/context-pack/facts.md --repo <repo>`.

## Rules

- A claim without a source is [SIN DEFINIR] or it is removed.
- Measured numbers keep their measurement context (where, when, how).
```

- [ ] **Step 5: Actualizar `README.md`** (agregar al bloque de uso)

```bash
wow context scan | wow context check                        # context pack con afirmaciones etiquetadas
wow pack prd | wow pack rfc | wow pack epic --id E1         # paquetes para Product Brain
wow pbchat audit prd --deep                                 # auditar la copia del chat de PB
wow plan guard                                              # ¿se puede editar el manifiesto?
```

- [ ] **Step 6: Correr ambas suites** — exit 0.

- [ ] **Step 7: Commit (solo con ambas suites en 0)**

```bash
python3 -m unittest discover -s tests && /usr/bin/python3 -m unittest discover -s tests && \
git add wow/cli.py tests/test_cli.py skills/ README.md && \
git commit -m "feat(skills): add plan guard and the wow-plan, wow-pack, wow-pb-audit and wow-context skills"
```

---

## Fuera de este plan

- **Plan 4:** `dashboard/wow-dashboard.html` (en inglés, offline, con los tres `progress.json` de ejemplo). Nota del Plan 2: los `tokens_in` de Claude excluyen la caché; el panel de consumo debe sumar `cache_read` y `cache_write` para mostrar el contexto real.
