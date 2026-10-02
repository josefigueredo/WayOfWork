# WayOfWork · Plan 5: alineación con Product Brain real — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que lo que `wow` le entrega a Product Brain llegue al 100% en el primer pegado sin inventar nada:
- paquetes PRD, RFC y épica con la forma exacta de las plantillas reales de PB;
- predicción local del % con las mismas reglas que el backend de PB;
- modo greenfield/brownfield;
- un manifiesto que lleve los datos que PB exige por historia;
- una auditoría que no se deje engañar por las secciones fijas de la plantilla.

**Architecture:**
- Las plantillas de PB se copian al repo (`wow/templates/`), verificadas por hash contra `reference/product-brain/upstream/`.
- `pbtemplate.py` extrae campos y grupos con las mismas expresiones regulares que `detector.ts` y `field-groups.ts`.
- `pbcompletion.py` porta `completion.ts` y `open-questions-validation.ts` para predecir el %, y valida enums y formatos de la épica.
- `pack.py` renderiza desde la plantilla y deja `{{campo}}` donde falta el dato: es el mismo marcador que PB cuenta como vacío. Opus completa esos campos siguiendo los prompts de `skills/wow-pack/references/`.

**Tech Stack:** Python 3.9+ stdlib; JS vanilla en el dashboard.

**Spec:** `docs/superpowers/specs/2026-10-01-wayofwork-design.md`.

**Evidencia de PB:** `reference/product-brain/README.md`, sobre el commit `9b19a89` de `josefigueredo/acme-agent`, leído el 2026-10-02.

## Global Constraints

- **Compatibilidad y dependencias:** Python 3.9 (`/usr/bin/python3`) y Homebrew; `from __future__ import annotations`; solo stdlib; `unittest`, sin red.
- **Idiomas:** código, CLI y `SKILL.md` en inglés; los prompts de referencia con instrucciones en inglés y salida en castellano. Los paquetes y las plantillas de PB quedan en castellano y **sin tildes en los encabezados** (así los tiene PB).
- **Exit codes:** `0` OK · `1` hallazgos · `2` no pude evaluar.
- **Compatibilidad del manifiesto:** los campos nuevos son **opcionales**. Un manifiesto de los Planes 1–4 sigue validando, y lo que le falta para PB aparece en `wow manifest lint --pb` y en `wow pack check`.
- **Commits:** sin atribución de IA, uno por tarea. Cada commit va solo si **ambas** suites salen con exit 0.

## Redefiniciones de los Planes 1–4 (decididas acá)

| Qué se construyó | Problema con PB real | Cambio en este plan |
|---|---|---|
| `wow pack prd\|rfc`: encabezados propios y marcadores `<!-- wow:fill -->` | No coinciden con la plantilla de PB (49 y 35 unidades); PB vuelve a preguntar | Render desde la plantilla real; lo que falta queda como `{{campo}}` (Task 4) |
| `wow pack epic`: historias "H1…" con story points y labels | PB espera JSON: épica de 26 campos e historias de 20 (US-001, Gherkin, componente, DoR de 4, DoD de 11, tasks con propósito y cómo) | Paquete de épica con forma PB; la tarea del manifiesto es la historia y la subtarea es la task de PB (Tasks 1 y 4) |
| Manifiesto | No tiene modo, datos de producto de la épica, componente ni historia por tarea, y las subtareas son solo texto | Campos opcionales nuevos y `pb_lint` (Task 1) |
| `repo.packet_status`: "ok" con solo el hash | Un paquete fresco pero incompleto no sirve | Fase 2 lista = hash, id de plantilla vigente y predicción del 100% sin errores (Tasks 4 y 6) |
| `PREAMBLE` | No contempla las secciones fijas API Gateway y SLA, ni la regla del owner de las preguntas | Preámbulo nuevo (Task 4) |
| `pbaudit`: corpus permitido = paquete más context pack | Con la plantilla nueva, el encabezado `### API Gateway` y el texto "No aplica: no hay API Gateway" "habilitaban" el término | El corpus ignora encabezados y cláusulas negadas; se suman "circuit breaker" y "Kong" a la lista semilla (Task 5) |
| `pbchat.CLOSED_RE`: un "100%" suelto cerraba el chat | "100% de disponibilidad" cerraba el chat; PB tiene una línea autoritativa de completitud | Cierra la línea autoritativa, "llega al 100%" o una frase de cierre explícita (Task 5) |
| `completion_pct` del audit | Se leía de frases del modelo | Se prefiere `**Completitud del documento:** N%`, la línea del backend (Task 5) |
| Prompts brownfield (commit `cda0163`) | Copiaban la plantilla y citaban `discovery/architecture.md` | Operan sobre los `{{campos}}` del paquete y citan `.spec-kit/discovery/architecture.md`, la ruta real según el orquestador; se suman prompts greenfield y de épica (Task 7) |

## Review Focus

1. **El paquete renombra o acentúa un encabezado** ("Visión y Estrategia") → la predicción lo sigue encontrando, porque normaliza tildes y mayúsculas. Test en Task 3.
2. **Una fila de Preguntas Abiertas sin owner** → la predicción baja a 99% y lo lista, como hace PB. Test en Task 3.
3. **Épica con criticidad "[SIN DEFINIR]" o fecha "pronto"** → `wow pack check` da error, porque un valor inválido en un enum o en una fecha rompe la exportación a Jira. No es solo un porcentaje. Test en Task 3.
4. **El paquete trae el encabezado "### API Gateway" con "No aplica: no hay API Gateway" y el chat dice "usamos Kong como API Gateway"** → la auditoría marca ambos términos. Test en Task 5.
5. **Manifiesto de los Planes 1–4 sin los campos nuevos** → sigue validando; `wow manifest lint --pb` lista lo que falta. Test en Task 1.

---

## File Structure

```
wow/templates/pb-prd.md, pb-rfc.md      plantillas PB copiadas (verificadas por hash) — Task 2
wow/pbtemplate.py                        campos, grupos, id de plantilla — Task 2
wow/pbcompletion.py                      predicción % (PRD/RFC) + chequeo de épica — Task 3
wow/manifest.py, schemas/manifest.schema.json   modo, product, component, story, subtareas — Task 1
wow/pack.py                              render PB + preámbulo nuevo — Task 4
wow/sources/repo.py                      template id en packet_status, pending_items — Task 4
wow/pbaudit.py, wow/sources/pbchat.py    corpus, inventos, completitud autoritativa, cierre — Task 5
wow/state.py, wow/evidence.py            modo, discovery, paquete incompleto, packet_pct — Task 6
dashboard/wow-dashboard.html, dashboard/examples/*.json   columna "Packet (predicted)" — Task 6
wow/cli.py                               plan init --mode, manifest lint --pb, pack check — Tasks 1, 3
skills/wow-pack/references/*.md, skills/*/SKILL.md, README.md, spec   prompts y docs — Task 7
tests/pbfill.py                          helper: completa un paquete para que prediga 100% — Task 3
```

---

### Task 1: manifiesto con modo, datos de producto, historia y `pb_lint`

**Files:**
- Modify: `schemas/manifest.schema.json`, `wow/manifest.py`, `wow/cli.py`, `tests/test_manifest.py`, `tests/test_cli.py`

**Interfaces:**
- Produces:
  - `manifest.MODES = ("greenfield", "brownfield")`
  - `manifest.FIBONACCI = (1, 2, 3, 5, 8, 13)`
  - `manifest.COMPONENTS = ("FE", "BE", "BO", "QA", "DEVOPS", "INFRA", "BFF", "AI")`
  - `manifest.new_manifest(plan_id, title, created, mode=None)`
  - `manifest.pb_lint(doc) -> list[str]`
  - `wow plan init ID --title T [--mode greenfield|brownfield]`
  - `wow manifest lint [--pb]`: con `--pb` imprime también `pb_lint`; exit 1 si hay hallazgos.
  - `test_manifest.pb_ready_doc()`: `valid_doc()` más modo, componentes, historias, criterios Gherkin y producto; la usan las Tasks 3–6.

- [ ] **Step 1: Escribir el test que falla**

Agregar a `tests/test_manifest.py`:

```python
def pb_ready_doc() -> dict:
    doc = valid_doc()
    doc["plan"]["mode"] = "brownfield"
    doc["epics"][0]["product"] = {
        "objective": "Curar casos", "problem": "Hoy se cura a mano", "strategic_objective": "Eficiencia",
        "expected_impact": "Menos tiempo de curación", "out_of_scope": "Migrar históricos",
        "insights": ["Los analistas curan 40 casos por día [MEDIDO]"], "assumptions": ["Hay analistas disponibles"],
        "dependencies": ["Equipo de plataforma"], "related_documents": ["PRD de la iniciativa"],
        "start_date": "2026-10-05", "end_date_estimated": "2026-12-18", "quarter": "Q4/2026",
        "criticality": "Alta", "priority": "Alta", "big_move": False, "owner": "Owner de producto",
        "vertical": "Plataforma", "technical_context": "Python sobre AWS Lambda", "notes": "Sin notas adicionales"}
    for task in doc["epics"][0]["tasks"]:
        task["component"] = "BE"
        task["acceptance"] = [f"{a.split(':')[0]}: Dado un caso Cuando el analista lo cura Entonces queda auditado"
                              for a in task["acceptance"]]
        task["story"] = {"user_story_text": "Como analista quiero curar casos para cerrar el ciclo",
                         "context_and_need": "Hoy se cura a mano [MEDIDO]", "scope": "Curación simple",
                         "out_of_scope": "Curación masiva", "technical_info": "Endpoint del BFF",
                         "assumptions": ["Caso existente"], "business_rules": ["Solo analistas"],
                         "edge_cases": ["Caso ya curado"], "assets": ["Contrato del BFF"]}
    return doc


class PbExtensionTest(unittest.TestCase):
    def test_extended_doc_validates_and_old_doc_still_validates(self):
        self.assertEqual(manifest.validate(pb_ready_doc()), [])
        self.assertEqual(manifest.validate(valid_doc()), [])

    def test_schema_rejects_bad_component_date_and_mode(self):
        doc = pb_ready_doc()
        doc["epics"][0]["tasks"][0]["component"] = "Backend"
        doc["epics"][0]["product"]["start_date"] = "pronto"
        doc["plan"]["mode"] = "legacy"
        errors = manifest.validate(doc)
        self.assertTrue(any("component" in e for e in errors), errors)
        self.assertTrue(any("start_date" in e for e in errors), errors)
        self.assertTrue(any("mode" in e for e in errors), errors)

    def test_subtasks_accept_objects(self):
        doc = pb_ready_doc()
        doc["epics"][0]["tasks"][0]["subtasks"] = ["write schema", {"title": "[BE] tabla", "purpose": "guardar",
                                                                     "how_to": "DynamoDB", "component": "BE"}]
        self.assertEqual(manifest.validate(doc), [])

    def test_pb_lint(self):
        self.assertEqual(manifest.pb_lint(pb_ready_doc()), [])
        doc = valid_doc()
        doc["epics"][0]["tasks"][0]["estimate"] = 4
        doc["epics"][0]["tasks"][1]["estimate"] = 13
        self.assertEqual(manifest.pb_lint(doc), [
            "plan: no mode; set plan.mode to greenfield or brownfield (wow plan init --mode)",
            "E1/1.1: estimate 4 is not Fibonacci (1, 2, 3, 5, 8, 13)",
            "E1/1.1: no component (FE, BE, BO, QA, DEVOPS, INFRA, BFF, AI)",
            "E1/1.1: no user story text (Como … quiero … para …)",
            "E1/1.1: AC1 is not Gherkin (Dado … Cuando … Entonces …)",
            "E1/1.2: estimate 13 is above 8; Product Brain suggests splitting the story",
            "E1/1.2: no component (FE, BE, BO, QA, DEVOPS, INFRA, BFF, AI)",
            "E1/1.2: no user story text (Como … quiero … para …)",
            "E1/1.2: AC1 is not Gherkin (Dado … Cuando … Entonces …)",
        ])
```

Agregar a `tests/test_cli.py`:

```python
class PbManifestCommandTest(unittest.TestCase):
    def test_init_with_mode_and_lint_pb(self):
        project = make_project()
        self.assertEqual(run_cli(["plan", "init", "0007-x", "--title", "X", "--mode", "greenfield",
                                  "--project", str(project)])[0], 0)
        saved = _json.loads((project / "wow/plan/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["plan"]["mode"], "greenfield")
        project2 = make_project()
        _manifest.save(project2, valid_doc())
        code, out, _ = run_cli(["manifest", "lint", "--pb", "--project", str(project2)])
        self.assertEqual(code, 1)
        self.assertIn("plan: no mode", out)
```

- [ ] **Step 2: Correr y verificar que falla** — `NameError`/`AttributeError: pb_lint` y `unrecognized arguments: --mode`.

- [ ] **Step 3: Implementar**

`schemas/manifest.schema.json`:
- En `plan.properties` agregar `"mode": {"type": "string", "enum": ["greenfield", "brownfield"]}`.
- En el objeto épica agregar `"product"`.
- En el objeto tarea agregar `"component"` y `"story"`, y reemplazar el schema de `subtasks.items` por la versión de abajo.

```json
"product": {
  "type": "object", "additionalProperties": false,
  "properties": {
    "objective": {"type": "string"}, "problem": {"type": "string"}, "strategic_objective": {"type": "string"},
    "expected_impact": {"type": "string"}, "out_of_scope": {"type": "string"},
    "insights": {"type": "array", "items": {"type": "string"}},
    "assumptions": {"type": "array", "items": {"type": "string"}},
    "dependencies": {"type": "array", "items": {"type": "string"}},
    "related_documents": {"type": "array", "items": {"type": "string"}},
    "start_date": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"},
    "end_date_estimated": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"},
    "quarter": {"type": "string", "pattern": "^Q[1-4]/[0-9]{4}$"},
    "criticality": {"type": "string", "enum": ["Alta", "Media", "Baja"]},
    "priority": {"type": "string", "enum": ["Alta", "Media", "Baja"]},
    "big_move": {"type": "boolean"}, "owner": {"type": "string"}, "vertical": {"type": "string"},
    "technical_context": {"type": "string"}, "notes": {"type": "string"}
  }
}
```

```json
"component": {"type": "string", "pattern": "^(FE|BE|BO|QA|DEVOPS|INFRA|BFF|AI)(/(FE|BE|BO|QA|DEVOPS|INFRA|BFF|AI))*$"},
"story": {
  "type": "object", "additionalProperties": false,
  "properties": {
    "user_story_text": {"type": "string"}, "context_and_need": {"type": "string"}, "scope": {"type": "string"},
    "out_of_scope": {"type": "string"}, "technical_info": {"type": "string"},
    "assumptions": {"type": "array", "items": {"type": "string"}},
    "business_rules": {"type": "array", "items": {"type": "string"}},
    "edge_cases": {"type": "array", "items": {"type": "string"}},
    "assets": {"type": "array", "items": {"type": "string"}}
  }
},
"subtasks": {"type": "array", "items": {
  "type": ["string", "object"], "required": ["title"], "additionalProperties": false,
  "properties": {
    "title": {"type": "string"}, "purpose": {"type": "string"}, "how_to": {"type": "string"},
    "component": {"type": "string", "pattern": "^(FE|BE|BO|QA|DEVOPS|INFRA|BFF|AI)(/(FE|BE|BO|QA|DEVOPS|INFRA|BFF|AI))*$"},
    "story_points": {"type": "integer", "minimum": 0},
    "requirements": {"type": "array", "items": {"type": "string"}}
  }
}}
```

`wow/manifest.py` (agregar `import re` si falta):

```python
MODES = ("greenfield", "brownfield")
FIBONACCI = (1, 2, 3, 5, 8, 13)
COMPONENTS = ("FE", "BE", "BO", "QA", "DEVOPS", "INFRA", "BFF", "AI")
_GHERKIN_RE = re.compile(r"\b(dado|given)\b.*\b(cuando|when)\b.*\b(entonces|then)\b", re.IGNORECASE | re.DOTALL)
_STORY_RE = re.compile(r"^\s*como\b.*\bquiero\b.*\bpara\b", re.IGNORECASE | re.DOTALL)


def pb_lint(doc: dict) -> List[str]:
    """What Product Brain needs that the base schema does not enforce (reference/product-brain/README.md)."""
    findings: List[str] = []
    if doc["plan"].get("mode") not in MODES:
        findings.append("plan: no mode; set plan.mode to greenfield or brownfield (wow plan init --mode)")
    for epic, task in _tasks(doc):
        ref = f"{epic['id']}/{task['id']}"
        estimate = task["estimate"]
        if estimate is not None and estimate not in FIBONACCI:
            findings.append(f"{ref}: estimate {estimate} is not Fibonacci (1, 2, 3, 5, 8, 13)")
        elif estimate is not None and estimate > 8:
            findings.append(f"{ref}: estimate {estimate} is above 8; Product Brain suggests splitting the story")
        if not task.get("component"):
            findings.append(f"{ref}: no component (FE, BE, BO, QA, DEVOPS, INFRA, BFF, AI)")
        if not _STORY_RE.match((task.get("story") or {}).get("user_story_text", "")):
            findings.append(f"{ref}: no user story text (Como … quiero … para …)")
        for item in task["acceptance"]:
            anchor, _, text = item.partition(": ")
            if not _GHERKIN_RE.search(text):
                findings.append(f"{ref}: {anchor} is not Gherkin (Dado … Cuando … Entonces …)")
    return findings
```

> Nota: `_tasks(doc)` ya existe y devuelve los pares `(epic, task)` en orden.

`new_manifest` recibe `mode: Optional[str] = None` y, si viene, hace `doc["plan"]["mode"] = mode`.

`wow/cli.py`:
- **`plan init`:** suma `init.add_argument("--mode", choices=list(manifest.MODES), default=None)` y pasa `mode=args.mode` a `new_manifest`.
- **`manifest lint`:** suma `--pb` (`store_true`). En `_cmd_manifest_lint`, si `args.pb`, extiende los hallazgos con `manifest.pb_lint(doc)` antes de imprimir y calcular el exit code.

- [ ] **Step 4: Correr ambas suites** — exit 0.

- [ ] **Step 5: Commit (solo con ambas suites en 0)** — `feat(manifest): add plan mode, product, story and component fields with a Product Brain lint`

---

### Task 2: plantillas de PB copiadas y `pbtemplate.py`

**Files:**
- Create: `wow/templates/pb-prd.md`, `wow/templates/pb-rfc.md`, `wow/pbtemplate.py`, `tests/test_pbtemplate.py`

**Interfaces:**
- Produces:
  - `pbtemplate.TEMPLATE_ID = "pb-9b19a89"`
  - `pbtemplate.KINDS = ("prd", "rfc")`
  - `pbtemplate.PLACEHOLDER_RE`: el mismo patrón que `detector.ts`, con dos grupos (llave doble y llave simple).
  - `pbtemplate.load(kind) -> str`
  - `pbtemplate.fields(text) -> list[str]`: únicos, en orden.
  - `pbtemplate.groups(names) -> dict[prefix, {"index_type": "numeric"|"alpha", "fields": {name: (index, sub)}}]`: port de `detectFieldGroups`.
  - `pbtemplate.units(kind) -> tuple[list[str], dict]`: los campos sueltos y los grupos.
  - `pbtemplate.extract_upstream(source_text, const_name) -> str`: lo usan el test de deriva y el paso de copia.

- [ ] **Step 1: Copiar las plantillas desde la referencia local y verificar el hash**

```bash
python3 - <<'EOF'
import hashlib
from pathlib import Path
src = Path("reference/product-brain/upstream/base-templates.ts").read_text(encoding="utf-8")
expected = {"PRD_TEMPLATE_CONTENT": ("pb-prd.md", "fa398c0931ea6dfd38e2880e64c91081ec616d08b650f8fde281439e5e4c18eb"),
            "RFC_TEMPLATE_CONTENT": ("pb-rfc.md", "c6f73799424bf8d8ec7c98e42846c548b664d6dcc4cfc2237c23c7c146159927")}
Path("wow/templates").mkdir(exist_ok=True)
for const, (name, digest) in expected.items():
    start = src.index(f"export const {const} = `") + len(f"export const {const} = `")
    text = src[start:src.index("`;", start)].replace("\\`", "`")
    assert hashlib.sha256(text.encode()).hexdigest() == digest, const
    Path("wow/templates", name).write_text(text, encoding="utf-8")
    print("wrote", name)
EOF
```

Expected: `wrote pb-prd.md` y `wrote pb-rfc.md`. Si el hash no coincide, la referencia cambió y hay que revisar el README antes de seguir.

- [ ] **Step 2: Escribir el test que falla**

`tests/test_pbtemplate.py`:

```python
from __future__ import annotations

import unittest

from helpers import ROOT
import pbtemplate


class TemplateTest(unittest.TestCase):
    def test_prd_fields_groups_units(self):
        scalars, groups = pbtemplate.units("prd")
        self.assertEqual(len(pbtemplate.fields(pbtemplate.load("prd"))), 123)
        self.assertEqual(sorted(groups), ["assumption", "dependency", "health_kpi", "in_scope", "kpi", "nfr",
                                          "out_scope", "risk", "secondary_kpi"])
        self.assertEqual(len(scalars) + len(groups), 49)
        self.assertIn("open_questions", scalars)

    def test_rfc_fields_groups_units(self):
        scalars, groups = pbtemplate.units("rfc")
        self.assertEqual(sorted(groups), ["api", "component", "dependency", "goal", "milestone", "non_goal",
                                          "repo", "risk"])
        self.assertEqual(groups["api"]["index_type"], "alpha")
        self.assertEqual(len(scalars) + len(groups), 35)

    def test_single_brace_and_unknown_kind(self):
        self.assertEqual(pbtemplate.fields("{a} {{b}} {{ a }}"), ["a", "b"])
        with self.assertRaises(ValueError):
            pbtemplate.load("epic")

    def test_vendored_templates_match_reference_when_present(self):
        source = ROOT / "reference/product-brain/upstream/base-templates.ts"
        if not source.is_file():
            self.skipTest("reference/product-brain/upstream is not present (run refresh.sh)")
        text = source.read_text(encoding="utf-8")
        self.assertEqual(pbtemplate.extract_upstream(text, "PRD_TEMPLATE_CONTENT"), pbtemplate.load("prd"))
        self.assertEqual(pbtemplate.extract_upstream(text, "RFC_TEMPLATE_CONTENT"), pbtemplate.load("rfc"))
```

- [ ] **Step 3: Correr y verificar que falla** — `No module named 'pbtemplate'`.

- [ ] **Step 4: Implementar `wow/pbtemplate.py`**

```python
"""Product Brain base templates vendored from josefigueredo/acme-agent@9b19a89 (reference/product-brain/README.md).

Field extraction and grouping mirror detector.ts (PLACEHOLDER_PATTERN) and field-groups.ts (detectFieldGroups).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

TEMPLATE_ID = "pb-9b19a89"
KINDS = ("prd", "rfc")
PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}|\{\s*([a-zA-Z0-9_.-]+)\s*\}")
_NUMERIC_RE = re.compile(r"^(.+?)_(\d+)(?:_(.+))?$")
_ALPHA_RE = re.compile(r"^(.+?)_([a-z])(?:_(.+))?$")
_DIR = Path(__file__).resolve().parent / "templates"


def load(kind: str) -> str:
    if kind not in KINDS:
        raise ValueError(f"unknown template kind {kind!r}; expected one of {KINDS}")
    return (_DIR / f"pb-{kind}.md").read_text(encoding="utf-8")


def fields(text: str) -> List[str]:
    found: List[str] = []
    for match in PLACEHOLDER_RE.finditer(text):
        name = (match.group(1) or match.group(2) or "").strip()
        if name and name not in found:
            found.append(name)
    return found


def groups(names: List[str]) -> Dict[str, dict]:
    numeric: Dict[Tuple[str, str], list] = {}
    alpha: Dict[Tuple[str, str], list] = {}
    for name in names:
        match = _NUMERIC_RE.match(name)
        if match:
            numeric.setdefault((match.group(1), match.group(3) or ""), []).append(
                (match.group(1), int(match.group(2)), match.group(3), name))
            continue
        match = _ALPHA_RE.match(name)
        if match:
            alpha.setdefault((match.group(1), match.group(3) or ""), []).append(
                (match.group(1), match.group(2), match.group(3), name))
    result: Dict[str, dict] = {}
    for index_type, buckets in (("numeric", numeric), ("alpha", alpha)):
        for entries in buckets.values():
            if len({entry[1] for entry in entries}) < 2:
                continue
            prefix = entries[0][0]
            if index_type == "alpha" and result.get(prefix, {}).get("index_type") == "numeric":
                continue
            group = result.setdefault(prefix, {"index_type": index_type, "fields": {}})
            for _, index, sub, name in entries:
                group["fields"][name] = (index, sub)
    return result


def units(kind: str) -> Tuple[List[str], Dict[str, dict]]:
    names = fields(load(kind))
    grouped = groups(names)
    members = {name for group in grouped.values() for name in group["fields"]}
    return [name for name in names if name not in members], grouped


def extract_upstream(source_text: str, const_name: str) -> str:
    marker = f"export const {const_name} = `"
    start = source_text.index(marker) + len(marker)
    return source_text[start:source_text.index("`;", start)].replace("\\`", "`")
```

- [ ] **Step 5: Correr ambas suites** — exit 0.

- [ ] **Step 6: Commit (solo con ambas suites en 0)** — `feat(pb): vendor Product Brain templates with field and group extraction`

---

### Task 3: `pbcompletion.py`, `wow pack check` y el helper de tests

**Files:**
- Create: `wow/pbcompletion.py`, `tests/pbfill.py`, `tests/test_pbcompletion.py`
- Modify: `wow/cli.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `pbtemplate.load/units/PLACEHOLDER_RE` (Task 2).
- Produces:
  - `pbcompletion.value_state(text) -> "filled"|"partial"|"empty"`: port de `evaluateFieldState` para strings; antes de evaluar quita los comentarios HTML.
  - `pbcompletion.predict(kind, packet_text) -> {"kind", "percentage", "units", "total", "pending": [{"field", "state", "section"}], "errors": []}`
  - `pbcompletion.EPIC_FIELDS`, `EPIC_LISTS`, `STORY_FIELDS`, `STORY_LISTS`, `DOR`, `DOD`: los consume la Task 4.
  - `pbcompletion.check_epic(packet_text) -> {mismo shape}`: 26 unidades, y `errors` con los enums, formatos, listas fijas y Gherkin.
  - `pbcompletion.check_file(project, name) -> dict | None`: `name` es `prd`, `rfc` o `epic-E<n>`; devuelve `None` si el archivo no existe.
  - CLI `wow pack check {prd,rfc,epic} [--id E1] [--project]`:
    - imprime `predicted completion: N% (U/T units)`, luego un `pending: <field> (<state>) in <section>` por campo y un `error: …` por error;
    - exit `0` si da 100% sin errores, `1` si no, `2` si falta el paquete o el `--id`.
  - `tests/pbfill.fill(text) -> str`: reemplaza cada `{{campo}}` por un valor válido, así el paquete predice 100%.

- [ ] **Step 1: Escribir el helper y el test que falla**

`tests/pbfill.py`:

```python
"""Test helper: fill every Product Brain placeholder of a generated packet so it predicts 100%."""
from __future__ import annotations

import re

VALUES = {"criticality": "Alta", "priority": "Media", "start_date": "2026-10-05", "end_date_estimated": "2026-12-18",
          "quarter": "Q4/2026", "big_move": "No", "component": "BE", "components": "BE", "status": "todo",
          "estimation_method": "story_points", "story_points": "3",
          "user_story_text": "Como analista quiero curar casos para cerrar el ciclo"}
_PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")
_INDEXED = re.compile(r"^[a-z_]+?_(?:\d+|[a-z])_")


def fill(text: str) -> str:
    text = text.replace("{{open_questions}}", "| 1 | dato | Owner de producto | Abierta |")
    return _PLACEHOLDER.sub(lambda m: VALUES.get(m.group(1), VALUES.get(_INDEXED.sub("", m.group(1)), "dato")), text)
```

`tests/test_pbcompletion.py`:

```python
from __future__ import annotations

import unittest

from helpers import make_project, write
import pbcompletion
import pbtemplate
from pbfill import fill


class ValueStateTest(unittest.TestCase):
    def test_states(self):
        self.assertEqual(pbcompletion.value_state("  "), "empty")
        self.assertEqual(pbcompletion.value_state("{{x}}"), "empty")
        self.assertEqual(pbcompletion.value_state("texto {{x}}"), "partial")
        self.assertEqual(pbcompletion.value_state("[SIN DEFINIR] — decide el owner"), "filled")
        self.assertEqual(pbcompletion.value_state("<!-- wow:fill x -->"), "empty")


class PredictTest(unittest.TestCase):
    def test_raw_templates_are_zero_and_filled_are_hundred(self):
        for kind, total in (("prd", 49), ("rfc", 35)):
            raw = pbcompletion.predict(kind, pbtemplate.load(kind))
            self.assertEqual((raw["percentage"], raw["total"]), (0, total), kind)
            full = pbcompletion.predict(kind, fill(pbtemplate.load(kind)))
            self.assertEqual((full["percentage"], full["pending"]), (100, []), kind)

    def test_open_question_without_owner_is_partial(self):
        text = fill(pbtemplate.load("prd")).replace("| 1 | dato | Owner de producto | Abierta |", "| 1 | dato |  | Abierta |")
        result = pbcompletion.predict("prd", text)
        self.assertEqual(result["percentage"], 99)
        self.assertEqual(result["pending"], [{"field": "open_questions", "state": "partial",
                                              "section": "## Preguntas Abiertas"}])

    def test_group_with_one_complete_row_is_filled_and_empty_kv_cell_is_empty(self):
        lines = fill(pbtemplate.load("prd")).replace("| Autor | dato |", "| Autor |  |").splitlines()
        start = lines.index("### KPIs Primarios")
        kpi_rows = [i for i in range(start, start + 9) if lines[i].startswith("| dato |")]
        for index in reversed(kpi_rows[1:]):
            del lines[index]
        result = pbcompletion.predict("prd", "\n".join(lines))
        self.assertIn({"field": "author", "state": "empty", "section": "# dato"}, result["pending"])
        self.assertNotIn("kpi", [p["field"] for p in result["pending"]])
        self.assertEqual(result["percentage"], 98)

    def test_accented_heading_still_matches(self):
        text = fill(pbtemplate.load("prd")).replace("## Vision y Estrategia", "## Visión y Estrategia")
        self.assertEqual(pbcompletion.predict("prd", text)["percentage"], 100)

    def test_missing_section_empties_its_fields(self):
        text = fill(pbtemplate.load("rfc"))
        start = text.index("### Coexistencia y Fallback")
        end = text.index("### Especificaciones de API")
        result = pbcompletion.predict("rfc", text[:start] + text[end:])
        self.assertIn("coexistence_strategy", [p["field"] for p in result["pending"]])


class EpicCheckTest(unittest.TestCase):
    def test_epic_errors_for_invalid_values(self):
        packet = ("# Épica E1 — X\n\n## Datos de la épica\n| Campo | Valor |\n| --- | --- |\n"
                  "| Criticidad (criticality) | [SIN DEFINIR] |\n| Fecha de inicio (start_date) | pronto |\n"
                  "| Quarter (quarter) | {{quarter}} |\n\n## Historias\n\n### US-001 — [Backend] API (tarea 1.1)\n"
                  "| Campo | Valor |\n| --- | --- |\n| Story points (story_points) | 4 |\n| Componente (component) | Backend |\n"
                  "| Historia (user_story_text) | Quiero curar |\n\n#### Criterios de aceptación (acceptance_criteria)\n"
                  "- AC1 — devuelve 200\n")
        result = pbcompletion.check_epic(packet)
        self.assertEqual(result["errors"], [
            "criticality: '[SIN DEFINIR]' must be one of Alta, Media, Baja",
            "start_date: 'pronto' must be YYYY-MM-DD",
            "US-001 story_points: 4 is not Fibonacci (1, 2, 3, 5, 8, 13)",
            "US-001 component: 'Backend' must be FE, BE, BO, QA, DEVOPS, INFRA, BFF or AI",
            "US-001 user_story_text: must read 'Como … quiero … para …'",
            "US-001 acceptance_criteria: 'AC1 — devuelve 200' is not Gherkin",
            "US-001 definition_of_ready: must be the 4 fixed Product Brain items",
            "US-001 definition_of_done: must be the 11 fixed Product Brain items with si/no",
        ])
        self.assertEqual(result["total"], 26)


class CheckFileTest(unittest.TestCase):
    def test_missing_and_present(self):
        project = make_project()
        self.assertIsNone(pbcompletion.check_file(project, "prd"))
        write(project, "wow/pb/prd.md", fill(pbtemplate.load("prd")))
        self.assertEqual(pbcompletion.check_file(project, "prd")["percentage"], 100)
```

Agregar a `tests/test_cli.py`:

```python
class PackCheckCommandTest(unittest.TestCase):
    def test_check_codes(self):
        import pbtemplate as _pbt
        from pbfill import fill as _fill
        project = make_project()
        self.assertEqual(run_cli(["pack", "check", "prd", "--project", str(project)])[0], 2)
        write(project, "wow/pb/prd.md", _pbt.load("prd"))
        code, out, _ = run_cli(["pack", "check", "prd", "--project", str(project)])
        self.assertEqual(code, 1)
        self.assertIn("predicted completion: 0% (0/49 units)", out)
        write(project, "wow/pb/prd.md", _fill(_pbt.load("prd")))
        self.assertEqual(run_cli(["pack", "check", "prd", "--project", str(project)])[0], 0)
        self.assertEqual(run_cli(["pack", "check", "epic", "--project", str(project)])[0], 2)
```

> Nota sobre `test_group_with_one_complete_row…`: deja una sola fila en KPIs Primarios (la tabla sigue llena) y vacía solo
> `author`: (49 − 1) / 49 = 97,96, que redondea a 98%.

- [ ] **Step 2: Correr y verificar que falla** — `No module named 'pbcompletion'`.

- [ ] **Step 3: Implementar `wow/pbcompletion.py`**

```python
"""Predict Product Brain's completion % before pasting (port of completion.ts + open-questions-validation.ts).

Same unit rules as the backend: a field is filled by any non-empty text, an unreplaced {{placeholder}} is empty,
mixed text with a placeholder is partial; each numbered table/list is one unit filled by one complete row;
open_questions needs question + owner + status on every row. Values are read from the packet by aligning it
with the vendored template section by section (headings compared without accents or case).
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pbtemplate

UNITS = {"filled": 1.0, "partial": 0.5, "empty": 0.0}
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_PURE_RE = re.compile(r"^\{\{\s*[a-zA-Z0-9_.-]+\s*\}\}$")
_MIXED_RE = re.compile(r"\{\{.+?\}\}")
_SEPARATOR_RE = re.compile(r"^\|?\s*:?-{3,}")
_LABEL_RE = re.compile(r"^\*\*(.+?)\*\*\s*:\s*(.*)$")


def value_state(text: str) -> str:
    value = _COMMENT_RE.sub("", text or "").strip()
    if not value or _PURE_RE.match(value):
        return "empty"
    return "partial" if _MIXED_RE.search(value) else "filled"


def _aggregate(states: List[str]) -> str:
    if not states or all(s == "empty" for s in states):
        return "empty"
    return "filled" if all(s == "filled" for s in states) else "partial"


def _any_row(states: List[str]) -> str:
    if not states or all(s == "empty" for s in states):
        return "empty"
    return "filled" if "filled" in states else "partial"


def _norm(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return re.sub(r"\s+", " ", "".join(c for c in decomposed if not unicodedata.combining(c))).strip().lower()


def _cells(line: str) -> List[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _sections(text: str) -> List[Tuple[str, List[str]]]:
    sections: List[Tuple[str, List[str]]] = [("", [])]
    for line in text.splitlines():
        if _HEADING_RE.match(line):
            sections.append((line.strip(), []))
        else:
            sections[-1][1].append(line)
    return sections


def _heading_regex(template_heading: str) -> "re.Pattern[str]":
    parts = re.split(r"(\{\{\s*[a-zA-Z0-9_.-]+\s*\}\})", _norm(template_heading))
    body = "".join(f"(?P<{re.sub(r'[^a-z0-9_]', '_', p.strip('{} '))}>.*?)" if p.startswith("{{") else re.escape(p)
                   for p in parts)
    return re.compile(f"^{body}$")


def _level(heading: str) -> int:
    match = _HEADING_RE.match(heading)
    return len(match.group(1)) if match else 0


def _template_map(kind: str) -> Tuple[Dict[str, dict], Dict[str, dict], Dict[str, List[str]]]:
    text = pbtemplate.load(kind)
    scalars, groups = pbtemplate.units(kind)
    member = {name: prefix for prefix, group in groups.items() for name in group["fields"]}
    meta: Dict[str, dict] = {}
    group_meta: Dict[str, dict] = {}
    literals: Dict[str, List[str]] = {}
    current, stack = "", []
    for line in text.splitlines():
        heading = _HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            stack = [h for h in stack if _level(h) < level]
            parent = stack[-1] if stack else ""
            stack.append(line.strip())
            current = line.strip()
        elif not pbtemplate.PLACEHOLDER_RE.search(line) and line.strip():
            literals.setdefault(current, []).append(_norm(line))
        for match in pbtemplate.PLACEHOLDER_RE.finditer(line):
            name = (match.group(1) or match.group(2)).strip()
            if name in member:
                prefix = member[name]
                if prefix not in group_meta:
                    layout = "block" if heading else ("table" if line.strip().startswith("|") else "bullet")
                    columns = [i for i, c in enumerate(_cells(line)) if pbtemplate.PLACEHOLDER_RE.search(c)] \
                        if layout == "table" else []
                    group_meta[prefix] = {"section": parent if heading else current, "layout": layout,
                                          "columns": columns}
                continue
            if name in meta:
                continue
            if heading:
                meta[name] = {"section": current, "kind": "heading"}
            elif name == "open_questions":
                meta[name] = {"section": current, "kind": "open_questions"}
            elif line.strip().startswith("|"):
                meta[name] = {"section": current, "kind": "kv", "label": _norm(_cells(line)[0])}
            elif _LABEL_RE.match(line.strip()):
                meta[name] = {"section": current, "kind": "label", "label": _norm(_LABEL_RE.match(line.strip()).group(1))}
            else:
                meta[name] = {"section": current, "kind": "free"}
    return meta, group_meta, literals


def _find(sections, template_heading: str) -> Optional[Tuple[int, str, List[str]]]:
    if not template_heading:
        return 0, "", sections[0][1]
    regex = _heading_regex(template_heading)
    for index, (heading, body) in enumerate(sections):
        if heading and regex.match(_norm(heading)):
            return index, heading, body
    return None


def _table_rows(body: List[str]) -> List[List[str]]:
    rows, in_table = [], False
    for line in body:
        if line.strip().startswith("|"):
            if not in_table:
                in_table = True
                continue  # header row of this table
            if not _SEPARATOR_RE.match(line.strip()):
                rows.append(_cells(line))
        else:
            in_table = False
    return rows


def _content_state(text: str) -> str:
    """State of a multi-slot block: empty when only placeholders and template labels remain."""
    without = _MIXED_RE.sub("", _COMMENT_RE.sub("", text))
    without = re.sub(r"(?i)\b(endpoint|descripcion|request|response)\s*:", "", without)
    if not re.sub(r"[\s\-`|>*:#.]", "", without):
        return "empty"
    return "partial" if _MIXED_RE.search(text) else "filled"


def _free_text(body: List[str], literals: List[str]) -> str:
    kept = []
    for line in body:
        stripped = line.strip()
        if not stripped or stripped.startswith("|") or _LABEL_RE.match(stripped) or _norm(stripped) in literals:
            continue
        kept.append(stripped.lstrip(">").strip())
    return "\n".join(kept)


def predict(kind: str, packet: str) -> dict:
    meta, group_meta, literals = _template_map(kind)
    clean = _COMMENT_RE.sub("", packet)
    sections = _sections(clean)
    states: List[Tuple[str, str, str]] = []
    for name, info in meta.items():
        found = _find(sections, info["section"])
        state = "empty"
        where = found[1] if found is not None and found[1] else info["section"]
        if found is not None:
            index, heading, body = found
            if info["kind"] == "heading":
                match = _heading_regex(info["section"]).match(_norm(heading))
                state = value_state(match.group(re.sub(r"[^a-z0-9_]", "_", name)) if match else "")
            elif info["kind"] == "kv":
                rows = [_cells(l) for l in body if l.strip().startswith("|")]
                state = next((value_state(r[1]) for r in rows if len(r) > 1 and _norm(r[0]) == info["label"]), "empty")
            elif info["kind"] == "label":
                lines = [_LABEL_RE.match(l.strip()) for l in body]
                state = next((value_state(m.group(2)) for m in lines if m and _norm(m.group(1)) == info["label"]), "empty")
            elif info["kind"] == "open_questions":
                rows = [r for r in _table_rows(body) if len(r) >= 4]
                state = _aggregate([_aggregate([value_state(c) for c in r[1:4]]) for r in rows])
            elif re.search(r"\{\{\s*" + re.escape(name) + r"\s*\}\}", clean):
                state = "empty"
            else:
                state = value_state(_free_text(body, literals.get(info["section"], [])))
        states.append((name, state, where))
    for prefix, info in group_meta.items():
        found = _find(sections, info["section"])
        state = "empty"
        where = found[1] if found is not None and found[1] else info["section"]
        if found is not None:
            index, heading, body = found
            if info["layout"] == "table":
                rows = [[row[i] if i < len(row) else "" for i in info["columns"]] for row in _table_rows(body)]
                state = _any_row([_aggregate([value_state(c) for c in row]) for row in rows])
            elif info["layout"] == "bullet":
                items = [l.strip()[2:] for l in body if l.strip().startswith("- ")]
                state = _any_row([value_state(item) for item in items])
            else:
                blocks, level = [], _level(heading)
                for sub_heading, sub_body in sections[index + 1:]:
                    if _level(sub_heading) <= level:
                        break
                    text = re.sub(r"^#+\s*[A-Z]\.\s*", "", sub_heading) + "\n" + "\n".join(sub_body)
                    blocks.append(_content_state(text))
                state = _any_row(blocks)
        states.append((prefix, state, where))
    units = sum(UNITS[state] for _, state, _ in states)
    total = len(states)
    return {"kind": kind, "percentage": round(units / total * 100) if total else 0, "units": units, "total": total,
            "pending": [{"field": f, "state": s, "section": sec} for f, s, sec in states if s != "filled"],
            "errors": []}
```

> **Notas sobre `predict`:**
> - `pending` informa la sección con el encabezado real del paquete (por ejemplo `# dato`); si no está, usa el de la plantilla.
> - En las tablas de grupo solo cuentan las columnas que tenían placeholder en la plantilla. Así la columna `#` con "1" no
>   vuelve "parcial" una fila vacía.
> - Los bloques de API se evalúan con `_content_state`: si solo quedan placeholders y las etiquetas
>   `Endpoint:` / `Request:` / `Response:`, el bloque cuenta como vacío.

Agregar, en el mismo archivo, el chequeo de la épica:

```python
EPIC_FIELDS = [("epic_name", "Nombre"), ("objective", "Objetivo"), ("problem", "Problema"),
               ("strategic_objective", "Objetivo estratégico"), ("expected_impact", "Impacto esperado"),
               ("out_of_scope", "Fuera de alcance"), ("start_date", "Fecha de inicio"),
               ("end_date_estimated", "Fecha estimada de entrega"), ("quarter", "Quarter"),
               ("criticality", "Criticidad"), ("priority", "Prioridad"), ("big_move", "Big Move"), ("owner", "Owner"),
               ("status", "Estado"), ("vertical", "Vertical"), ("technical_context", "Contexto técnico"),
               ("estimation_method", "Método de estimación"), ("jira_prefix", "Prefijo Jira"), ("notes", "Notas")]
EPIC_LISTS = [("insights", "Insights"), ("assumptions", "Supuestos"), ("dependencies", "Dependencias"),
              ("related_documents", "Documentos relacionados"), ("components", "Componentes"), ("labels", "Labels")]
STORY_FIELDS = [("user_story_text", "Historia"), ("context_and_need", "Contexto y necesidad"), ("scope", "Alcance"),
                ("out_of_scope", "Fuera de alcance"), ("technical_info", "Información técnica"),
                ("story_points", "Story points"), ("priority", "Prioridad"), ("component", "Componente"),
                ("status", "Estado")]
STORY_LISTS = [("assumptions", "Supuestos"), ("business_rules", "Reglas de negocio"), ("edge_cases", "Casos borde"),
               ("assets", "Assets"), ("dependencies", "Dependencias"), ("acceptance_criteria", "Criterios de aceptación"),
               ("definition_of_ready", "Definition of Ready"), ("definition_of_done", "Definition of Done"),
               ("tasks", "Tasks")]
DOR = ["La Historia de Usuario está clara y detallada.", "Los criterios de aceptación están definidos.",
       "Los assets (APIs, Figmas UI/UX, etc) están listos.", "El tamaño de la tarea ha sido estimado por el equipo."]
DOD = ["El código ha sido revisado por pares (Code Review).",
       "Las pruebas automatizadas y manuales han pasado exitosamente.",
       "Se realizó Demo end to end del desarrollo entre Producto, UX e Ingeniería.",
       "No existen errores críticos conocidos, lo cual nos permite deployar.",
       "El desarrollo está integrado y desplegado en el entorno correspondiente.",
       "Tenemos alertas configuradas desde Ing. para detectar anomalías.",
       "Tenemos taggeado el flujo en Amplitude.",
       "Se necesita incluir comunicaciones hacia el usuario: mails, push, comprobantes, etc.",
       "Tiene dependencias con tools de gestión: CRM -tipologías-, Backoffice.",
       "Se necesitan herramientas / capacitaciones / procesos necesarios para la gestión del producto en las áreas de "
       "Experiencia, Operaciones (Contact Center, Backoffice, Sucursales).",
       "Tiene dependencias con el BOT / Centro de ayuda /IVR /Turnero / Videollamada."]
_KEY_RE = re.compile(r"\(([a-z_]+)\)\s*$")
_STORY_HEADING_RE = re.compile(r"^###\s+(US-\d+)\s+[—-]\s+(.*)$")
_ENUM3 = ("Alta", "Media", "Baja")
_STATUS = ("draft", "todo", "in_progress", "in_review", "done", "blocked")
_COMPONENT_RE = re.compile(r"^(FE|BE|BO|QA|DEVOPS|INFRA|BFF|AI)(/(FE|BE|BO|QA|DEVOPS|INFRA|BFF|AI))*$")
_GHERKIN_RE = re.compile(r"\b(dado|given)\b.*\b(cuando|when)\b.*\b(entonces|then)\b", re.IGNORECASE)
_STORY_TEXT_RE = re.compile(r"^\s*como\b.*\bquiero\b.*\bpara\b", re.IGNORECASE)


def _parse_epic(text: str) -> Tuple[Dict[str, List[str]], List[Dict[str, List[str]]]]:
    epic: Dict[str, List[str]] = {}
    stories: List[Dict[str, List[str]]] = []
    target = epic
    for heading, body in _sections(_COMMENT_RE.sub("", text)):
        story = _STORY_HEADING_RE.match(heading)
        if story:
            target = {"id": [story.group(1)], "title": [story.group(2)]}
            stories.append(target)
        elif heading.startswith("## "):
            target = epic
        key = _KEY_RE.search(heading)
        if key:
            target[key.group(1)] = [l.strip()[2:] for l in body if l.strip().startswith("- ")]
        for line in body:
            if line.strip().startswith("|"):
                cells = _cells(line)
                match = _KEY_RE.search(cells[0]) if cells else None
                if match and len(cells) > 1:
                    target[match.group(1)] = [cells[1]]
    return epic, stories


def _present(values: List[str]) -> Optional[str]:
    return values[0] if values and value_state(values[0]) == "filled" else None


def check_epic(text: str) -> dict:
    epic, stories = _parse_epic(text)
    errors: List[str] = []
    for key, allowed in (("criticality", _ENUM3), ("priority", _ENUM3), ("status", _STATUS),
                         ("estimation_method", ("story_points", "hours", "t_shirt")), ("big_move", ("Sí", "Si", "No"))):
        value = _present(epic.get(key, []))
        if value is not None and value not in allowed:
            errors.append(f"{key}: {value!r} must be one of {', '.join(allowed)}")
    for key in ("start_date", "end_date_estimated"):
        value = _present(epic.get(key, []))
        if value is not None and not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
            errors.append(f"{key}: {value!r} must be YYYY-MM-DD")
    quarter = _present(epic.get("quarter", []))
    if quarter is not None and not re.match(r"^Q[1-4]/\d{4}$", quarter):
        errors.append(f"quarter: {quarter!r} must be Q<1-4>/YYYY")
    for item in epic.get("components", []):
        if value_state(item) == "filled" and not _COMPONENT_RE.match(item):
            errors.append(f"components: {item!r} must be FE, BE, BO, QA, DEVOPS, INFRA, BFF or AI")
    for story in stories:
        sid = story["id"][0]
        points = _present(story.get("story_points", []))
        if points is not None and points not in {str(n) for n in (1, 2, 3, 5, 8, 13)}:
            errors.append(f"{sid} story_points: {points} is not Fibonacci (1, 2, 3, 5, 8, 13)")
        component = _present(story.get("component", []))
        if component is not None and not _COMPONENT_RE.match(component):
            errors.append(f"{sid} component: {component!r} must be FE, BE, BO, QA, DEVOPS, INFRA, BFF or AI")
        priority = _present(story.get("priority", []))
        if priority is not None and priority not in _ENUM3:
            errors.append(f"{sid} priority: {priority!r} must be one of Alta, Media, Baja")
        status = _present(story.get("status", []))
        if status is not None and status not in ("todo", "in_progress", "done", "blocked"):
            errors.append(f"{sid} status: {status!r} must be todo, in_progress, done or blocked")
        story_text = _present(story.get("user_story_text", []))
        if story_text is not None and not _STORY_TEXT_RE.match(story_text):
            errors.append(f"{sid} user_story_text: must read 'Como … quiero … para …'")
        for criterion in story.get("acceptance_criteria", []):
            if value_state(criterion) == "filled" and not _GHERKIN_RE.search(criterion):
                errors.append(f"{sid} acceptance_criteria: {criterion!r} is not Gherkin")
        if story.get("definition_of_ready", []) != DOR:
            errors.append(f"{sid} definition_of_ready: must be the 4 fixed Product Brain items")
        dod = story.get("definition_of_done", [])
        if [d.rsplit(" — ", 1)[0] for d in dod] != DOD or any(d.rsplit(" — ", 1)[-1] not in ("si", "no") for d in dod):
            errors.append(f"{sid} definition_of_done: must be the 11 fixed Product Brain items with si/no")
    states: List[Tuple[str, str]] = []
    for key, _ in EPIC_FIELDS:
        states.append((key, value_state(epic[key][0]) if epic.get(key) else "empty"))
    for key, _ in EPIC_LISTS:
        states.append((key, _aggregate([value_state(v) for v in epic.get(key, [])])))
    story_keys = ["id", "title"] + [k for k, _ in STORY_FIELDS] + [k for k, _ in STORY_LISTS]
    story_states = [_aggregate([_aggregate([value_state(v) for v in s.get(k, [])]) for k in story_keys])
                    for s in stories]
    states.append(("user_stories", _aggregate(story_states)))
    units = sum(UNITS[s] for _, s in states)
    return {"kind": "epic", "percentage": round(units / len(states) * 100), "units": units, "total": len(states),
            "pending": [{"field": k, "state": s, "section": "epic"} for k, s in states if s != "filled"],
            "errors": errors}


def check_file(project: Path, name: str) -> Optional[dict]:
    path = project / "wow" / "pb" / f"{name}.md"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    return check_epic(text) if name.startswith("epic-") else predict(name, text)
```

> Nota: el test de errores de épica pide la lista exacta de errores. El orden lo dan los dos bucles de arriba: primero los campos de la épica y después cada historia.

`wow/cli.py`: `import pbcompletion` y un subparser `check` dentro de `pack`. El `pack` actual tiene el argumento posicional `kind`, así que se convierte en subcomandos de forma compatible:
- `wow pack prd|rfc|epic …` sigue funcionando: si el primer valor es `check`, se usa el subcomando nuevo.
- Implementación: `pk.add_argument("kind", choices=["prd", "rfc", "epic", "check"])`, más un posicional opcional `target` (`nargs="?"`, choices `prd`, `rfc`, `epic`) que se usa solo con `check`.

```python
def _cmd_pack_check(args, project: Path) -> int:
    if args.target is None or (args.target == "epic" and not args.id):
        sys.stderr.write("wow: pack check needs prd | rfc | epic --id E<n>\n")
        return exitcodes.CANNOT_EVALUATE
    name = f"epic-{args.id}" if args.target == "epic" else args.target
    result = pbcompletion.check_file(project, name)
    if result is None:
        sys.stderr.write(f"wow: wow/pb/{name}.md not found; run wow pack {args.target} first\n")
        return exitcodes.CANNOT_EVALUATE
    units = f"{result['units']:g}"
    print(f"predicted completion: {result['percentage']}% ({units}/{result['total']} units)")
    for item in result["pending"]:
        print(f"pending: {item['field']} ({item['state']}) in {item['section']}")
    for error in result["errors"]:
        print(f"error: {error}")
    return exitcodes.OK if result["percentage"] == 100 and not result["errors"] else exitcodes.FINDINGS
```

Al principio de `_cmd_pack`: `if args.kind == "check": return _cmd_pack_check(args, _project(args))`. En el parser: `pk.add_argument("target", nargs="?", choices=["prd", "rfc", "epic"], default=None)`.

- [ ] **Step 4: Correr ambas suites** — exit 0. Si `test_group_with_one_complete_row…` falla porque el filtro vació alguna tabla, ajustá el filtro como dice la nota del Step 1 y registrá el Ruling.

- [ ] **Step 5: Commit (solo con ambas suites en 0)** — `feat(pb): predict Product Brain completion locally and check epic packets`

---

### Task 4: `pack.py` con la forma de PB, preámbulo nuevo y paquetes viejos como desactualizados

**Files:**
- Modify: `wow/pack.py`, `wow/sources/repo.py`, `wow/cli.py`, `tests/test_pack.py` (reescribir), `tests/test_repo.py`, `tests/test_state.py`

**Interfaces:**
- Consumes:
  - `pbtemplate` (Task 2);
  - `pbcompletion.EPIC_*`, `STORY_*`, `DOR`, `DOD` (Task 3);
  - `test_manifest.pb_ready_doc` (Task 1);
  - `pbfill.fill` (Task 3).
- Produces:
  - `pack.render_prd(doc, brief, mhash, pending=(), owner_role="Owner de producto") -> str`
  - `pack.render_rfc(doc, brief, mhash, pending=(), owner_role="Owner de producto") -> str`
  - `pack.render_epic(doc, epic_id, mhash) -> str`
  - `pack.PREAMBLE` (nuevo texto) y `pack.parse_brief`, `write_packet`, `ensure_preamble`, sin cambios.
  - El encabezado de los tres paquetes es `<!-- wow: manifest-hash=<h> template=pb-9b19a89 · generated by `wow pack …` -->`.
  - `repo.TEMPLATE_RE` y `repo.pending_items(project) -> list[str]` (los ítems `- [ ]` de `pending-owner.md`).
  - `repo.packet_status`: devuelve "stale" también cuando falta el id de plantilla o es distinto de `pbtemplate.TEMPLATE_ID`.
  - CLI `wow pack prd|rfc`: le pasa `pending=repo.pending_items(project)`.

- [ ] **Step 1: Reescribir `tests/test_pack.py` (el test que falla)**

```python
from __future__ import annotations

import unittest

from helpers import make_project, write
import config
import manifest
import pack
import pbcompletion
import state
from pbfill import fill
from sources import repo
from test_manifest import pb_ready_doc, valid_doc

BRIEF = """# Plan
## Brief
- Goal: Curar casos en IRIS v2
- Decisions: D1 una sola máquina de estados · D2 BFF como frontera
- Constraints: costo del juez ≤ USD 100
- Non-goals: migrar datos históricos · curación masiva
- Open questions: ¿Se incorpora la etapa de plan?
"""
H = "0123456789abcdef"


class BriefTest(unittest.TestCase):
    def test_parse_brief(self):
        brief = pack.parse_brief(BRIEF)
        self.assertEqual((brief["Goal"], brief["Open questions"]), ("Curar casos en IRIS v2", "¿Se incorpora la etapa de plan?"))


class PrdRfcTest(unittest.TestCase):
    def test_prd_follows_pb_template_and_keeps_unknowns_as_placeholders(self):
        text = pack.render_prd(pb_ready_doc(), pack.parse_brief(BRIEF), H, pending=["North Star"])
        self.assertEqual(repo.HASH_RE.search(text).group(1), H)
        self.assertIn("template=pb-9b19a89", text)
        self.assertIn("## Vision y Estrategia", text)
        self.assertIn("| Tipo de Iniciativa | Evolución de sistema existente |", text)
        self.assertIn("| 1 | E1: Curation | E1.C1: analysts can curate |", text)
        self.assertIn("| 1 | migrar datos históricos | {{out_scope_1_reason}} | {{out_scope_1_when}} |", text)
        self.assertIn("| 2 | curación masiva |", text)
        self.assertIn("| 1 | ¿Se incorpora la etapa de plan? | Owner de producto | Abierta |", text)
        self.assertIn("| 2 | North Star | Owner de producto | Abierta |", text)
        self.assertIn("{{why_now}}", text)
        self.assertNotIn("{{in_scope_2_name}}", text)
        result = pbcompletion.predict("prd", text)
        self.assertLess(result["percentage"], 100)
        self.assertEqual(pbcompletion.predict("prd", fill(text))["percentage"], 100)

    def test_rfc_greenfield_coexistence_and_milestones(self):
        doc = pb_ready_doc()
        doc["plan"]["mode"] = "greenfield"
        text = pack.render_rfc(doc, pack.parse_brief(BRIEF), H)
        self.assertIn("No aplica: sistema nuevo; no convive con un sistema previo.", text)
        self.assertIn("| E1 | Curation | 5 story points |", text)
        self.assertIn("- E1.C1: analysts can curate", text)
        self.assertIn("### API Gateway", text)
        self.assertEqual(pbcompletion.predict("rfc", fill(text))["percentage"], 100)


class EpicTest(unittest.TestCase):
    def test_epic_packet_has_pb_shape_and_checks_clean_when_filled(self):
        text = pack.render_epic(pb_ready_doc(), "E1", H)
        self.assertIn("| Criticidad (criticality) | Alta |", text)
        self.assertIn("### US-002 — [BE] API (tarea 1.2)", text)
        self.assertIn("| Story points (story_points) | 2 |", text)
        self.assertIn("| Prioridad (priority) | Media |", text)
        self.assertIn("- US-001 (tarea 1.1)", text)
        self.assertIn("- AC1 — Dado un caso Cuando el analista lo cura Entonces queda auditado", text)
        self.assertIn("- " + pbcompletion.DOR[0], text)
        self.assertIn("- " + pbcompletion.DOD[10] + " — no", text)
        self.assertIn("E1.C1: analysts can curate", text)
        result = pbcompletion.check_epic(fill(text))
        self.assertEqual((result["percentage"], result["errors"]), (100, []))
        with self.assertRaises(ValueError):
            pack.render_epic(pb_ready_doc(), "E9", H)

    def test_old_manifest_epic_lists_what_is_missing(self):
        result = pbcompletion.check_epic(pack.render_epic(valid_doc(), "E1", H))
        self.assertLess(result["percentage"], 100)
        self.assertTrue(any("not Gherkin" in e for e in result["errors"]))


class WriteTest(unittest.TestCase):
    def test_refuses_overwrite_without_force_and_preamble_rules(self):
        project = make_project()
        pack.write_packet(project, "prd", "v1")
        with self.assertRaises(FileExistsError):
            pack.write_packet(project, "prd", "v2")
        text = pack.ensure_preamble(project).read_text(encoding="utf-8")
        for needle in ("API Gateway", "SLA", "Owner es el rol que decide", "No aplica", "[SIN DEFINIR]"):
            self.assertIn(needle, text)


class StateIntegrationTest(unittest.TestCase):
    def test_filled_packets_reach_phase_3_and_unfilled_stay_in_phase_2(self):
        project = make_project()
        write(project, "wow/context-pack/facts.md", "x")
        write(project, "wow/context-pack/pending-owner.md", "")
        write(project, ".spec-kit/discovery/architecture.md", "# Arquitectura\n")
        doc = pb_ready_doc()
        doc["plan"]["readiness"] = {"verdict": "approved", "rounds": 1}
        manifest.save(project, doc)
        mhash = manifest.manifest_hash(project)
        brief = pack.parse_brief(BRIEF)
        packets = {"prd": pack.render_prd(doc, brief, mhash), "rfc": pack.render_rfc(doc, brief, mhash),
                   "epic-E1": pack.render_epic(doc, "E1", mhash)}
        for name, text in packets.items():
            pack.write_packet(project, name, text)
        result = state.compute_state(project, config.DEFAULTS)
        self.assertEqual(result["plan"]["phase"], 2)
        self.assertTrue(any(s["action"].startswith("complete the prd packet") for s in result["next_steps"]))
        for name, text in packets.items():
            pack.write_packet(project, name, fill(text), force=True)
        self.assertEqual(state.compute_state(project, config.DEFAULTS)["plan"]["phase"], 3)


if __name__ == "__main__":
    unittest.main()
```

En `tests/test_repo.py`, `PacketTest`: los encabezados de `prd.md` y `epic-E1.md` llevan `template=pb-9b19a89`. Agregar un caso con `<!-- wow: manifest-hash={H} -->` (sin plantilla) que da `"stale"`, y un test de `pending_items`:

```python
    def test_template_id_required(self):
        project = make_project()
        write(project, "wow/pb/prd.md", f"<!-- wow: manifest-hash={H} template=pb-9b19a89 -->\n")
        write(project, "wow/pb/rfc.md", f"<!-- wow: manifest-hash={H} -->\n")
        status = repo.packet_status(project, H, [])
        self.assertEqual((status["prd"], status["rfc"]), ("ok", "stale"))

    def test_pending_items(self):
        project = make_project()
        write(project, "wow/context-pack/pending-owner.md", "- [ ] North Star\n- [x] SLA\n  - [ ] rollout\n")
        self.assertEqual(repo.pending_items(project), ["North Star", "rollout"])
```

En `tests/test_state.py`, `project_at_phase_3()` usa `pb_ready_doc()` en vez de `valid_doc()`, escribe `.spec-kit/discovery/architecture.md` y genera los tres paquetes con `pack.render_*` más `pbfill.fill(...)`:

```python
    brief = pack.parse_brief("## Brief\n- Goal: x\n- Open questions: none\n")
    texts = {"prd": pack.render_prd(doc, brief, h), "rfc": pack.render_rfc(doc, brief, h),
             "epic-E1": pack.render_epic(doc, "E1", h)}
    for name, text in texts.items():
        write(p, f"wow/pb/{name}.md", fill(text))
```

El test de la línea ~90, que escribe un `epic-E1.md` con un hash viejo, sigue esperando "stale".

- [ ] **Step 2: Correr y verificar que falla** — `render_prd() got an unexpected keyword argument 'pending'` y las aserciones de forma.

- [ ] **Step 3: Implementar**

`wow/sources/repo.py`:

```python
import pbtemplate

TEMPLATE_RE = re.compile(r"template=(pb-[0-9a-f]{7})")
_PENDING_RE = re.compile(r"^\s*-\s*\[ \]\s*(.+?)\s*$")


def pending_items(project: Path) -> List[str]:
    path = project / "wow" / "context-pack" / "pending-owner.md"
    if not path.is_file():
        return []
    return [m.group(1) for m in map(_PENDING_RE.match, path.read_text(encoding="utf-8").splitlines()) if m]
```

En `_packet(path, mhash)`, después de leer el texto: si `HASH_RE` coincide con `mhash` pero `TEMPLATE_RE` no aparece o es distinto de `pbtemplate.TEMPLATE_ID`, devolver `"stale"`.

`wow/pack.py`: reemplazar `render_prd`, `render_rfc`, `render_epic`, `PREAMBLE`, `_header`, `_fill`, `_or_undefined` y `_questions` por lo siguiente. Quedan sin cambios `parse_brief`, `write_packet`, `ensure_preamble`, `UNDEFINED` y `_BRIEF_KEYS`.

```python
import pbcompletion
import pbtemplate

PREAMBLE = """Reglas para este documento (aplicalas en todas las secciones):
1. Usá solo la información de este chat y de los documentos que adjunto. Si un dato no está,
   escribí [SIN DEFINIR] y agregalo a "Preguntas abiertas". No lo completes con ejemplos genéricos ni con TODO.
2. Conservá las etiquetas [MEDIDO], [ESTIMACIÓN] y [SIN DEFINIR] tal como vienen.
3. Las filas de la plantilla pensadas para un marketplace (comprador, vendedor) se completan con
   "No aplica: <motivo>" si este dominio no las tiene; no adaptes el dominio a la plantilla.
4. Las secciones "API Gateway" y "SLA" se completan con la verdad: "No aplica: <motivo>" o [SIN DEFINIR].
   No agregues componentes, proveedores, SLAs, circuit breakers, North Star con targets, plazos ni owners
   que no figuren en el material.
5. Las decisiones pendientes del owner van a "Preguntas abiertas", no se resuelven por inferencia.
   En cada fila, Owner es el rol que decide (no inventes personas) y Estado es "Abierta".
6. Conservá los ids de los criterios (AC1, E1.C1…) tal como vienen.
7. Antes de dar una sección por completa, listá las afirmaciones que no tienen fuente en el material.
   No marques un ítem del checklist como cumplido sin citar dónde se cumple.
"""

OWNER_ROLE = "Owner de producto"
INITIATIVE_TYPE = {"brownfield": "Evolución de sistema existente", "greenfield": "Iniciativa nueva"}
PRIORITY_ES = {"high": "Alta", "medium": "Media", "low": "Baja"}
_NONE = ("", "none", "ninguna", "ninguno")


def _header(mhash: str, command: str) -> str:
    return f"<!-- wow: manifest-hash={mhash} template={pbtemplate.TEMPLATE_ID} · generated by `{command}` -->"


def _items(value: str) -> List[str]:
    parts = [p.strip() for p in re.split(r"[·;]", value or "")]
    return [p for p in parts if p.lower() not in _NONE]


def _sub(text: str, values: Dict[str, str]) -> str:
    for name, value in values.items():
        text = re.sub(r"\{\{\s*" + re.escape(name) + r"\s*\}\}", lambda _m, v=value: v, text)
    return text


def _rows(text: str, prefix: str, items: List[Dict[str, str]]) -> str:
    """Replace the template rows of a numbered group with one row per item; unknown cells keep a placeholder."""
    if not items:
        return text
    pattern = re.compile(r"\{\{\s*" + re.escape(prefix) + r"_(\d+)(?:_([a-z0-9_]+))?\s*\}\}")
    lines = text.split("\n")
    positions = [i for i, line in enumerate(lines) if pattern.search(line)]
    if not positions:
        return text
    template_row = lines[positions[0]]
    rows = []
    for n, item in enumerate(items, 1):
        def cell(match, n=n, item=item):
            sub = match.group(2) or ""
            return item.get(sub) or "{{%s_%d%s}}" % (prefix, n, f"_{sub}" if sub else "")
        rows.append(re.sub(r"^\|\s*1\s*\|", f"| {n} |", pattern.sub(cell, template_row)))
    return "\n".join(lines[:positions[0]] + rows + lines[positions[-1] + 1:])


def _open_questions(brief: Dict[str, str], pending, owner_role: str) -> Optional[str]:
    questions = _items(brief["Open questions"]) + list(pending)
    if questions:
        return "\n".join(f"| {n} | {q} | {owner_role} | Abierta |" for n, q in enumerate(questions, 1))
    if brief["Open questions"].strip().lower() in _NONE[1:]:
        return f"| 1 | Ninguna | {owner_role} | Cerrada |"
    return None


def render_prd(doc: dict, brief: Dict[str, str], mhash: str, pending=(), owner_role: str = OWNER_ROLE) -> str:
    plan = doc["plan"]
    values = {"title": plan["title"], "prd_status": "Borrador"}
    if plan.get("mode") in INITIATIVE_TYPE:
        values["initiative_type"] = INITIATIVE_TYPE[plan["mode"]]
    if brief["Goal"].strip():
        values["executive_summary"] = brief["Goal"].strip()
    requirements = []
    for epic in doc["epics"]:
        requirements.append(f"**{epic['id']} — {epic['title']}**")
        requirements += [f"- {item}" for item in epic["done_when"]]
        requirements += [f"- {t['id']} {t['title']}: " + "; ".join(t["acceptance"]) for t in epic["tasks"] if t["acceptance"]]
    values["key_requirements"] = "\n".join(requirements)
    questions = _open_questions(brief, pending, owner_role)
    if questions:
        values["open_questions"] = questions
    text = _sub(pbtemplate.load("prd"), values)
    text = _rows(text, "in_scope", [{"name": f"{e['id']}: {e['title']}", "description": "; ".join(e["done_when"]) or e["title"]}
                                    for e in doc["epics"]])
    text = _rows(text, "out_scope", [{"name": item} for item in _items(brief["Non-goals"])])
    return _header(mhash, "wow pack prd") + "\n" + text


def render_rfc(doc: dict, brief: Dict[str, str], mhash: str, pending=(), owner_role: str = OWNER_ROLE) -> str:
    plan = doc["plan"]
    values = {"title": plan["title"], "status": "Borrador", "version": "0.1"}
    if brief["Goal"].strip():
        values["executive_summary"] = brief["Goal"].strip()
    if plan.get("mode") == "greenfield":
        values["coexistence_strategy"] = "No aplica: sistema nuevo; no convive con un sistema previo."
    questions = _open_questions(brief, pending, owner_role)
    if questions:
        values["open_questions"] = questions
    text = _sub(pbtemplate.load("rfc"), values)
    text = _rows(text, "goal", [{"": item} for epic in doc["epics"] for item in epic["done_when"]])
    text = _rows(text, "non_goal", [{"": item} for item in _items(brief["Non-goals"])])
    milestones = []
    for epic in doc["epics"]:
        estimates = [t["estimate"] for t in epic["tasks"]]
        eta = f"{sum(estimates)} story points" if all(e is not None for e in estimates) else ""
        milestones.append({"phase": epic["id"], "deliverable": epic["title"], "eta": eta})
    text = _rows(text, "milestone", milestones)
    return _header(mhash, "wow pack rfc") + "\n" + text


def _ph(key: str) -> str:
    return "{{" + key + "}}"


def render_epic(doc: dict, epic_id: str, mhash: str) -> str:
    epic = next((e for e in doc["epics"] if e["id"] == epic_id), None)
    if epic is None:
        raise ValueError(f"epic {epic_id} not found in the manifest")
    product = dict(epic.get("product") or {})
    key = doc["plan"]["export"]["epics"].get(epic_id)
    tasks = epic["tasks"]
    stories = {t["id"]: f"US-{n:03d}" for n, t in enumerate(tasks, 1)}
    scalar = {"epic_name": epic["title"], "status": "todo", "estimation_method": "story_points"}
    if key:
        scalar["jira_prefix"] = key.split("-")[0]
    if "big_move" in product:
        scalar["big_move"] = "Sí" if product["big_move"] else "No"
    for field, _ in pbcompletion.EPIC_FIELDS:
        if field in product and field != "big_move":
            scalar[field] = product[field]
    closing = "Criterios de cierre de la épica: " + "; ".join(epic["done_when"]) if epic["done_when"] else ""
    scalar["notes"] = " ".join(p for p in (product.get("notes", ""), closing) if p) or _ph("notes")
    lists = {field: list(product.get(field) or []) for field, _ in pbcompletion.EPIC_LISTS}
    lists["labels"] = lists["labels"] or sorted({l for t in tasks for l in t["labels"]})
    lists["components"] = lists["components"] or sorted({t["component"] for t in tasks if t.get("component")})
    lines = [_header(mhash, f"wow pack epic --id {epic_id}"), f"# Épica {epic_id} — {epic['title']}", "",
             "## Datos de la épica", "| Campo | Valor |", "| --- | --- |"]
    lines += [f"| {label} ({field}) | {scalar.get(field) or _ph(field)} |" for field, label in pbcompletion.EPIC_FIELDS]
    for field, label in pbcompletion.EPIC_LISTS:
        lines += ["", f"### {label} ({field})"] + ([f"- {v}" for v in lists[field]] or [f"- {_ph(field)}"])
    lines += ["", "## Historias"]
    for task in tasks:
        story = dict(task.get("story") or {})
        component = task.get("component") or _ph("component")
        values = {"story_points": str(task["estimate"]) if task["estimate"] is not None else "",
                  "priority": PRIORITY_ES.get(task["priority"] or "", ""), "component": task.get("component", ""),
                  "status": "todo"}
        values.update({k: v for k, v in story.items() if isinstance(v, str)})
        lines += ["", f"### {stories[task['id']]} — [{component}] {task['title']} (tarea {task['id']})",
                  "| Campo | Valor |", "| --- | --- |"]
        lines += [f"| {label} ({field}) | {values.get(field) or _ph(field)} |" for field, label in pbcompletion.STORY_FIELDS]
        story_lists = {k: list(story.get(k) or []) for k in ("assumptions", "business_rules", "edge_cases", "assets")}
        story_lists["dependencies"] = [f"{stories[d]} (tarea {d})" if d in stories else f"{d} (otra épica)"
                                       for d in task["depends_on"]] or ["Ninguna"]
        story_lists["acceptance_criteria"] = [a.replace(": ", " — ", 1) for a in task["acceptance"]]
        story_lists["definition_of_ready"] = list(pbcompletion.DOR)
        story_lists["definition_of_done"] = [f"{c} — no" for c in pbcompletion.DOD]
        story_lists["tasks"] = []
        for sub in task["subtasks"]:
            sub = {"title": sub} if isinstance(sub, str) else sub
            story_lists["tasks"].append(
                f"{sub['title']} — Propósito: {sub.get('purpose') or _ph('purpose')} — Cómo: {sub.get('how_to') or _ph('how_to')}"
                f" — Componente: {sub.get('component') or component} — Estado: todo")
        for field, label in pbcompletion.STORY_LISTS:
            lines += ["", f"#### {label} ({field})"] + ([f"- {v}" for v in story_lists[field]] or [f"- {_ph(field)}"])
    lines.append("")
    return "\n".join(lines)
```

> Nota: hay que importar `Optional` en `pack.py`. Las tasks de una historia sin subtareas quedan como `- {{tasks}}`, que es lo que el Tech Lead completa.

`wow/cli.py`, en `_cmd_pack`: `pending = repo_src.pending_items(project)`, que se pasa a `render_prd` y `render_rfc`.

- [ ] **Step 4: Correr ambas suites** — exit 0. Si `test_state` tiene otras aserciones que dependían del paquete "ok" con solo el hash, ajustalas al fixture nuevo y registralo como Ruling.

- [ ] **Step 5: Commit (solo con ambas suites en 0)** — `feat(pack): render packets with the real Product Brain templates and mark old packets stale`

---

### Task 5: auditoría y cierre de chat alineados con PB

**Files:**
- Modify: `wow/pbaudit.py`, `wow/sources/pbchat.py`, `tests/test_pbaudit.py`, `tests/test_pbchat.py`

**Interfaces:**
- Produces:
  - `pbaudit.KNOWN_INVENTIONS` suma `("circuit breaker", r"\bcircuit[ -]?breakers?\b")` y `("Kong", r"\bkong\b")`.
  - `pbaudit._supporting_text(text) -> str`: saca encabezados y cláusulas con negación ("no hay", "no es", "no existe", "no usa", "no aplica", "inexistente", "sin").
  - `pbaudit.AUTHORITATIVE_RE = re.compile(r"\*\*Completitud del documento:\*\*\s*(\d{1,3})\s*%")`: `completion_pct` toma el último valor y, si no hay ninguno, cae en el regex anterior.
  - `pbchat.parse_chat`: `closed` es verdadero con la línea autoritativa al 100%, con "(llega|documento|completitud) … 100%" o con una frase de cierre. Un "100%" suelto ya no cierra.

- [ ] **Step 1: Escribir el test que falla**

Agregar a `tests/test_pbaudit.py`:

```python
class TemplateAwareAuditTest(unittest.TestCase):
    def test_template_heading_and_negation_do_not_whitelist(self):
        packet = "### API Gateway\n| Tecnologia | No aplica: no hay API Gateway |\n### SLA\n[SIN DEFINIR] — no hay SLA acordado\n"
        project = make_project()
        write(project, "wow/pb/rfc.md", packet)
        write(project, "wow/pb/chats/rfc.md", "Usamos Kong como API Gateway con circuit breaker y un SLA de 99,9%.\n")
        terms = [i["term"] for i in pbaudit.audit(project, "rfc")["inventions"]]
        self.assertEqual(terms, ["API Gateway", "SLA", "circuit breaker", "Kong"])

    def test_authoritative_completion_wins(self):
        project = make_project()
        write(project, "wow/pb/chats/prd.md", "El PRD llega al 100%.\n**Completitud del documento:** 96% · Pendiente: Metadata\n")
        self.assertEqual(pbaudit.audit(project, "prd")["completion_pct"], 96)
```

En `tests/test_pbchat.py`, agregar y mantener los tests existentes (que siguen pasando):

```python
    def test_bare_hundred_percent_does_not_close(self):
        self.assertFalse(pbchat.parse_chat("Requerimos 100% de disponibilidad")["closed"])
        self.assertTrue(pbchat.parse_chat("**Completitud del documento:** 100% (documento completo).")["closed"])
```

- [ ] **Step 2: Correr y verificar que falla** — inventos incompletos, 100 en vez de 96 y un chat cerrado de más.

- [ ] **Step 3: Implementar**

`wow/sources/pbchat.py`:

```python
CLOSED_RE = re.compile(
    r"\*\*Completitud del documento:\*\*\s*100\s*%"
    r"|\b(?:llega|documento|completitud)\b[^\n]{0,20}\b100\s*%"
    r"|\b(?:dalo|damos|doy|lo doy)\s+por\s+cerrad[oa]|\bpor\s+cerrad[oa]", re.IGNORECASE)
```

`wow/pbaudit.py`:
- agregar los dos inventos a `KNOWN_INVENTIONS`;
- agregar `no aplica` a `_NEGATION_RE`;
- definir `AUTHORITATIVE_RE`;
- en `audit`, reemplazar `allowed = _allowed_text(project, doc)` por `allowed = _supporting_text(_allowed_text(project, doc))`;
- hacer que `percents` prefiera `AUTHORITATIVE_RE`:

```python
AUTHORITATIVE_RE = re.compile(r"\*\*Completitud del documento:\*\*\s*(\d{1,3})\s*%")


def _supporting_text(text: str) -> str:
    """Text that can support a term: no headings and no negated clauses ("No aplica: no hay API Gateway")."""
    kept = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        kept += [c for c in _CLAUSE_RE.split(line.replace("|", ".")) if not _NEGATION_RE.search(c)]
    return "\n".join(kept)
```

```python
    authoritative = [int(m) for m in AUTHORITATIVE_RE.findall(text) if int(m) <= 100]
    percents = authoritative or [int(m) for m in _COMPLETION_RE.findall(text) if int(m) <= 100]
```

- [ ] **Step 4: Correr ambas suites** — exit 0.

- [ ] **Step 5: Commit (solo con ambas suites en 0)** — `fix(pb-audit): ignore template headings and negations, prefer Product Brain's authoritative completion`

---

### Task 6: modo en el estado, discovery brownfield y % del paquete en el snapshot y el dashboard

**Files:**
- Modify: `wow/state.py`, `wow/evidence.py`, `dashboard/wow-dashboard.html`, `dashboard/examples/partial.json`, `dashboard/examples/full.json`, `tests/test_state.py`, `tests/test_evidence.py`, `tests/test_dashboard.py`

**Interfaces:**
- Consumes: `pbcompletion.check_file` (Task 3) y `repo.packet_status` (Task 4).
- Produces:
  - **Estado, fase 1:** si el manifiesto no tiene `plan.mode`, agrega el paso `set the plan mode` (harness, `wow plan init --mode` o editar `plan.mode`).
  - **Estado, fase 0 brownfield:** si falta `.spec-kit/discovery/architecture.md`, agrega `run Spec-Kit discovery on the existing code` (cursor, `models["cursor_reason"]`, `/spec-kit.discovery`). Es un paso, no un bloqueo de fase.
  - **Estado, fase 2:** un paquete "ok" con predicción menor a 100% o con errores agrega `complete the <name> packet` (harness, `models["author"]`, `wow-pack, then wow pack check …`, con el motivo `predicted completion N%, E error(s)`) y deja el plan en fase 2.
  - **Evidencia:** cada entrada de `pb_status` suma `packet_pct` y `packet_errors` (`None` si no hay paquete).
  - **Dashboard:** la columna "Packet (predicted)" del panel Product Brain se muestra aunque no haya copia del chat.

- [ ] **Step 1: Escribir el test que falla**

Agregar a `tests/test_state.py`:

```python
class ModeStepsTest(unittest.TestCase):
    def test_missing_mode_and_brownfield_discovery_steps(self):
        p = make_project()
        write(p, "wow/context-pack/facts.md", "x")
        write(p, "wow/context-pack/pending-owner.md", "")
        manifest.save(p, valid_doc())
        actions = [s["action"] for s in state.compute_state(p, CFG)["next_steps"]]
        self.assertIn("set the plan mode", actions)
        from test_manifest import pb_ready_doc
        manifest.save(p, pb_ready_doc())
        steps = state.compute_state(p, CFG)["next_steps"]
        discovery = [s for s in steps if s["action"] == "run Spec-Kit discovery on the existing code"]
        self.assertEqual(discovery[0]["where"], "cursor")
        self.assertEqual(discovery[0]["command"], "/spec-kit.discovery")
```

> Nota: la guía devuelve como máximo 3 pasos, con Cursor al final. Si el paso de discovery queda fuera del recorte, el test debe mirar `plan["missing"]`, que conserva todas las acciones del plan. Registralo como Ruling si hace falta.

Agregar a `tests/test_evidence.py`:

```python
class PacketPctTest(unittest.TestCase):
    def test_packet_pct(self):
        import pbtemplate
        project = make_project()
        write(project, "wow/pb/prd.md", pbtemplate.load("prd"))
        out = evidence.pb_status(project, [])
        self.assertEqual((out["prd"]["packet_pct"], out["rfc"]["packet_pct"]), (0, None))
```

En `tests/test_dashboard.py` (`RenderTest`), sumar `"Packet (predicted)"` a las agujas de `full`.

- [ ] **Step 2: Correr y verificar que falla.**

- [ ] **Step 3: Implementar**

`wow/state.py`: `import pbcompletion`.
- **Modo y discovery:** después de cargar el manifiesto válido (`doc is not None`), con `mode = doc["plan"].get("mode")`:

```python
        if mode not in manifest.MODES:
            steps.append(_step(None, 1, "set the plan mode", "harness", models["author"],
                               "wow plan init --mode greenfield|brownfield (or edit plan.mode)",
                               "greenfield and brownfield change phase 0 and the packet prompts"))
        elif mode == "brownfield" and not (project / ".spec-kit" / "discovery" / "architecture.md").is_file():
            steps.append(_step(None, 0, "run Spec-Kit discovery on the existing code", "cursor",
                               models["cursor_reason"], "/spec-kit.discovery",
                               "brownfield plans cite the real architecture from .spec-kit/discovery/architecture.md"))
```

- **Paquetes incompletos:** en el bucle de la fase 2, cuando `status == "ok"`:

```python
            if status == "ok":
                check = pbcompletion.check_file(project, name)
                if check and (check["percentage"] < 100 or check["errors"]):
                    plan["phase"] = min(plan["phase"], 2)
                    target = f"epic --id {eid}" if eid else kind
                    steps.append(_step(None, 2, f"complete the {name} packet", "harness", models["author"],
                                       f"wow-pack, then wow pack check {target}",
                                       f"predicted completion {check['percentage']}%, {len(check['errors'])} error(s)"))
                continue
```

`wow/evidence.py`: `import pbcompletion`. En `PB_KEYS` sumar `"packet_pct", "packet_errors"`. En `pb_status`, después de armar `entry`:

```python
        check = pbcompletion.check_file(project, doc)
        entry["packet_pct"] = check["percentage"] if check else None
        entry["packet_errors"] = len(check["errors"]) if check else None
```

Actualizar `tests/test_evidence.py::PbStatusTest` para que los dicts esperados incluyan `"packet_pct": None, "packet_errors": None`.

`dashboard/wow-dashboard.html`, `productBrain`: encabezado `<th class="num">Packet (predicted)</th>` después de `Document`. Cada fila arranca con `<td class="num">${isNum(s.packet_pct) ? `${s.packet_pct}%` : "—"}${s.packet_errors ? ` · ${s.packet_errors} error(s)` : ""}</td>`. La fila sin chat usa `colspan="6"` para la nota.

En `dashboard/examples/full.json`, agregar `"packet_pct": 100, "packet_errors": 0` a cada entrada de `pb`. En `partial.json`, `epic-E1` lleva `"packet_pct": 87, "packet_errors": 1` y las demás entradas `100, 0`.

- [ ] **Step 4: Correr ambas suites** — exit 0.

- [ ] **Step 5: Commit (solo con ambas suites en 0)** — `feat(state): plan mode, brownfield discovery step and packet completion in state, snapshot and dashboard`

---

### Task 7: prompts, skills y documentación

**Files:**
- Modify: `skills/wow-pack/references/brownfield-prd.md`, `brownfield-rfc.md`
- Create: `skills/wow-pack/references/greenfield-prd.md`, `greenfield-rfc.md`, `epic.md`
- Modify: `skills/wow-pack/SKILL.md`, `skills/wow-plan/SKILL.md`, `skills/wow-context/SKILL.md`, `README.md`, `reference/product-brain/README.md`, `docs/superpowers/specs/2026-10-01-wayofwork-design.md`, `tests/test_cli.py`

**Interfaces:**
- **Prompts:** operan sobre `wow/pb/<doc>.md` generado por `wow pack`: completan solo los `{{campos}}` y terminan con `wow pack check …` en exit 0. No copian la plantilla y citan `.spec-kit/discovery/architecture.md`.
- **Skills:** `wow-pack` elige el prompt por `plan.mode`.

- [ ] **Step 1: Escribir el test que falla** (agregar a `tests/test_cli.py`)

```python
class ReferencesContractTest(unittest.TestCase):
    def test_prompts_exist_follow_the_packet_and_cite_the_real_discovery_path(self):
        base = ROOT / "skills/wow-pack/references"
        for name in ("brownfield-prd.md", "brownfield-rfc.md", "greenfield-prd.md", "greenfield-rfc.md", "epic.md"):
            text = (base / name).read_text(encoding="utf-8")
            self.assertIn("wow pack check", text, name)
            self.assertNotIn("discovery/architecture.md`", text.replace(".spec-kit/discovery/architecture.md`", ""), name)
            self.assertNotIn("TEMPLATE (fill it)", text, name)
        skill = (ROOT / "skills/wow-pack/SKILL.md").read_text(encoding="utf-8")
        for name in ("brownfield-prd.md", "greenfield-prd.md", "epic.md"):
            self.assertIn(name, skill)
```

- [ ] **Step 2: Correr y verificar que falla.**

- [ ] **Step 3: Escribir los prompts.** Instrucciones en inglés, salida en castellano. Los cinco comparten esta estructura:
- **Fuente de verdad:** cita `reference/product-brain/README.md`.
- **Cómo puntúa PB:** cualquier texto llena un campo; cada tabla cuenta como una unidad; las preguntas abiertas necesitan pregunta, owner y estado.
- **INPUTS:** los del modo.
- **RULES:** las reglas 1–11 de los prompts actuales, adaptadas. La regla 2 pasa a ser: "Edit `wow/pb/<doc>.md` in place. Replace every `{{placeholder}}`; never rename, reorder or remove headings, tables or columns; keep the first header line."
- **CHECKLIST:** la Fase 3 de PB más los gates del modo.
- **Cómo pegarlo en PB.**

Cierre común: "Run `wow pack check <prd|rfc|epic --id E<n>>` and fix the packet until it exits 0. Then paste `wow/pb/preamble.md` and the packet."

Diferencias por archivo:

| Archivo | Fuentes y énfasis |
|---|---|
| `brownfield-prd.md` | El context pack con `[MEDIDO]` y `fuente: path:line`, `.spec-kit/discovery/architecture.md` y el código. "Contexto" describe el sistema actual con citas de archivo; "Problema", el dolor medido; los baselines van `[MEDIDO]` |
| `brownfield-rfc.md` | Lo mismo, más "Hoy / Cambio" en cada sección. **Coexistencia y Fallback** es obligatoria. Las APIs citan handler y DTO o llevan `[TBD - verificar en código/Swagger]`. Indexar los repos en PB |
| `greenfield-prd.md` | El Brief, las notas de discovery en el repo y las decisiones del owner. Los baselines suelen ser `[SIN DEFINIR] — se mide desde el lanzamiento`; los usuarios son roles objetivo, no actuales; "Contexto" es el mercado o proceso actual sin código |
| `greenfield-rfc.md` | Arquitectura propuesta con alternativas abiertas. "Coexistencia y Fallback" ya viene como "No aplica: sistema nuevo"; "Repositorios" y "Componentes", los que se van a crear; no hay contratos verificados, así que las APIs propuestas se marcan "(propuesta)" |
| `epic.md` (ambos modos) | Completa `wow/pb/epic-E<n>.md`. Las historias usan "Como… quiero… para…". Los criterios en Gherkin conservan el `AC1 —`. Componente: `FE`, `BE`, `BO`, `QA`, `DEVOPS`, `INFRA`, `BFF` o `AI`. Story points Fibonacci; más de 8 se divide. DoR y DoD sin tocar (el DoD empieza en "no"). Cada task con Propósito y Cómo, citando endpoints y tablas del RFC. Una lista sin elementos se escribe "Ninguno" o "Ninguna", nunca vacía, porque una lista vacía deja la historia parcial. Un enum o una fecha desconocidos quedan como `{{campo}}`, porque `[SIN DEFINIR]` rompe la exportación a Jira; se escalan al owner |

- [ ] **Step 4: Actualizar las skills y la documentación**

`skills/wow-pack/SKILL.md`:

```markdown
---
name: wow-pack
description: Generate the Product Brain packets (PRD, RFC and one per epic) in the exact shape of Product Brain's templates, fill their {{placeholders}} with the mode's prompt, and verify locally that Product Brain will score them 100%. Use before any Product Brain chat or when wow-guide recommends `wow pack`.
---

# wow-pack

## Steps

1. Run `wow manifest lint --pb`; fix the manifest first if it reports missing mode, components, stories or Gherkin.
2. Run `wow pack prd`, `wow pack rfc` and `wow pack epic --id E<n>` for each epic.
   Exit 1 means the packet exists: only use `--force` if you accept losing filled fields.
3. Fill every `{{placeholder}}` following the prompt for the plan mode (plan.mode in wow/plan/manifest.json):
   - brownfield: references/brownfield-prd.md, references/brownfield-rfc.md
   - greenfield: references/greenfield-prd.md, references/greenfield-rfc.md
   - every epic: references/epic.md
4. Run `wow pack check prd`, `wow pack check rfc` and `wow pack check epic --id E<n>` until each exits 0.
   The prediction uses Product Brain's own completion rules (reference/product-brain/README.md).
5. Tell the user to paste `wow/pb/preamble.md` first, then the packet, using model 3.1 Pro; for the RFC,
   index or attach the repositories in Product Brain so it verifies contracts against code.

## Rules

- Unknown text fields: `[SIN DEFINIR] — <what is missing and who decides>`, plus an open-question row.
- Unknown enums and dates in an epic stay as `{{field}}` and go to the owner: an invalid value breaks the Jira export.
- Never rename headings or remove template tables; Product Brain maps fields by structure.
```

`skills/wow-plan/SKILL.md`, paso 1: después de crear el plan, `wow plan init <id> --title "<t>" --mode greenfield|brownfield`. Paso 4: suma `component` (FE…AI), `story` (user_story_text "Como… quiero… para…", context, scope, out_of_scope, rules, edge_cases, assets, technical_info) y `product` por épica. Los criterios se escriben "AC1: Dado … Cuando … Entonces …". Paso 5: `wow manifest lint --pb`.

`skills/wow-context/SKILL.md`, en brownfield: las afirmaciones de arquitectura citan `.spec-kit/discovery/architecture.md` (generado por `/spec-kit.discovery`) o el código.

`README.md`, en el bloque de uso:

```bash
wow plan init 0001-x --title "X" --mode brownfield         # el modo cambia la fase 0 y los prompts
wow manifest lint --pb                                      # lo que Product Brain exige por historia
wow pack check prd | wow pack check epic --id E1           # predicción local del % de Product Brain
```

`reference/product-brain/README.md`, en "Pendiente": marcar lo implementado y anotar la ruta real de discovery. `docs/superpowers/specs/…design.md`: nueva sección `## 17. Adaptación a Product Brain real (2026-10-02)` que resume la tabla de redefiniciones de este plan.

- [ ] **Step 5: Correr ambas suites** — exit 0, incluido `AllSkillsContractTest` (máximo 80 líneas, comandos `wow` reales).

- [ ] **Step 6: Commit (solo con ambas suites en 0)** — `docs(skills): mode-aware Product Brain prompts and pack check workflow`

---

## Fuera de este plan

- Actualizar `docs/site/way-of-work.html` en el repo SPECKIT con el flujo nuevo.
- Plantillas de PB personalizadas por equipo: hoy se asume la plantilla base y el modo de detectar copias personalizadas queda pendiente.
- Caso de Negocio (`CASO_DE_NEGOCIO_TEMPLATE_CONTENT`): PB lo ofrece como contexto previo al PRD y no está en el flujo actual.
