# Dos flujos (PB y SK) con checklists y `wow sk run` — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** WoW lleva Product Brain y Spec-Kit como dos flujos independientes unidos solo por la clave de una épica de Jira, muestra un checklist por flujo (md y consola, con % de completitud, también en la statusline) y puede mandar comandos de Spec-Kit a Cursor desde Claude Code sin perder telemetría.

**Architecture:** El estado de Spec-Kit se extrae de `state._epic_state` a un módulo propio que arranca con cualquier clave de épica (exportada por PB, creada con `jk` o registrada con `wow sk start`). Un módulo de checklists deriva cada ítem de evidencia verificable, lo renderiza con una plantilla con placeholders y suma una sección manual que solo cuenta si trae evidencia. Manejar `cursor-agent` interactivo dentro de tmux (el único camino medido que dispara todos los hooks) vive en una skill atómica nueva, `Harness/run-in-cursor` (hermana de `jira-kanban`, con su propio repo, CLI `ric` y hook global de Cursor); `wow sk run` es un envoltorio fino que le agrega la regla de Spec-Kit.

**Tech Stack:** Python stdlib 3.9+ (WoW), unittest, tmux, `cursor-agent` 2026.10.01, ccstatusline (custom-command widget).

**Spec:** la conversación del 2026-10-06 y la medición guardada en Engram (`discovery/cursor-agent-headless-telemetry`); este plan resume las decisiones del usuario:
1. Dos flujos independientes; el contrato entre ellos es la clave de épica.
2. Checklist por flujo en md y consola con %; tildes derivadas de evidencia más ítems manuales con evidencia.
3. El % visible en cada prompt vía statusline.
4. `wow guide` queda como resumen de los dos flujos.
5. `/spec-kit.sync-status` solo desde Cursor; el resto se puede mandar desde acá, y el usuario puede seguir corriendo cualquier comando en Cursor.

## Global Constraints

- Python 3.9+ stdlib, sin dependencias; la suite pasa con `python3` y `/usr/bin/python3` (3.9).
- Código, mensajes del CLI y skills en inglés; documentación para personas en castellano rioplatense.
- Conventional commits sin atribución a IA.
- `wow sk run` nunca usa `-p` y rechaza `sync-status` con exit 1.
- `wow progress --line` termina en menos de 1 s y no toca la red (ccstatusline corta a los 1000 ms: `ccstatusline.js:53032`).
- Nunca se imprime ni se copia una credencial (`IC_JIRA_*`, la key de New Relic de los binarios de Spec-Kit).
- Códigos de salida de WoW: 0 OK · 1 hallazgos · 2 no pude evaluar.

## Review Focus

1. Proyecto sin `wow/` (statusline en cualquier carpeta): `wow progress --line` imprime vacío y sale 0, sin traceback.
2. Máquina sin el hook global de run-in-cursor en `~/.cursor/hooks.json`: `ric run` no se queda esperando para siempre; avisa al lanzar (`ric install-hook`) y corta por timeout con exit 124.
3. Ítem manual tildado sin `evidencia:`: no suma al % y la consola lo nombra.
4. Jira no configurado o caído: el checklist marca los ítems que dependen de Jira como "sin verificar" (no hechos, no aplicables) y el resto se calcula igual.
5. Un comando con `sync-status` escondido en el texto (`'/spec-kit.sync-status specs/x'` con espacios o mayúsculas): `wow sk run` lo rechaza igual.

---

## Mapa de archivos

| Archivo | Responsabilidad |
|---|---|
| `wow/tmpl.py` (nuevo) | Motor de plantillas estricto (`{{name}}`, `{{?name}}`, `{{~name}}`), copia del de jira-kanban |
| `wow/templates/checklist.md` (nuevo) | Forma del checklist de un flujo |
| `wow/checklist.py` (nuevo) | `Item`, porcentaje, render, lectura de la sección manual |
| `wow/flow_pb.py` (nuevo) | Ítems del flujo PB a partir de las fuentes existentes |
| `wow/flow_sk.py` (nuevo) | Estado, pasos e ítems del flujo SK para una clave de épica |
| `wow/state.py` (modificar) | `_epic_state` delega en `flow_sk` apenas hay clave; suma épicas SK registradas |
| `wow/progress.py` (nuevo) | Escribe `wow/checklists/*.md` y `progress.json`; arma la línea de la statusline |
| `Harness/run-in-cursor/` (repo nuevo) | Skill atómica: `ric run|send|quit|install-hook|hook`, SKILL.md, README, install.sh, tests |
| `wow/skrun.py` (nuevo) | Envoltorio: rechaza `sync-status` y llama a `ric` |
| `wow/cli.py` (modificar) | `wow progress`, `wow sk start|run|send|quit` |
| `skills/wow-guide`, `skills/wow-sk-prep` (modificar) | Los dos flujos y `wow sk run` |
| `AGENTS.md` (WoW y SPECKIT), `README.md`, página de internals | Reglas nuevas y la fila medida |

---

### Task 1: Motor de plantillas y checklist

**Files:**
- Create: `wow/tmpl.py`, `wow/templates/checklist.md`, `wow/checklist.py`
- Test: `tests/test_checklist.py`

**Interfaces:**
- Produces: `tmpl.render(text: str, values: dict, escape=None) -> str`, `tmpl.load(name: str) -> str`, `tmpl.TemplateError`;
  `checklist.Item(id: str, label: str, state: str, evidence: str = "")` con `state` en `"done" | "todo" | "na" | "unverified"`;
  `checklist.percent(items: List[Item]) -> int`; `checklist.render(title: str, items: List[Item], manual: str) -> str`;
  `checklist.manual_items(text: str) -> List[Item]`; `checklist.manual_section(text: str) -> str`.

- [ ] **Step 1: Copiar el motor.** `wow/tmpl.py` es copia literal de `Harness/jira-kanban/jkan/template.py` (commit 4908d26), con `TEMPLATES = Path(__file__).resolve().parent / "templates"` y la primera línea del docstring: `"""Strict placeholder templates (same engine as jira-kanban's jkan/template.py; keep them in step)."""`.

- [ ] **Step 2: Plantilla** `wow/templates/checklist.md`:

```markdown
# {{title}}

Completitud: {{percent}}% ({{done}} de {{total}})

## Derivado

Lo tilda `wow progress` a partir de evidencia; editarlo a mano no cambia nada.

{{derived}}

## Manual

Tildá con `[x]` y escribí `evidencia: …` en la misma línea; sin evidencia no cuenta.

{{~manual}}
```

- [ ] **Step 3: Tests que fallan** `tests/test_checklist.py`:

```python
from __future__ import annotations

import unittest

from helpers import ROOT  # noqa: F401
import checklist
from checklist import Item


class PercentTest(unittest.TestCase):
    def test_not_applicable_items_leave_the_total(self):
        items = [Item("a", "A", "done"), Item("b", "B", "todo"), Item("c", "C", "na")]
        self.assertEqual(checklist.percent(items), 50)

    def test_unverified_counts_as_not_done(self):
        self.assertEqual(checklist.percent([Item("a", "A", "done"), Item("b", "B", "unverified")]), 50)

    def test_nothing_applicable_is_zero(self):
        self.assertEqual(checklist.percent([Item("a", "A", "na")]), 0)


class ManualTest(unittest.TestCase):
    TEXT = ("# x\n\n## Derivado\n\n- [x] A\n\n## Manual\n\nTildá con…\n\n"
            "- [x] Avisar al equipo — evidencia: mensaje en #plate 2026-10-06\n"
            "- [x] Probar en el navegador\n- [ ] Pedir acceso\n")

    def test_a_ticked_item_counts_only_with_evidence(self):
        items = checklist.manual_items(self.TEXT)
        self.assertEqual([(i.label, i.state) for i in items], [
            ("Avisar al equipo", "done"), ("Probar en el navegador", "todo"), ("Pedir acceso", "todo")])
        self.assertEqual(items[0].evidence, "mensaje en #plate 2026-10-06")

    def test_the_manual_section_survives_a_rewrite(self):
        kept = checklist.manual_section(self.TEXT)
        self.assertIn("- [ ] Pedir acceso", kept)
        out = checklist.render("Flujo PB", [Item("a", "A", "done")], kept)
        self.assertEqual(checklist.manual_section(out), kept)


class RenderTest(unittest.TestCase):
    def test_marks_and_percent(self):
        out = checklist.render("Flujo SK · PLATE-504", [
            Item("sync", "Sync de la épica", "done", "specs/001/spec.md"),
            Item("disc", "Discovery", "na", "greenfield"),
            Item("jira", "Historias en Done", "unverified", "jira no configurado")], "")
        self.assertIn("Completitud: 50% (1 de 2)", out)
        self.assertIn("- [x] Sync de la épica — specs/001/spec.md", out)
        self.assertIn("- [-] Discovery — no aplica: greenfield", out)
        self.assertIn("- [?] Historias en Done — sin verificar: jira no configurado", out)
```

Run: `python3 -m unittest discover -s tests -p 'test_checklist.py'` — Expected: ERROR `No module named 'checklist'`.

- [ ] **Step 4: Implementación** `wow/checklist.py`:

```python
"""A flow's checklist: items derived from evidence, plus manual ones that count only with written evidence."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

import tmpl

MARK = {"done": "[x]", "todo": "[ ]", "na": "[-]", "unverified": "[?]"}
PREFIX = {"done": "", "todo": "", "na": "no aplica: ", "unverified": "sin verificar: "}
_MANUAL = re.compile(r"^- \[([ xX])\]\s+(.*?)(?:\s+—\s+evidencia:\s*(.*))?$")


@dataclass
class Item:
    id: str
    label: str
    state: str
    evidence: str = ""


def percent(items: List[Item]) -> int:
    counted = [i for i in items if i.state != "na"]
    return round(100 * sum(i.state == "done" for i in counted) / len(counted)) if counted else 0


def manual_section(text: str) -> str:
    """The item lines under '## Manual', verbatim."""
    _, _, tail = (text or "").partition("\n## Manual\n")
    return "\n".join(line for line in tail.splitlines() if line.startswith("- [")).strip()


def manual_items(text: str) -> List[Item]:
    items = []
    for n, line in enumerate(manual_section(text).splitlines()):
        match = _MANUAL.match(line)
        if match:
            ticked, label, evidence = match.group(1).lower() == "x", match.group(2), (match.group(3) or "").strip()
            items.append(Item(f"manual-{n}", label, "done" if ticked and evidence else "todo", evidence))
    return items


def _line(item: Item) -> str:
    note = PREFIX[item.state] + item.evidence if item.evidence or PREFIX[item.state] else ""
    return f"- {MARK[item.state]} {item.label}" + (f" — {note}" if note else "")


def render(title: str, items: List[Item], manual: str) -> str:
    counted = [i for i in items if i.state != "na"]
    return tmpl.render(tmpl.load("checklist.md"), {
        "title": title, "percent": str(percent(items)), "done": str(sum(i.state == "done" for i in counted)),
        "total": str(len(counted)), "derived": "\n".join(_line(i) for i in items) or "- [-] Nada que verificar",
        "manual": manual}).rstrip("\n") + "\n"
```

Nota: `percent()` y `render()` reciben los ítems derivados más `manual_items(...)`; quien llama los concatena (Task 4).

- [ ] **Step 5:** Run `python3 -m unittest discover -s tests` y `/usr/bin/python3 -m unittest discover -s tests` — Expected: OK.
- [ ] **Step 6: Commit** `feat(checklist): derived and manual checklist items rendered from a template`.

---

### Task 2: Ítems del flujo PB

**Files:**
- Create: `wow/flow_pb.py`
- Test: `tests/test_flow_pb.py` (reusa `project_at_phase_3`, `FakeJira` y `summary` de `tests/test_state.py`)

**Interfaces:**
- Consumes: `repo.context_pack_status`, `manifest.load|validate|lint|manifest_hash`, `repo.packet_status`, `pbcompletion.check_file|ready`, `pbchat.chat_status`, `state.REVIEW_CLOSED`, `jira.epic_summary(key) -> {"exists","stories","done","story_keys","url"}`.
- Produces: `flow_pb.items(project: Path, cfg: dict, jira) -> List[checklist.Item]`.

Ítems, en orden (id → condición de `done`):
`context` (facts.md y pending-owner.md existen) · `owner` (sin decisiones abiertas) · `manifest` (valida y sin lint) · `readiness` (veredicto `approved`) · `packet-prd`, `packet-rfc`, `packet-<E>` por épica no draft (estado `ok` y `pbcompletion.ready`) · `chat-prd`, `chat-rfc`, `chat-<E>` (presente, cerrado y auditoría en `REVIEW_CLOSED`) · `export-<E>` (clave en `plan.export.epics`) · `stories-<E>` (Jira: `stories >= len(tasks)`; `unverified` si `jira is None` o `SourceUnavailable`) · `fix-fields-<E>` (alguna línea de `harness/jira-writes.jsonl` con `command` que empieza con `jira fix-fields` y `key` en `story_keys`; `unverified` sin Jira).
Sin manifest: solo `context`, `owner` y `manifest` en `todo`.

- [ ] **Step 1: Tests que fallan** (uno por regla; código completo):

```python
from __future__ import annotations

import json
import unittest

from helpers import make_project, write
import config
import flow_pb
from sources import SourceUnavailable
from test_state import FakeJira, project_at_phase_3, summary

CFG = config.DEFAULTS


def states(items):
    return {i.id: i.state for i in items}


class FlowPbTest(unittest.TestCase):
    def test_empty_project_asks_for_context_and_plan(self):
        got = states(flow_pb.items(make_project(), CFG, None))
        self.assertEqual(got, {"context": "todo", "owner": "todo", "manifest": "todo"})

    def test_exported_epic_with_all_stories_and_fixed_fields_is_done(self):
        p = project_at_phase_3()
        write(p, "harness/jira-writes.jsonl", json.dumps({"tool": "wow", "command": "jira fix-fields", "action": "update",
                                                          "key": "IRIS-41", "fields": {}}) + "\n")
        jira = FakeJira({"IRIS-40": dict(summary("IRIS-40", 1, 0), story_keys=["IRIS-41"])})
        got = states(flow_pb.items(p, CFG, jira))
        self.assertEqual(got["export-E1"], "done")
        self.assertEqual(got["stories-E1"], "done")
        self.assertEqual(got["fix-fields-E1"], "done")

    def test_without_jira_the_jira_items_are_unverified_not_failed(self):
        got = states(flow_pb.items(project_at_phase_3(), CFG, None))
        self.assertEqual(got["stories-E1"], "unverified")
        self.assertEqual(got["fix-fields-E1"], "unverified")

    def test_jira_down_is_unverified_too(self):
        got = states(flow_pb.items(project_at_phase_3(), CFG, FakeJira(error="jira: timeout")))
        self.assertEqual(got["stories-E1"], "unverified")
```

Antes de escribir el test 2, leé `project_at_phase_3` en `tests/test_state.py:33-60` y ajustá la épica (`E1`), la clave (`IRIS-40`) y la cantidad de tareas del manifest a lo que ese helper arma; si tiene más de una tarea, poné `summary("IRIS-40", <n>, 0)` con ese `n`.

Run: `python3 -m unittest discover -s tests -p 'test_flow_pb.py'` — Expected: ERROR `No module named 'flow_pb'`.

- [ ] **Step 2: Implementación** `wow/flow_pb.py`: una función `items()` que recorre las reglas de arriba en orden, con un helper `_jira_summary(jira, key)` que devuelve `(summary | None, motivo)` atrapando `SourceUnavailable`, y `_fixed(project, story_keys)` que lee `harness/jira-writes.jsonl` línea por línea ignorando JSON inválido. Cada ítem lleva en `evidence` el archivo, la clave o el motivo (por ejemplo `wow/pb/prd.md 100%`, `IRIS-40`, `jira no configurado`). Reutilizá exactamente las mismas llamadas que `state.compute_state` (`state.py:44-118`) para que el checklist y los pasos nunca discrepen.
- [ ] **Step 3:** suites 3.14 y 3.9 — Expected: OK.
- [ ] **Step 4: Commit** `feat(flow-pb): the Product Brain flow as a checklist derived from its sources`.

---

### Task 3: Flujo SK independiente

**Files:**
- Create: `wow/flow_sk.py`
- Modify: `wow/state.py:139-260` (`_epic_state`) y `wow/state.py:118-131` (épicas registradas)
- Test: `tests/test_flow_sk.py`; ajustar los casos de `tests/test_state.py` que esperaban que una épica con clave siguiera en fase 3 por un chat sin auditar.

**Interfaces:**
- Consumes: `speckit.features(project)` (campos `dir, epic_key, has_plan, has_tasks, has_work_units, tasks_total, tasks_done, stories, pending_work_units, unchecked_tasks, units`), `sk.commands_for`, `estimate.suggest_model`, `state.review_final`, `state.REVIEW_CLOSED`.
- Produces:
  - `flow_sk.state(project, cfg, key, jira, expected: Optional[int] = None, ref: Optional[str] = None, mode: Optional[str] = None) -> {"phase": int|str, "progress": str|None, "reason": str|None, "jira_url": str|None, "steps": List[dict], "items": List[Item]}` — `ref` es el id para reviews (la épica del manifest, o la clave si no hay manifest); `expected` es la cantidad de historias del manifest o `None` (entonces alcanza con `stories > 0`).
  - `flow_sk.registered(project) -> List[str]` y `flow_sk.register(project, key) -> bool` sobre `wow/sk/epics.json` (`{"epics": ["PLATE-553"]}`).

Ítems SK por épica: `discovery` (`na` si `mode == "greenfield"`; `done` si existe `.spec-kit/discovery/architecture.md`) · `sync` (hay feature con esa `epic_key`) · `clarify` (`spec.md` contiene `## Clarifications` y `### Session`: `spec-kit.clarify.md:150-151` del clon de referencia 65a6940) · `plan` · `tasks` · `work-units` · `wu-<ID>` por cada id de `units` (`done` si no está en `pending_work_units`) · `review-<story>` por historia con todas sus tareas hechas · `jira-done` (rótulo `Historias en Done (sync-status, en Cursor)`) · `review-epic` · `epic-closed` (`summary["epic_done"]`; `unverified` sin Jira).

- [ ] **Step 1: Tests que fallan** en `tests/test_flow_sk.py`: (a) clave sin feature → paso `sync` con el comando de `sk.commands_for("sync", cfg, epic=key)[0]` e ítem `sync` en `todo`; (b) feature con `## Clarifications\n\n### Session 2026-10-06` → `clarify` en `done`; (c) `mode="greenfield"` → `discovery` en `na`; (d) `wow sk start PLATE-553` dos veces deja una sola entrada en `wow/sk/epics.json`; (e) `state.compute_state` sobre un proyecto **sin manifest** con `PLATE-553` registrada devuelve una épica `PLATE-553` con su fase SK. Armá los features con `write(p, "specs/001-x/spec.md", "**Jira Epic:** PLATE-553\n...")` y un `tasks.md` mínimo como en `tests/test_speckit.py`.
- [ ] **Step 2:** Run el archivo — Expected: ERROR `No module named 'flow_sk'`.
- [ ] **Step 3: Implementación.** Mover a `flow_sk.state` el cuerpo de `_epic_state` desde `if jira is None:` (`state.py:189`) hasta el final, cambiando `eid` por `ref` en reviews y pasos, `len(epic["tasks"])` por `expected`, y agregando la construcción de `items`. `_epic_state` queda con la fase 3 de PB solo mientras `key` es `None`; con clave llama a `flow_sk.state(project, cfg, key, jira, expected=len(epic["tasks"]), ref=eid, mode=doc["plan"].get("mode"))`. En `compute_state`, después del bucle de épicas del manifest, sumar `flow_sk.registered(project)` que no estén ya entre las claves exportadas, con `ref=key` y `expected=None`; y cuando no hay manifest, no cortar ahí: las épicas registradas se evalúan igual.
- [ ] **Step 4:** suites 3.14 y 3.9. Los tests de `test_state.py` que cambien de expectativa se actualizan en este mismo commit, con un comentario de una línea que diga por qué (el flujo SK ya no espera a la auditoría de PB).
- [ ] **Step 5: Commit** `feat(flow-sk): Spec-Kit runs from any Jira epic key, independent of Product Brain`.

---

### Task 4: `wow progress` y la línea de la statusline

**Files:**
- Create: `wow/progress.py`
- Modify: `wow/cli.py` (parser `progress` con `--line`; parser `sk start KEY`)
- Test: `tests/test_progress.py`

**Interfaces:**
- Consumes: `flow_pb.items`, `flow_sk.state`, `flow_sk.registered`, `checklist.*`, `state.compute_state` (para saber qué claves tiene el flujo SK).
- Produces: `progress.write(project, cfg, jira) -> dict` que escribe `wow/checklists/pb.md`, `wow/checklists/sk-<KEY>.md` y `wow/checklists/progress.json` (`{"pb": {"percent": int, "done": int, "total": int}, "sk": {"PLATE-553": {...}}, "manual_without_evidence": [str]}`) y devuelve ese dict; `progress.line(cwd: Path) -> str` que solo lee `progress.json` subiendo desde `cwd` hasta encontrar `wow/` y devuelve por ejemplo `PB 62% · SK PLATE-553 40%`, o `""`.

- [ ] **Step 1: Tests que fallan:** (a) `write` crea los tres archivos y `pb.md` contiene `Completitud:`; (b) una sección manual existente en `pb.md` sobrevive a `write` y un ítem tildado sin evidencia aparece en `manual_without_evidence`; (c) `line()` desde una subcarpeta del proyecto devuelve `PB …%`; (d) `line()` en una carpeta sin `wow/` devuelve `""`; (e) `run_cli(["progress", "--line"])` con stdin `{"workspace": {"current_dir": "<tmp sin wow>"}}` imprime vacío y sale 0 aunque el JSON venga roto.
- [ ] **Step 2:** Run — Expected: ERROR `No module named 'progress'`.
- [ ] **Step 3: Implementación.** `write` concatena ítems derivados y `checklist.manual_items(texto_anterior)` para el %, y renderiza con `checklist.render(title, derivados, checklist.manual_section(texto_anterior))`. El CLI: `wow progress` llama `write` e imprime cada flujo como `Flujo PB  62%  (8 de 13)` seguido de sus ítems no hechos (`[ ]`/`[?]`) y de los manuales sin evidencia; `wow progress --line` lee `cwd` de `workspace.current_dir` (o `cwd`) del JSON de stdin, con `try/except` amplio que siempre sale 0. `wow sk start KEY` llama `flow_sk.register` e imprime `tracking KEY` o `already tracked KEY`.
- [ ] **Step 4:** suites 3.14 y 3.9; además medir `time wow progress --line < /dev/null` en este repo: debe quedar muy por debajo de 1 s.
- [ ] **Step 5: Commit** `feat(progress): wow progress writes the checklists and a one-line summary`.

---

### Task 5a: Skill `run-in-cursor` (repo propio, hermano de jira-kanban)

**Files (repo nuevo `Harness/run-in-cursor`, `git init`, sin remoto hasta que el usuario lo cree):**
- Create: `ric.py` (entrada), `ric/__init__.py`, `ric/hook.py`, `ric/session.py`, `ric/cli.py`, `SKILL.md`, `README.md` (castellano), `install.sh`, `.gitignore`, `tests/helpers.py`, `tests/test_hook.py`, `tests/test_session.py`, `tests/test_cli.py`

**Interfaces:**
- Produces (CLI, lo que consume WoW):
  - `ric run [--workspace DIR] [--model M] [--timeout S] [--deny REGEX]... "<prompt o /comando>"` → imprime `session: <S>`, `status: <completed|aborted|error|timeout>`, `tokens: in=<n> out=<n>` y la pantalla; exit 0 completed, 1 aborted/error/denegado, 124 timeout, 2 no puede (sin tmux o sin `cursor-agent`).
  - `ric send <S> "<texto>"` (mismas salidas, espera el turno nuevo), `ric quit <S>`, `ric install-hook [--hooks-file ~/.cursor/hooks.json]`, `ric hook` (lo llama Cursor).
- Produces (Python): `hook.record(payload: dict, log: Optional[str]) -> None`; `hook.install(path: Path, command: str) -> bool`; `session.denied(prompt: str, patterns: List[str]) -> Optional[str]`; `session.run(workspace, prompt, model=None, timeout=1800, tmux=_tmux, sleep=time.sleep, clock=time.monotonic) -> dict`; `session.send(...)`; `session.quit(name, tmux=_tmux) -> bool`.

Comportamiento medido que el código respeta (2026-10-06, `cursor-agent` 2026.10.01-e373342):
- Lanzar: `tmux new-session -d -s <S> -x 200 -y 50 -c <workspace> "RUN_IN_CURSOR_LOG=<log> cursor-agent --trust --force [--model M] '<prompt>'"`; `<S>` = `ric-<slug>-<HHMMSS>`; `<log>` = `<workspace>/.run-in-cursor/runs/<S>.jsonl`. Nunca `-p`.
- Las variables de entorno de la sesión llegan a los hooks (medido con `PROBE_RUN`), y Cursor ejecuta los hooks globales de `~/.cursor/hooks.json` en cualquier proyecto.
- El hook global (`stop` y `sessionEnd`) escribe una línea JSON en `$RUN_IN_CURSOR_LOG` solo si la variable existe (`{"event","status","model","input_tokens","output_tokens","reason","t"}`, nunca el prompt), imprime `{}` y nunca falla.
- Fin de turno: una línea nueva con `event == "stop"`; su `status` es el resultado.
- Pantalla: `tmux capture-pane -p -t <S>` sin líneas vacías ni de bordes (`▄`, `▀`).
- Salir: `send-keys -l /quit`, `Enter`, y otro `Enter` si `has-session` sigue en 0 (el primero lo toma el autocompletado); espera la línea `sessionEnd`.
- `.run-in-cursor/` va al `.gitignore` del workspace si es un repo (agregar la línea si falta, sin tocar el resto).

- [ ] **Step 1: Tests que fallan** con un `FakeTmux` que registra los argumentos y simula el hook escribiendo en el log:
  - `hook.record` sin `RUN_IN_CURSOR_LOG` no escribe nada; con la variable, escribe solo las claves de la lista (un payload con `prompt` no lo filtra).
  - `hook.install` agrega `stop` y `sessionEnd` como unión, sin pisar el hook `stop` de WoW ni los demás eventos, y es idempotente (segunda vez devuelve `False`).
  - `run` arma exactamente el `new-session` de arriba (comparar la lista) y devuelve `status == "completed"`, los tokens y la pantalla.
  - Nunca aparecen `-p` ni `--print` en los argumentos de ninguna llamada.
  - `denied("/spec-kit.sync-status x", ["spec-kit\\.sync-status"])` devuelve un motivo; con mayúsculas y espacios delante también; `denied("/spec-kit.plan", [...])` devuelve `None`.
  - Sin línea `stop` y con `clock` avanzando: `status == "timeout"`.
  - `quit` manda `/quit` literal y `Enter`, y un segundo `Enter` si la sesión sigue viva.
  - Sin hook instalado (archivo de hooks sin `ric hook`): `run` imprime el aviso `run "ric install-hook" first` y sigue (cortará por timeout).
- [ ] **Step 2:** `python3 -m unittest discover -s tests` — Expected: ERROR `No module named 'ric'`.
- [ ] **Step 3: Implementación** (polling cada 2 s con `sleep` inyectado; `send` lee el log desde el offset anterior). `install.sh` copia el esquema de `jira-kanban/install.sh` (symlinks en `~/.agents/skills/run-in-cursor`, `~/.claude/skills/run-in-cursor` y `~/.codex/skills/run-in-cursor`).
- [ ] **Step 4:** suites 3.14 y 3.9.
- [ ] **Step 5: `SKILL.md`** (inglés): cuándo usarla ("run this in Cursor", mandar un prompt o slash command a Cursor registrando la sesión), los pasos (`ric run`, leer la pantalla, `ric send` si pregunta, `ric quit` al final) y las reglas (nunca `-p`; los comandos que escriben afuera se pasan con `--deny` o los decide el usuario). README en castellano con la medición.
- [ ] **Step 6: Verificación real** en `scratchpad/probe`: `ric install-hook`, `ric run "/probe-cmd hola"`, `ric quit`; confirmar `status: completed`, tokens y `sessionEnd` en el log. Sin Spec-Kit en ese proyecto, así que no sale nada hacia New Relic.
- [ ] **Step 7: Instalar** con `./install.sh` y commit `feat: run-in-cursor, drive interactive cursor-agent from another agent and keep every hook`.

### Task 5b: `wow sk run`, `send` y `quit` sobre `ric`

**Files:**
- Create: `wow/skrun.py`
- Modify: `wow/cli.py` (subcomandos `sk run|send|quit`), `wow/sk.py:15-18` (docstring de `commands_for`)
- Test: `tests/test_skrun.py`

**Interfaces:**
- Consumes: la CLI `ric` de la Task 5a, ubicada en `~/.agents/skills/run-in-cursor/ric.py` (o `WOW_RIC` si está definida).
- Produces: `skrun.refuse(command: str) -> Optional[str]`; `skrun.argv(action: str, args: List[str]) -> List[str]`.

- [ ] **Step 1: Tests que fallan:** `refuse` rechaza `sync-status` (con espacios y mayúsculas) con un motivo que dice `run it in Cursor`, y cualquier cosa que no empiece con `/spec-kit.`; `argv("run", ["/spec-kit.plan x"])` arma `[sys.executable, <ric.py>, "run", "--workspace", <project>, "--deny", "spec-kit\\.sync-status", "/spec-kit.plan x"]`; sin `ric.py` en la ruta, `run_cli(["sk", "run", ...])` sale 2 con `install run-in-cursor`.
- [ ] **Step 2:** Run — Expected: ERROR `No module named 'skrun'`.
- [ ] **Step 3: Implementación**: el CLI llama `subprocess.run(skrun.argv(...))` sin capturar la salida (el usuario ve la pantalla) y devuelve su exit code.
- [ ] **Step 4:** suites 3.14 y 3.9.
- [ ] **Step 5: Commit** `feat(sk): wow sk run sends Spec-Kit commands to Cursor through run-in-cursor`.

---

### Task 6: Guardrail y statusline

**Files:**
- Modify: `~/.claude/hooks/git-guardrails.sh` (backup previo `git-guardrails.sh.bak-2026-10-06`)
- Modify: `~/.config/ccstatusline/settings.json` (backup previo `settings.json.bak-2026-10-06`)

- [ ] **Step 1:** Agregar al guardrail un patrón que bloquee cualquier comando de Claude que contenga `spec-kit.sync-status` (en `wow sk run|send`, `ric run|send`, `tmux send-keys` o `cursor-agent`), con el mensaje `/spec-kit.sync-status writes to Jira: run it in Cursor`. Seguir el estilo de patrones existente (`[^;&|]*`).
- [ ] **Step 2: Verificar el guardrail** con el mismo método que los patrones anteriores: pasarle por stdin `{"tool_input":{"command":"wow sk run '/spec-kit.sync-status specs/x'"}}` y comprobar que bloquea, y con `wow sk run '/spec-kit.plan'` que deja pasar.
- [ ] **Step 3:** En `~/.config/ccstatusline/settings.json`, en la segunda línea (hoy vacía), agregar `{"id": "wow-progress", "type": "custom-command", "commandPath": "wow progress --line", "timeout": 1000, "maxWidth": 60}`.
- [ ] **Step 4: Verificar**: `echo '{"workspace":{"current_dir":"<un proyecto con wow>"}}' | wow progress --line` imprime la línea; en una carpeta sin `wow/` imprime vacío. Pedirle al usuario que confirme que la ve debajo del prompt.
- [ ] (Sin commit: son archivos de la máquina del usuario. Anotar los cambios en la respuesta final.)

---

### Task 7: Skills, reglas y documentación

**Files:**
- Modify: `skills/wow-guide/SKILL.md`, `skills/wow-sk-prep/SKILL.md`, `AGENTS.md` (WoW), `README.md` (WoW)
- Modify: `/Users/josefigueredo/CurrentCode/SPECKIT/AGENTS.md` (regla de Spec-Kit y "El usuario publica")
- Modify: `Research/docs/site/_tools/internals/spec-kit-internals.html` (tabla "Dónde llega cada camino") y regenerar

- [ ] **Step 1: `wow-guide`:** empieza por `wow progress` (los dos checklists con %) y después `wow state` para los próximos pasos; presenta "Flujo PB" y "Flujo SK · <clave>" por separado, y dice que una épica creada fuera de PB entra con `wow sk start KEY`.
- [ ] **Step 2: `wow-sk-prep`:** el paso 3 pasa a ser `wow sk run "<comando>"` (y `wow sk send`/`wow sk quit` para las preguntas de clarify), con la alternativa de pegar el comando en Cursor si el usuario prefiere; `/spec-kit.sync-status` siempre se le entrega al usuario para Cursor.
- [ ] **Step 3a: `AGENTS.md` y `README.md` de SPECKIT:** `Harness/run-in-cursor/` se suma a "el código propio que se desarrolla" junto a WayOfWork y jira-kanban (TDD, 3.9, conventional commits).
- [ ] **Step 3: `AGENTS.md` de SPECKIT:** reemplazar la regla "Spec-Kit se registra desde Cursor interactivo…" por: registra cualquier sesión interactiva de Cursor (GUI, `cursor-agent` sin `-p` a mano, `wow sk run` o la skill `run-in-cursor`, que manejan `cursor-agent` interactivo en tmux); nunca `-p` ni el CLI `spec-kit` de la terminal; el agente puede mandar comandos con `wow sk run` salvo `/spec-kit.sync-status`, que escribe en Jira y corre solo en Cursor; el usuario puede seguir corriendo cualquier comando en Cursor. En "El usuario publica" sumar `/spec-kit.sync-status`.
- [ ] **Step 4: Página de internals:** en la tabla, la fila de `cursor-agent` interactivo pasa a decir que `beforeSubmitPrompt` llega (medido 2026-10-06) y se agrega la fila `wow sk run` (interactivo en tmux): `sí` / las cinco fases más `afterAgentResponse` / `sí`; en el párrafo de medición, agregar la de 2026-10-06 con la versión `2026.10.01-e373342` y que `-p --output-format json` devuelve `usage` pero no dispara `stop`. Regenerar con `python3 Research/docs/site/_tools/gen_internals.py` (arma `spec-kit-internals.html` desde `_tools/internals/spec-kit-internals.html`) y correr `wow cite check` sobre la página.
- [ ] **Step 5: README y `AGENTS.md` de WoW:** comandos nuevos (`wow progress`, `wow sk start|run|send|quit`), los dos flujos y que `run-wu` sigue deprecado.
- [ ] **Step 6:** suites 3.14 y 3.9 (no deberían cambiar) y `wow cite check`.
- [ ] **Step 7: Commits** en WoW `docs: two flows, checklists and wow sk run`; los cambios de SPECKIT (`AGENTS.md`, página) quedan sin commit porque esa carpeta no es repo: listarlos en la respuesta final.
