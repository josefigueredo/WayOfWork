# WayOfWork · Plan 4: dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un `dashboard/wow-dashboard.html` standalone, offline y en inglés, al que se arrastran uno o varios `wow/progress.json` y que grafica qué hay, dónde vive en GitHub y Jira, qué falta, velocidad, calidad de review, consumo de LLM y estado de Product Brain. Antes, `wow snapshot` se enriquece con los datos que hoy le faltan al dashboard.

**Architecture:** Dos partes.
1. **Python:** el módulo `wow/evidence.py` agrega a `current` tres bloques: `pb` (estado y auditoría de cada chat), `reviews` (resúmenes de `wow review`) y `pricing` (tabla de precios con fecha). `history_point` gana el progreso por épica para poder dibujar el burn-up.
2. **HTML:** un solo archivo con tres scripts inline.
   - `wow-core`: cálculo puro.
   - `wow-render`: arma los paneles como strings de HTML/SVG, también puro.
   - `wow-app`: el cableado del DOM (drag&drop, tema, tooltip y copiar).

   Al ser puros, `wow-core` y `wow-render` se testean renderizando con `node` desde `unittest`; el render headless del spec 12 queda sin navegador.

**Tech Stack:**
- Python 3.9+ con stdlib.
- HTML, CSS y JS vanilla (ES2020), sin dependencias.
- `node` (≥ 18) solo para los tests de render; si falta, esos tests se saltean con motivo.

**Spec:** `docs/superpowers/specs/2026-10-01-wayofwork-design.md` (secciones 7.1, 7.2, 8, 10, 11, 12 y D12). Planes previos: `2026-10-01-wow-core-guide.md`, `2026-10-02-wow-review-usage-sk.md` y `2026-10-02-wow-product-brain-side.md`.

## Global Constraints

**Python y tests**
- Compatible con 3.9 (`/usr/bin/python3`) y con Homebrew. Usar `from __future__ import annotations`, solo stdlib y `unittest`. Sin red y sin modelos reales.

**Dashboard: aislamiento y forma**
- Un solo archivo, todo en **inglés**: etiquetas, mensajes y comentarios (D10).
- CSP en `<meta>`: `default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'`.
- Prohibido: `fetch`, `XMLHttpRequest`, `WebSocket`, `EventSource`, `sendBeacon`, `<link>`, `@import` y cualquier `src`/`url()` remoto.
- Todo string que venga de `progress.json` pasa por `esc()`. Un `href` solo se emite si la URL empieza con `http://` o `https://`.

**Dashboard: datos y reglas visuales**
- Lo que no tiene dato se ve como "No data" **rayado y con motivo**, nunca como cero (D12). Los costos siempre dicen "estimated" y llevan la fecha de la tabla.
- Paleta validada con `dataviz` (`validate_palette.js`, `--pairs all`, PASS en ambos modos):
  - light: anthropic `#2a78d6` · openai `#eb6834` · cursor `#1baf7a`;
  - dark: `#3987e5` · `#d95926` · `#199e70`.
- El pool de Cursor siempre usa el slot 3 (aqua). El aqua de light queda por debajo de 3:1 (WARN), así que se aplica la regla de alivio: etiquetas directas en las barras más la vista de tabla.
- Status `good #0ca30c`, `warning #fab219`, `serious #ec835a` y `critical #d03b3b`: siempre con icono y etiqueta, nunca solo color.

**Commits y suites**
- Conventional Commits sin atribución de IA, uno por tarea, en `main`. **El commit va solo si ambas suites salen con exit 0.**
- Suites: `python3 -m unittest discover -s tests` y `/usr/bin/python3 -m unittest discover -s tests`.

## Desvíos del spec (decididos acá, a confirmar en la revisión del plan)

1. **Throughput semanal:** se calcula con los deltas de tareas `[x]` entre snapshots (fuente `history`), no con transiciones de Jira. La etiqueta del panel lo dice. **Lead time** queda en "No data: needs Jira transition dates (not collected yet)".
2. **Reparto de consumo:** se muestra por **pool × épica**, tomando la épica del prefijo de `ref` (`E1/WU-008` → `E1`), en lugar de "por fase". Los registros de uso no traen la fase y estimarla sería repartir a ojo, que el spec prohíbe.
3. **Confluence:** no se recolecta todavía. El panel de links lo muestra como "No data: not collected yet".
4. **Mediana de duración:** la misma que `wow usage` (`statistics.median` truncado a entero). El p95 se calcula por rango más cercano.

## Review Focus

1. **Un `progress.json` con `<img onerror>` en un título o `javascript:` en una URL** → se ve escapado y sin `href`. Test en Task 3.
2. **`schema_version` distinto de 1, o archivo que no es JSON** → aviso visible, render parcial o vacío, nunca pantalla en blanco. Tests en Tasks 2 y 3.
3. **Snapshot viejo sin `pb`, `reviews` ni `pricing`** → esos paneles muestran "No data" con el motivo "run wow snapshot again". Test en Task 3 (`partial.json` no trae `reviews`).
4. **Consumo con contadores en `null`** → la suma sigue en `null` y se ve "—", nunca `0`. Test en Task 2.
5. **Tema oscuro e impresión** → el dashboard sigue legible. La impresión fuerza los tokens claros aunque el tema activo sea oscuro. Verificación visual en Task 4 (Step 6).

---

## File Structure

```
wow/evidence.py                    pb_status, review_summaries, pricing — Task 1
wow/snapshot.py                    (modificar) history_point con progreso por épica — Task 1
wow/config.py                      (modificar) DEFAULTS["pricing"] — Task 1
wow/cli.py                         (modificar) snapshot agrega pb, reviews, pricing — Task 1
schemas/progress.schema.json       (modificar) current.pb|reviews|pricing — Task 1
dashboard/wow-dashboard.html       Tasks 2 (esqueleto + core), 3 (render), 4 (app + CSS)
dashboard/examples/empty.json · partial.json · full.json   Task 3
tests/test_evidence.py             Task 1
tests/test_snapshot.py · test_cli.py   (modificar) Task 1
tests/test_dashboard.py            Tasks 2–4
README.md                          (modificar) Task 4
```

---

### Task 1: evidencia para el dashboard en `wow snapshot`

**Files:**
- Create: `wow/evidence.py`, `tests/test_evidence.py`
- Modify: `wow/snapshot.py`, `wow/config.py`, `wow/cli.py`, `schemas/progress.schema.json`, `tests/test_snapshot.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes:
  - `pbchat.chat_status(project, doc) -> {"present", "closed", "audit"}` (Plan 1);
  - el formato de `wow/reviews/<ref>.json` (Plan 2: `ref`, `anchor_set`, `rounds[{verdict, blockers}]`, `final`).
- Produces:
  - `evidence.PB_KEYS = ("present", "closed", "audit", "completion_pct", "inventions", "missing_anchors", "open_questions")`.
  - `evidence.pb_status(project: Path, epic_ids: list[str]) -> dict`:
    - claves `prd`, `rfc` y `epic-<id>`, en ese orden;
    - cada valor es un dict con `PB_KEYS`;
    - `inventions`, `missing_anchors` y `open_questions` son **cantidades**, o `None` si no hay una auditoría legible.
  - `evidence.review_summaries(project: Path) -> list[dict]`:
    - un elemento `{"ref", "anchor_set", "rounds", "final", "first_pass", "blockers"}` por archivo legible de `wow/reviews/*.json`, en orden de nombre de archivo;
    - salta los archivos corruptos;
    - `first_pass` vale `True` si la ronda 1 dio `APPROVED`;
    - `blockers` es el total sumado entre todas las rondas.
  - `evidence.pricing(cfg: dict) -> {"as_of": str | None, "per_mtok": dict}`.
  - `config.DEFAULTS["pricing"] = {"as_of": None, "per_mtok": {}}`. Las tarifas son USD por millón de tokens: `{"<model>": {"in", "out", "cache_read", "cache_write"}}`.
  - `snapshot.history_point` agrega `"epics": {id: {"done": int, "total": int}}`, solo para las épicas que tienen `progress`.
  - `wow snapshot` escribe `current.pb`, `current.reviews` y `current.pricing`.
  - El schema `progress` los declara como **opcionales**, para no romper snapshots viejos.

- [ ] **Step 1: Escribir el test que falla**

`tests/test_evidence.py`:

```python
from __future__ import annotations

import json
import unittest

from helpers import make_project, write
import config
import evidence


class PbStatusTest(unittest.TestCase):
    def test_reads_audit_details_and_missing_docs(self):
        project = make_project()
        write(project, "wow/pb/chats/prd.md", "llega al 100%\n")
        write(project, "wow/pb/chats/prd.audit.json", json.dumps({
            "verdict": "changes_required", "completion_pct": 100, "inventions": [{"term": "x"}],
            "missing_anchors": ["AC2"], "open_questions": ["q1", "q2"]}))
        write(project, "wow/pb/chats/rfc.md", "draft\n")
        write(project, "wow/pb/chats/rfc.audit.json", "{bad")
        out = evidence.pb_status(project, ["E1"])
        self.assertEqual(list(out), ["prd", "rfc", "epic-E1"])
        self.assertEqual(out["prd"], {"present": True, "closed": True, "audit": "changes_required",
                                      "completion_pct": 100, "inventions": 1, "missing_anchors": 1,
                                      "open_questions": 2})
        self.assertEqual(out["rfc"]["audit"], "unknown")
        self.assertIsNone(out["rfc"]["inventions"])
        self.assertEqual(out["epic-E1"], {"present": False, "closed": False, "audit": None, "completion_pct": None,
                                          "inventions": None, "missing_anchors": None, "open_questions": None})


class ReviewSummariesTest(unittest.TestCase):
    def test_summaries_sorted_and_corrupt_skipped(self):
        project = make_project()
        write(project, "wow/reviews/plan.json", json.dumps({
            "ref": "plan", "anchor_set": "readiness", "final": "approved",
            "rounds": [{"n": 1, "verdict": "CHANGES_REQUIRED", "blockers": [{"anchor": "R1"}]},
                       {"n": 2, "verdict": "APPROVED", "blockers": []}]}))
        write(project, "wow/reviews/IRIS-41.json", json.dumps({
            "ref": "IRIS-41", "anchor_set": "story", "final": "approved",
            "rounds": [{"n": 1, "verdict": "APPROVED", "blockers": []}]}))
        write(project, "wow/reviews/broken.json", "{bad")
        self.assertEqual(evidence.review_summaries(project), [
            {"ref": "IRIS-41", "anchor_set": "story", "rounds": 1, "final": "approved", "first_pass": True,
             "blockers": 0},
            {"ref": "plan", "anchor_set": "readiness", "rounds": 2, "final": "approved", "first_pass": False,
             "blockers": 1}])
        self.assertEqual(evidence.review_summaries(make_project()), [])


class PricingTest(unittest.TestCase):
    def test_defaults_and_configured_table(self):
        self.assertEqual(evidence.pricing(config.DEFAULTS), {"as_of": None, "per_mtok": {}})
        cfg = {"pricing": {"as_of": "2026-09-01", "per_mtok": {"m": {"in": 1}}}}
        self.assertEqual(evidence.pricing(cfg), {"as_of": "2026-09-01", "per_mtok": {"m": {"in": 1}}})


if __name__ == "__main__":
    unittest.main()
```

En `tests/test_snapshot.py`, reemplazar la expectativa de `test_history_point_sums_known_progress` por:

```python
        self.assertEqual(point, {"ts": "2026-10-02T10:00:00Z", "plan_phase": 3,
                                 "phases": {"E1": 5, "E2": "unknown"}, "tasks_done": 3, "tasks_total": 4,
                                 "epics": {"E1": {"done": 3, "total": 4}}})
```

Agregar a `tests/test_cli.py`:

```python
class SnapshotEvidenceTest(unittest.TestCase):
    def test_snapshot_writes_pb_reviews_pricing_and_validates(self):
        import schema as _schema
        project = make_project()
        write(project, ".wow/config.json", _json.dumps({"github": {"enabled": False},
                                                        "usage": {"claude_root": str(project / "c"),
                                                                  "codex_root": str(project / "x")}}))
        write(project, "wow/reviews/plan.json", _json.dumps({"ref": "plan", "anchor_set": "readiness",
                                                             "rounds": [], "final": None}))
        self.assertEqual(run_cli(["snapshot", "--project", str(project)])[0], 0)
        saved = _json.loads((project / "wow/progress.json").read_text(encoding="utf-8"))
        current = saved["current"]
        self.assertEqual(list(current["pb"]), ["prd", "rfc"])
        self.assertEqual(current["reviews"][0]["ref"], "plan")
        self.assertEqual(current["pricing"], {"as_of": None, "per_mtok": {}})
        self.assertEqual(_schema.validate(saved, _schema.load_schema("progress")), [])
```

- [ ] **Step 2: Correr y verificar que falla** — `No module named 'evidence'`, `history_point` sin `epics` y `KeyError: 'pb'`.

- [ ] **Step 3: Implementar**

`wow/evidence.py`:

```python
"""Extra evidence the dashboard needs: Product Brain chat status, review summaries and pricing (spec 7.1, 8)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from sources import pbchat

PB_KEYS = ("present", "closed", "audit", "completion_pct", "inventions", "missing_anchors", "open_questions")


def _count(value) -> int:
    return len(value) if isinstance(value, list) else 0


def pb_status(project: Path, epic_ids: List[str]) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for doc in ["prd", "rfc"] + [f"epic-{eid}" for eid in epic_ids]:
        chat = pbchat.chat_status(project, doc)
        entry = {key: None for key in PB_KEYS}
        entry.update({"present": chat["present"], "closed": chat["closed"], "audit": chat["audit"]})
        path = project / "wow" / "pb" / "chats" / f"{doc}.audit.json"
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = None
            if isinstance(data, dict):
                entry["completion_pct"] = data.get("completion_pct")
                entry["inventions"] = _count(data.get("inventions"))
                entry["missing_anchors"] = _count(data.get("missing_anchors"))
                entry["open_questions"] = _count(data.get("open_questions"))
        out[doc] = entry
    return out


def review_summaries(project: Path) -> List[dict]:
    base = project / "wow" / "reviews"
    rows: List[dict] = []
    if not base.is_dir():
        return rows
    for path in sorted(base.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict) or not isinstance(data.get("rounds"), list):
            continue
        rounds = [r for r in data["rounds"] if isinstance(r, dict)]
        rows.append({"ref": data.get("ref", path.stem), "anchor_set": data.get("anchor_set"),
                     "rounds": len(rounds), "final": data.get("final"),
                     "first_pass": bool(rounds) and rounds[0].get("verdict") == "APPROVED",
                     "blockers": sum(_count(r.get("blockers")) for r in rounds)})
    return rows


def pricing(cfg: dict) -> dict:
    table = cfg.get("pricing") or {}
    return {"as_of": table.get("as_of"), "per_mtok": dict(table.get("per_mtok") or {})}
```

`wow/snapshot.py`, reemplazar `history_point` por:

```python
def history_point(state: dict, now: str) -> dict:
    done = total = 0
    per_epic = {}
    for epic in state["epics"]:
        progress = epic.get("progress")
        if progress:
            d, t = (int(x) for x in progress.split("/"))
            done, total = done + d, total + t
            per_epic[epic["id"]] = {"done": d, "total": t}
    return {"ts": now, "plan_phase": state["plan"]["phase"],
            "phases": {e["id"]: e["phase"] for e in state["epics"]},
            "tasks_done": done, "tasks_total": total, "epics": per_epic}
```

`wow/config.py`, agregar a `DEFAULTS` (después de `"github"`):

```python
    "pricing": {"as_of": None, "per_mtok": {}},
```

`wow/cli.py`: agregar `import evidence` y, en `_cmd_snapshot`, después de `result = links.build_links(project, result, prs)`:

```python
    result["pb"] = evidence.pb_status(project, [e["id"] for e in result["epics"]])
    result["reviews"] = evidence.review_summaries(project)
    result["pricing"] = evidence.pricing(cfg)
```

`schemas/progress.schema.json`: dentro de `current.properties`, después de `"sources"`:

```json
        "sources": {"type": "object"},
        "pb": {"type": "object"},
        "reviews": {"type": "array", "items": {"type": "object", "required": ["ref", "rounds", "final", "first_pass"]}},
        "pricing": {"type": "object", "required": ["as_of", "per_mtok"]}
```

- [ ] **Step 4: Correr ambas suites** — exit 0.

- [ ] **Step 5: Commit (solo con ambas suites en 0)**

```bash
python3 -m unittest discover -s tests && /usr/bin/python3 -m unittest discover -s tests && \
git add wow/evidence.py wow/snapshot.py wow/config.py wow/cli.py schemas/progress.schema.json \
        tests/test_evidence.py tests/test_snapshot.py tests/test_cli.py && \
git commit -m "feat(snapshot): add Product Brain status, review summaries, pricing and per-epic history"
```

---

### Task 2: esqueleto del dashboard y `wow-core`

**Files:**
- Create: `dashboard/wow-dashboard.html`, `tests/test_dashboard.py`

**Interfaces:**
- Produces: el global `WowCore` (en `<script id="wow-core">`) con:
  - `PHASES: string[7]` = `["Context", "Plan", "Packets", "Product Brain", "Spec-Kit", "Build", "Close"]`
  - `VENDORS: string[]` = `["anthropic", "openai", "cursor"]` (orden fijo de color)
  - `arr(v) -> array` (`[]` si no es un array)
  - `validate(doc) -> {ok: boolean, warnings: string[]}`
  - `phaseState(phase, col) -> "done" | "current" | "todo" | "unknown"`
  - `sumOrNull(values) -> number | null`
  - `median(sortedNumbers) -> number | null` (igual a `statistics.median` truncado)
  - `quantile(sortedNumbers, q) -> number | null` (rango más cercano)
  - `vendorKey(vendor) -> "anthropic" | "openai" | "cursor" | "other"`
  - `pool(vendor) -> "own" | "cursor" | "other"`
  - `usageByModel(usage) -> [{vendor, model, pool, count, tokens_in, tokens_out, cache_read, cache_write, reasoning_out, median_ms, p95_ms}]`
  - `poolTotals(usage) -> {own: {count, tokens_in, tokens_out}, cursor: {…}, other: {…}}`
  - `refEpic(ref) -> string | null`
  - `usageByEpic(usage) -> [{epic, own, cursor}]` (tokens in + out por pool; `epic: "unattributed"` cuando `ref` es null)
  - `estimateCost(usage, pricing) -> {available: false, reason} | {available: true, as_of, byPool: {own, cursor, other}, priced, unpriced}`
  - `weekStart(ts) -> "YYYY-MM-DD" | null` (lunes, UTC)
  - `weeklyThroughput(history) -> [{week, done}]` (sin la primera semana, que solo sirve de base)
  - `burnup(history, epicId) -> [{ts, done, total}]`
  - `quality(reviews) -> {total, decided, firstPassRate | null, hitl, rows}`
- `tests/test_dashboard.py` define `HTML`, `EXAMPLES`, `NODE`, `script(sid)` y `run_node(js) -> CompletedProcess`, que reutilizan las Tasks 3 y 4.

- [ ] **Step 1: Escribir el test que falla**

`tests/test_dashboard.py`:

```python
from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest

from helpers import ROOT

HTML = ROOT / "dashboard" / "wow-dashboard.html"
EXAMPLES = ROOT / "dashboard" / "examples"
NODE = shutil.which("node")
_FORBIDDEN = ["fetch(", "XMLHttpRequest", "WebSocket", "EventSource", "sendBeacon", "<link", "@import",
              'src="http', "src='http", "url(http", "url('http", 'url("http']


def html_text() -> str:
    return HTML.read_text(encoding="utf-8")


def script(sid: str) -> str:
    match = re.search(rf'<script id="{sid}">(.*?)</script>', html_text(), re.S)
    if match is None:
        raise AssertionError(f"script #{sid} not found")
    return match.group(1)


def run_node(js: str) -> subprocess.CompletedProcess:
    return subprocess.run([NODE, "--input-type=commonjs", "-"], input=js, capture_output=True, text=True,
                          timeout=60)


class StaticTest(unittest.TestCase):
    def test_csp_blocks_network(self):
        text = html_text()
        csp = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)"', text)
        self.assertIsNotNone(csp)
        for directive in ("default-src 'none'", "connect-src 'none'", "form-action 'none'", "base-uri 'none'"):
            self.assertIn(directive, csp.group(1))

    def test_no_network_apis_or_remote_resources(self):
        text = html_text()
        for needle in _FORBIDDEN:
            self.assertNotIn(needle, text, needle)

    def test_english_only(self):
        self.assertIsNone(re.search(r"[áéíóúñÁÉÍÓÚÑ¿¡]", html_text()))


@unittest.skipIf(NODE is None, "node is not installed")
class CoreTest(unittest.TestCase):
    def test_core_functions(self):
        js = script("wow-core") + r"""
const assert = require("assert");
const C = WowCore;
const R = (o) => Object.assign({ts: "t", vendor: "anthropic", tool: "claude-code", model: "m1", tokens_in: null,
  tokens_out: null, cache_read: null, cache_write: null, reasoning_out: null, duration_ms: null,
  scope: "message", ref: null, source: "x"}, o);

assert.deepStrictEqual(C.validate([]).ok, false);
const v2 = C.validate({schema_version: 2, current: {}, history: [], usage: []});
assert.strictEqual(v2.ok, true);
assert.ok(v2.warnings[0].includes("schema_version"));
assert.deepStrictEqual(C.validate({schema_version: 1, current: {}}).warnings, ['missing "history"', 'missing "usage"']);

assert.deepStrictEqual([C.phaseState(5, 3), C.phaseState(5, 5), C.phaseState(5, 6), C.phaseState("unknown", 3)],
  ["done", "current", "todo", "unknown"]);

assert.strictEqual(C.sumOrNull([null, undefined]), null);
assert.strictEqual(C.sumOrNull([null, 2, 3]), 5);
assert.strictEqual(C.median([100, 300]), 200);
assert.strictEqual(C.median([100, 201]), 150);
assert.strictEqual(C.quantile([100, 200, 300], 0.95), 300);
assert.strictEqual(C.median([]), null);

const rows = C.usageByModel([R({tokens_in: 10, duration_ms: 100}), R({tokens_in: 5, duration_ms: 300}),
  R({duration_ms: 200}), R({vendor: "cursor", tool: "cursor-agent", model: "composer", tokens_out: 7})]);
assert.deepStrictEqual(rows.map(r => [r.vendor, r.model, r.count, r.pool]),
  [["anthropic", "m1", 3, "own"], ["cursor", "composer", 1, "cursor"]]);
assert.strictEqual(rows[0].tokens_in, 15);
assert.strictEqual(rows[0].cache_read, null);
assert.deepStrictEqual([rows[0].median_ms, rows[0].p95_ms], [200, 300]);
assert.strictEqual(rows[1].median_ms, null);

const pools = C.poolTotals([R({tokens_in: 4}), R({vendor: "cursor", tokens_out: 6})]);
assert.deepStrictEqual([pools.own.tokens_in, pools.own.tokens_out, pools.cursor.tokens_out], [4, null, 6]);

assert.deepStrictEqual([C.refEpic("E1/WU-8"), C.refEpic("plan"), C.refEpic(null)], ["E1", "plan", null]);
assert.deepStrictEqual(C.usageByEpic([R({ref: "E1/WU-8", tokens_in: 3}), R({vendor: "cursor", ref: "E1/WU-9",
  tokens_out: 2}), R({tokens_in: 1})]), [{epic: "E1", own: 3, cursor: 2}, {epic: "unattributed", own: 1, cursor: null}]);

assert.strictEqual(C.estimateCost([R({tokens_in: 1})], {as_of: null, per_mtok: {}}).available, false);
const cost = C.estimateCost([R({tokens_in: 1000000, tokens_out: 1000000}), R({model: "zzz", tokens_in: 5})],
  {as_of: "2026-09-01", per_mtok: {m1: {in: 3, out: 15}}});
assert.deepStrictEqual([cost.available, cost.as_of, cost.priced, cost.unpriced, cost.byPool.own], [true, "2026-09-01", 1, 1, 18]);

assert.strictEqual(C.weekStart("2026-09-10T10:00:00Z"), "2026-09-07");
assert.strictEqual(C.weekStart("nope"), null);
assert.deepStrictEqual(C.weeklyThroughput([{ts: "2026-09-08T10:00:00Z", tasks_done: 0},
  {ts: "2026-09-10T10:00:00Z", tasks_done: 2}, {ts: "2026-09-16T10:00:00Z", tasks_done: 5},
  {ts: "2026-09-23T10:00:00Z", tasks_done: 4}]), [{week: "2026-09-14", done: 3}, {week: "2026-09-21", done: 0}]);

assert.deepStrictEqual(C.burnup([{ts: "a", epics: {E1: {done: 1, total: 4}}}, {ts: "b", epics: {}},
  {ts: "c", epics: {E1: {done: 3, total: 5}}}], "E1"), [{ts: "a", done: 1, total: 4}, {ts: "c", done: 3, total: 5}]);

const q = C.quality([{ref: "a", rounds: 1, final: "approved", first_pass: true},
  {ref: "b", rounds: 3, final: "hitl", first_pass: false}, {ref: "c", rounds: 1, final: null, first_pass: false}]);
assert.deepStrictEqual([q.total, q.decided, q.firstPassRate, q.hitl], [3, 2, 0.5, 1]);
assert.strictEqual(C.quality([]).firstPassRate, null);
console.log("core ok");
"""
        proc = run_node(js)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("core ok", proc.stdout)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Correr y verificar que falla** — `FileNotFoundError` (el HTML no existe todavía).

- [ ] **Step 3: Crear `dashboard/wow-dashboard.html`**. Los scripts `wow-render` y `wow-app` quedan vacíos hasta las Tasks 3 y 4, y el `<style>` es mínimo hasta la Task 4.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'">
<title>WayOfWork Dashboard</title>
<style>
body { font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
</style>
</head>
<body>
<header>
  <h1>WayOfWork Dashboard</h1>
  <div class="controls">
    <label class="file">Open progress.json <input id="file" type="file" accept=".json,application/json" multiple></label>
    <button id="theme" type="button">Toggle theme</button>
    <button id="print" type="button">Print</button>
  </div>
</header>
<div id="drop" class="drop">Drop one or more <code>wow/progress.json</code> files here. Nothing leaves this page.</div>
<div id="warnings" role="status"></div>
<div id="portfolio"></div>
<main id="panels"></main>
<div id="tip" role="tooltip" hidden></div>
<script id="wow-core">
const WowCore = (() => {
  "use strict";
  const PHASES = ["Context", "Plan", "Packets", "Product Brain", "Spec-Kit", "Build", "Close"];
  const VENDORS = ["anthropic", "openai", "cursor"];
  const POOLS = {anthropic: "own", openai: "own", cursor: "cursor"};
  const TOKEN_FIELDS = ["tokens_in", "tokens_out", "cache_read", "cache_write", "reasoning_out"];

  const arr = (v) => (Array.isArray(v) ? v : []);
  const isNum = (v) => typeof v === "number" && Number.isFinite(v);

  function validate(doc) {
    if (!doc || typeof doc !== "object" || Array.isArray(doc)) return {ok: false, warnings: ["not a JSON object"]};
    const warnings = [];
    if (doc.schema_version !== 1) {
      warnings.push(`schema_version ${JSON.stringify(doc.schema_version)} is not 1; showing what is recognizable`);
    }
    for (const key of ["history", "usage"]) if (!(key in doc)) warnings.push(`missing "${key}"`);
    const ok = !!doc.current && typeof doc.current === "object";
    if (!ok) warnings.push('missing "current"');
    return {ok, warnings};
  }

  function phaseState(phase, col) {
    if (!isNum(phase)) return "unknown";
    if (phase > col) return "done";
    return phase === col ? "current" : "todo";
  }

  function sumOrNull(values) {
    let total = null;
    for (const v of values) if (isNum(v)) total = (total === null ? 0 : total) + v;
    return total;
  }

  function median(sorted) {
    if (!sorted.length) return null;
    const mid = sorted.length >> 1;
    return sorted.length % 2 ? sorted[mid] : Math.trunc((sorted[mid - 1] + sorted[mid]) / 2);
  }

  function quantile(sorted, q) {
    if (!sorted.length) return null;
    const rank = Math.min(sorted.length, Math.max(1, Math.ceil(q * sorted.length)));
    return sorted[rank - 1];
  }

  const vendorKey = (vendor) => (VENDORS.includes(vendor) ? vendor : "other");
  const pool = (vendor) => POOLS[vendor] || "other";
  const records = (usage) => arr(usage).filter((r) => r && typeof r === "object");

  function usageByModel(usage) {
    const groups = new Map();
    for (const r of records(usage)) {
      const key = `${r.vendor}\u0000${r.model}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(r);
    }
    const rows = [];
    for (const items of groups.values()) {
      const durations = items.map((r) => r.duration_ms).filter(isNum).sort((a, b) => a - b);
      const row = {vendor: items[0].vendor ?? null, model: items[0].model ?? null, pool: pool(items[0].vendor),
                   count: items.length, median_ms: median(durations), p95_ms: quantile(durations, 0.95)};
      for (const field of TOKEN_FIELDS) row[field] = sumOrNull(items.map((r) => r[field]));
      rows.push(row);
    }
    const rank = (v) => (VENDORS.indexOf(v) < 0 ? VENDORS.length : VENDORS.indexOf(v));
    return rows.sort((a, b) => rank(a.vendor) - rank(b.vendor) || String(a.model).localeCompare(String(b.model)));
  }

  function poolTotals(usage) {
    const out = {};
    for (const name of ["own", "cursor", "other"]) {
      const items = records(usage).filter((r) => pool(r.vendor) === name);
      out[name] = {count: items.length, tokens_in: sumOrNull(items.map((r) => r.tokens_in)),
                   tokens_out: sumOrNull(items.map((r) => r.tokens_out))};
    }
    return out;
  }

  const refEpic = (ref) => (typeof ref === "string" && ref ? ref.split("/")[0] : null);

  function usageByEpic(usage) {
    const groups = new Map();
    for (const r of records(usage)) {
      const epic = refEpic(r.ref) || "unattributed";
      if (!groups.has(epic)) groups.set(epic, {epic, own: [], cursor: []});
      const target = groups.get(epic)[pool(r.vendor) === "cursor" ? "cursor" : "own"];
      target.push(r.tokens_in, r.tokens_out);
    }
    return [...groups.values()].map((g) => ({epic: g.epic, own: sumOrNull(g.own), cursor: sumOrNull(g.cursor)}));
  }

  function estimateCost(usage, pricing) {
    const table = (pricing && pricing.per_mtok) || {};
    if (!Object.keys(table).length) {
      return {available: false, reason: "no price table: set pricing.per_mtok in .wow/config.json"};
    }
    const byPool = {own: 0, cursor: 0, other: 0};
    let priced = 0;
    let unpriced = 0;
    for (const r of records(usage)) {
      const rates = table[r.model];
      if (!rates) { unpriced += 1; continue; }
      let cost = 0;
      for (const [field, rate] of [["tokens_in", rates.in], ["tokens_out", rates.out],
                                   ["cache_read", rates.cache_read], ["cache_write", rates.cache_write]]) {
        if (isNum(r[field]) && isNum(rate)) cost += (r[field] * rate) / 1e6;
      }
      byPool[pool(r.vendor)] += cost;
      priced += 1;
    }
    return {available: true, as_of: (pricing && pricing.as_of) || null, byPool, priced, unpriced};
  }

  function weekStart(ts) {
    const d = new Date(ts);
    if (Number.isNaN(d.getTime())) return null;
    const back = (d.getUTCDay() + 6) % 7;
    return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() - back)).toISOString().slice(0, 10);
  }

  function weeklyThroughput(history) {
    const lastByWeek = new Map();
    for (const h of arr(history)) {
      const week = h && weekStart(h.ts);
      if (week && isNum(h.tasks_done)) lastByWeek.set(week, h.tasks_done);
    }
    const weeks = [...lastByWeek.keys()].sort();
    return weeks.slice(1).map((week, i) => ({week, done: Math.max(0, lastByWeek.get(week) - lastByWeek.get(weeks[i]))}));
  }

  function burnup(history, epicId) {
    return arr(history)
      .filter((h) => h && h.epics && h.epics[epicId] && isNum(h.epics[epicId].done))
      .map((h) => ({ts: h.ts, done: h.epics[epicId].done, total: h.epics[epicId].total}));
  }

  function quality(reviews) {
    const rows = arr(reviews).filter((r) => r && typeof r === "object");
    const decided = rows.filter((r) => r.final === "approved" || r.final === "hitl");
    const firstPass = decided.filter((r) => r.first_pass).length;
    return {total: rows.length, decided: decided.length,
            firstPassRate: decided.length ? firstPass / decided.length : null,
            hitl: rows.filter((r) => r.final === "hitl").length, rows};
  }

  return {PHASES, VENDORS, arr, validate, phaseState, sumOrNull, median, quantile, vendorKey, pool,
          usageByModel, poolTotals, refEpic, usageByEpic, estimateCost, weekStart, weeklyThroughput, burnup,
          quality};
})();
</script>
<script id="wow-render"></script>
<script id="wow-app"></script>
</body>
</html>
```

- [ ] **Step 4: Correr ambas suites** — exit 0. `CoreTest` imprime `core ok`.

- [ ] **Step 5: Commit (solo con ambas suites en 0)**

```bash
python3 -m unittest discover -s tests && /usr/bin/python3 -m unittest discover -s tests && \
git add dashboard/wow-dashboard.html tests/test_dashboard.py && \
git commit -m "feat(dashboard): add the offline dashboard shell and the pure metrics core"
```

---

### Task 3: `wow-render` y los tres `progress.json` de ejemplo

**Files:**
- Create: `dashboard/examples/empty.json`, `dashboard/examples/partial.json`, `dashboard/examples/full.json`
- Modify: `dashboard/wow-dashboard.html` (contenido de `<script id="wow-render">`), `tests/test_dashboard.py`

**Interfaces:**
- Consumes: `WowCore` (Task 2).
- Produces: el global `WowRender` con:
  - `esc(v) -> string`
  - `safeUrl(u) -> string | null`
  - `renderAll(doc) -> string[7]`: en orden `panel-phase-map`, `panel-next-steps`, `panel-links`, `panel-velocity`, `panel-quality`, `panel-usage`, `panel-pb`.
  - `renderDoc(entry) -> {warnings: string, html: string}`, con `entry = {name, doc, error?}`.
  - `portfolio(entries, active) -> string`.
- Los elementos con tooltip llevan `data-tip` (texto plano escapado) y `tabindex="0"`. Los botones de copiar llevan `data-copy`; los de selección de archivo, `data-select`.

- [ ] **Step 1: Escribir los ejemplos**

`dashboard/examples/empty.json`:

```json
{
  "schema_version": 1,
  "generated_at": "2026-10-02T12:00:00Z",
  "current": {
    "schema_version": 1,
    "plan": {"id": null, "phase": 0, "stale_packets": [], "missing": ["build the context pack", "plan the initiative"],
             "links": {"files": []}},
    "epics": [],
    "blockers": [],
    "next_steps": [
      {"epic": null, "phase": 0, "action": "build the context pack", "where": "harness", "model": "claude-opus",
       "command": "wow-context", "why": "wow/context-pack/facts.md and pending-owner.md are required before planning"},
      {"epic": null, "phase": 1, "action": "plan the initiative", "where": "harness", "model": "claude-opus",
       "command": "wow-plan", "why": "there is no wow/plan/manifest.json yet"}
    ],
    "steps_total": 2,
    "sources": {"jira": "not_configured", "github": "disabled"},
    "pb": {
      "prd": {"present": false, "closed": false, "audit": null, "completion_pct": null, "inventions": null,
              "missing_anchors": null, "open_questions": null},
      "rfc": {"present": false, "closed": false, "audit": null, "completion_pct": null, "inventions": null,
              "missing_anchors": null, "open_questions": null}
    },
    "reviews": [],
    "pricing": {"as_of": null, "per_mtok": {}}
  },
  "history": [{"ts": "2026-10-02T12:00:00Z", "plan_phase": 0, "phases": {}, "tasks_done": 0, "tasks_total": 0, "epics": {}}],
  "usage": []
}
```

`dashboard/examples/partial.json` (fuentes caídas; snapshot previo a `reviews` y `pricing`):

```json
{
  "schema_version": 1,
  "generated_at": "2026-09-30T18:00:00Z",
  "current": {
    "schema_version": 1,
    "plan": {"id": "0001-example", "phase": 3, "stale_packets": [], "missing": [],
             "links": {"files": ["wow/plan/PLAN.md", "wow/plan/manifest.json", "wow/pb/prd.md", "wow/pb/rfc.md"]}},
    "epics": [
      {"id": "E1", "title": "Curation", "jira": null, "jira_url": null, "phase": 3, "reason": null, "progress": null,
       "missing": ["audit the epic E1 chat"], "links": {"jira": null, "prs": [], "files": []}},
      {"id": "E2", "title": "Reporting", "jira": "EX-50", "jira_url": null, "phase": "unknown",
       "reason": "jira: HTTP 401", "progress": null, "missing": [], "links": {"jira": null, "prs": [], "files": []}}
    ],
    "blockers": ["owner: 1 decision(s) open in wow/context-pack/pending-owner.md"],
    "next_steps": [
      {"epic": "E1", "phase": 3, "action": "audit the epic E1 chat", "where": "harness", "model": "codex",
       "command": "wow-pb-audit", "why": "audit verdict is changes_required"}
    ],
    "steps_total": 1,
    "sources": {"jira": "jira: HTTP 401", "github": "partial: github: gh pr list failed in mfe-example"},
    "pb": {
      "prd": {"present": true, "closed": true, "audit": "approved", "completion_pct": 100, "inventions": 0,
              "missing_anchors": 0, "open_questions": 2},
      "rfc": {"present": true, "closed": true, "audit": "approved", "completion_pct": 95, "inventions": 0,
              "missing_anchors": 0, "open_questions": 1},
      "epic-E1": {"present": true, "closed": true, "audit": "changes_required", "completion_pct": 100,
                  "inventions": 2, "missing_anchors": 1, "open_questions": 0},
      "epic-E2": {"present": false, "closed": false, "audit": null, "completion_pct": null, "inventions": null,
                  "missing_anchors": null, "open_questions": null}
    }
  },
  "history": [
    {"ts": "2026-09-22T18:00:00Z", "plan_phase": 1, "phases": {"E1": 1, "E2": 1}, "tasks_done": 0, "tasks_total": 0},
    {"ts": "2026-09-30T18:00:00Z", "plan_phase": 3, "phases": {"E1": 3, "E2": "unknown"}, "tasks_done": 0, "tasks_total": 0}
  ],
  "usage": [
    {"ts": "2026-09-29T10:00:00Z", "vendor": "anthropic", "tool": "claude-code", "model": "claude-opus-5-5",
     "tokens_in": 2400, "tokens_out": 900, "cache_read": 150000, "cache_write": 6000, "reasoning_out": null,
     "duration_ms": 14000, "scope": "message", "ref": "plan", "source": "claude-transcript"},
    {"ts": "2026-09-30T11:00:00Z", "vendor": "anthropic", "tool": "claude-code", "model": "claude-opus-5-5",
     "tokens_in": null, "tokens_out": null, "cache_read": null, "cache_write": null, "reasoning_out": null,
     "duration_ms": null, "scope": "message", "ref": null, "source": "claude-transcript"}
  ]
}
```

`dashboard/examples/full.json`:

```json
{
  "schema_version": 1,
  "generated_at": "2026-10-02T12:00:00Z",
  "current": {
    "schema_version": 1,
    "plan": {"id": "0002-example", "phase": 3, "stale_packets": [], "missing": [],
             "links": {"files": ["wow/plan/PLAN.md", "wow/plan/manifest.json", "wow/pb/prd.md", "wow/pb/rfc.md",
                                 "wow/context-pack/facts.md"]}},
    "epics": [
      {"id": "E1", "title": "Curation", "jira": "EX-40", "jira_url": "https://example.atlassian.net/browse/EX-40",
       "phase": 5, "reason": null, "progress": "7/12", "missing": ["implement WU-008", "review EX-43"],
       "links": {"jira": "https://example.atlassian.net/browse/EX-40",
                 "prs": [{"repo": "backend-example", "number": 7, "title": "EX-41 curate endpoint", "state": "MERGED",
                          "url": "https://github.com/example/backend-example/pull/7", "branch": "feat/EX-41",
                          "checks": "passing"},
                         {"repo": "backend-example", "number": 9, "title": "EX-43 audit trail", "state": "OPEN",
                          "url": "https://github.com/example/backend-example/pull/9", "branch": "feat/EX-43",
                          "checks": "failing"}],
                 "files": ["specs/001-curation/spec.md", "specs/001-curation/plan.md", "specs/001-curation/tasks.md",
                           "wow/pb/epic-E1.md"]}},
      {"id": "E2", "title": "Reporting", "jira": "EX-50", "jira_url": "https://example.atlassian.net/browse/EX-50",
       "phase": 4, "reason": null, "progress": null, "missing": ["ratify tasks and work units"],
       "links": {"jira": "https://example.atlassian.net/browse/EX-50", "prs": [],
                 "files": ["specs/002-reporting/spec.md", "specs/002-reporting/plan.md", "wow/pb/epic-E2.md"]}},
      {"id": "E3", "title": "Exports", "jira": "EX-60", "jira_url": "https://example.atlassian.net/browse/EX-60",
       "phase": 6, "reason": null, "progress": "10/10", "missing": ["run the epic review"],
       "links": {"jira": "https://example.atlassian.net/browse/EX-60",
                 "prs": [{"repo": "backend-example", "number": 12, "title": "EX-61 csv export", "state": "MERGED",
                          "url": "https://github.com/example/backend-example/pull/12", "branch": "feat/EX-61",
                          "checks": "passing"}],
                 "files": ["specs/003-exports/spec.md", "specs/003-exports/tasks.md", "wow/pb/epic-E3.md"]}}
    ],
    "blockers": [],
    "next_steps": [
      {"epic": "E3", "phase": 6, "action": "run the epic review", "where": "harness", "model": "codex",
       "command": "wow review --set epic --ref E3 --repo ../backend-example", "why": "all tasks are checked"},
      {"epic": "E1", "phase": 5, "action": "implement WU-008", "where": "cursor", "model": "composer-2.5",
       "command": "wow run-wu WU-008 --epic E1", "why": "WU-008 is not checked in tasks.md"},
      {"epic": "E2", "phase": 4, "action": "ratify tasks and work units", "where": "cursor",
       "model": "claude-sonnet-5-5-high", "command": "wow sk cmd tasks --feature specs/002-reporting",
       "why": "tasks.md or work-units.json is missing"}
    ],
    "steps_total": 4,
    "sources": {"jira": "ok", "github": "ok"},
    "pb": {
      "prd": {"present": true, "closed": true, "audit": "approved", "completion_pct": 100, "inventions": 0,
              "missing_anchors": 0, "open_questions": 0},
      "rfc": {"present": true, "closed": true, "audit": "approved", "completion_pct": 100, "inventions": 0,
              "missing_anchors": 0, "open_questions": 0},
      "epic-E1": {"present": true, "closed": true, "audit": "approved", "completion_pct": 100, "inventions": 0,
                  "missing_anchors": 0, "open_questions": 0},
      "epic-E2": {"present": true, "closed": true, "audit": "approved", "completion_pct": 100, "inventions": 0,
                  "missing_anchors": 0, "open_questions": 0},
      "epic-E3": {"present": true, "closed": true, "audit": "approved", "completion_pct": 100, "inventions": 0,
                  "missing_anchors": 0, "open_questions": 0}
    },
    "reviews": [
      {"ref": "EX-41", "anchor_set": "story", "rounds": 1, "final": "approved", "first_pass": true, "blockers": 0},
      {"ref": "EX-42", "anchor_set": "story", "rounds": 2, "final": "approved", "first_pass": false, "blockers": 1},
      {"ref": "EX-61", "anchor_set": "story", "rounds": 3, "final": "hitl", "first_pass": false, "blockers": 4},
      {"ref": "plan", "anchor_set": "readiness", "rounds": 2, "final": "approved", "first_pass": false, "blockers": 2}
    ],
    "pricing": {"as_of": "2026-09-01 (example values)",
                "per_mtok": {"claude-opus-5-5": {"in": 15, "out": 75, "cache_read": 1.5, "cache_write": 18.75},
                             "composer-2.5": {"in": 1.25, "out": 10, "cache_read": 0.125, "cache_write": null}}}
  },
  "history": [
    {"ts": "2026-09-08T18:00:00Z", "plan_phase": 3, "phases": {"E1": 4, "E2": 3, "E3": 5}, "tasks_done": 2, "tasks_total": 20,
     "epics": {"E3": {"done": 2, "total": 8}}},
    {"ts": "2026-09-15T18:00:00Z", "plan_phase": 3, "phases": {"E1": 5, "E2": 3, "E3": 5}, "tasks_done": 7, "tasks_total": 22,
     "epics": {"E1": {"done": 1, "total": 12}, "E3": {"done": 6, "total": 10}}},
    {"ts": "2026-09-22T18:00:00Z", "plan_phase": 3, "phases": {"E1": 5, "E2": 4, "E3": 5}, "tasks_done": 12, "tasks_total": 22,
     "epics": {"E1": {"done": 4, "total": 12}, "E3": {"done": 8, "total": 10}}},
    {"ts": "2026-09-29T18:00:00Z", "plan_phase": 3, "phases": {"E1": 5, "E2": 4, "E3": 6}, "tasks_done": 15, "tasks_total": 22,
     "epics": {"E1": {"done": 5, "total": 12}, "E3": {"done": 10, "total": 10}}},
    {"ts": "2026-10-02T12:00:00Z", "plan_phase": 3, "phases": {"E1": 5, "E2": 4, "E3": 6}, "tasks_done": 17, "tasks_total": 22,
     "epics": {"E1": {"done": 7, "total": 12}, "E3": {"done": 10, "total": 10}}}
  ],
  "usage": [
    {"ts": "2026-09-30T10:00:00Z", "vendor": "anthropic", "tool": "claude-code", "model": "claude-opus-5-5",
     "tokens_in": 1200, "tokens_out": 340, "cache_read": 90000, "cache_write": 4000, "reasoning_out": null,
     "duration_ms": 8100, "scope": "message", "ref": "plan", "source": "claude-transcript"},
    {"ts": "2026-10-01T10:00:00Z", "vendor": "anthropic", "tool": "claude-code", "model": "claude-opus-5-5",
     "tokens_in": 800, "tokens_out": 500, "cache_read": 120000, "cache_write": 2000, "reasoning_out": null,
     "duration_ms": 12000, "scope": "message", "ref": "E1/WU-008", "source": "claude-transcript"},
    {"ts": "2026-10-01T11:00:00Z", "vendor": "openai", "tool": "codex", "model": "gpt-5-codex",
     "tokens_in": 15000, "tokens_out": 900, "cache_read": 12000, "cache_write": null, "reasoning_out": 400,
     "duration_ms": 30000, "scope": "turn", "ref": "E1/EX-42", "source": "codex-session"},
    {"ts": "2026-10-01T12:00:00Z", "vendor": "openai", "tool": "codex", "model": "gpt-5-codex",
     "tokens_in": 9000, "tokens_out": 600, "cache_read": 8000, "cache_write": null, "reasoning_out": 200,
     "duration_ms": 22000, "scope": "turn", "ref": null, "source": "codex-session"},
    {"ts": "2026-10-01T13:00:00Z", "vendor": "cursor", "tool": "cursor-agent", "model": "composer-2.5",
     "tokens_in": 1000, "tokens_out": 50, "cache_read": 30000, "cache_write": 500, "reasoning_out": null,
     "duration_ms": 60000, "scope": "task", "ref": "E1/WU-008", "source": "cursor-run"},
    {"ts": "2026-10-02T09:00:00Z", "vendor": "cursor", "tool": "cursor-agent", "model": "composer-2.5",
     "tokens_in": 2000, "tokens_out": 120, "cache_read": 40000, "cache_write": 800, "reasoning_out": null,
     "duration_ms": 90000, "scope": "task", "ref": "E2/WU-002", "source": "cursor-run"}
  ]
}
```

- [ ] **Step 2: Escribir el test que falla** (agregar a `tests/test_dashboard.py`)

```python
class ExamplesTest(unittest.TestCase):
    def test_examples_validate_against_progress_schema(self):
        import schema
        for name in ("empty.json", "partial.json", "full.json"):
            doc = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
            self.assertEqual(schema.validate(doc, schema.load_schema("progress")), [], name)


@unittest.skipIf(NODE is None, "node is not installed")
class RenderTest(unittest.TestCase):
    def test_render_examples_and_hostile_input(self):
        js = script("wow-core") + script("wow-render") + r"""
const assert = require("assert");
const fs = require("fs");
const R = WowRender;
const EX = %s;
const ex = (n) => JSON.parse(fs.readFileSync(EX + "/" + n, "utf8"));
const panels = (html) => (html.match(/<section class="panel/g) || []).length;

for (const n of ["empty.json", "partial.json", "full.json"]) {
  const out = R.renderDoc({name: n, doc: ex(n)});
  assert.strictEqual(panels(out.html), 7, n);
  assert.strictEqual(out.warnings, "", n);
  assert.strictEqual(R.renderAll(ex(n)).length, 7, n);
}
const empty = R.renderDoc({name: "e", doc: ex("empty.json")}).html;
assert.ok(empty.includes("No data"));
assert.ok(empty.includes("build the context pack"));
const partial = R.renderDoc({name: "p", doc: ex("partial.json")}).html;
assert.ok(partial.includes("jira: HTTP 401"));
assert.ok(partial.includes("run wow snapshot again"));
const full = R.renderDoc({name: "f", doc: ex("full.json")}).html;
for (const needle of ["E3", "estimated", "2026-09-01 (example values)", "Cursor", "EX-43", "checks failing",
                      'href="https://github.com/example/backend-example/pull/9"', "data-copy=", "HITL"]) {
  assert.ok(full.includes(needle), needle);
}

const evil = ex("full.json");
evil.current.epics[0].title = "<img src=x onerror=alert(1)>";
evil.current.epics[0].jira_url = "javascript:alert(1)";
evil.current.epics[0].links.jira = "javascript:alert(1)";
evil.current.epics[0].links.prs[0].url = "javascript:alert(2)";
const bad = R.renderDoc({name: "evil", doc: evil}).html;
assert.ok(!bad.includes("<img src=x"));
assert.ok(bad.includes("&lt;img src=x"));
assert.ok(!/href="javascript:/i.test(bad));

const v2 = R.renderDoc({name: "v2.json", doc: Object.assign(ex("empty.json"), {schema_version: 2})});
assert.ok(v2.warnings.includes("schema_version"));
assert.strictEqual(panels(v2.html), 7);
const broken = R.renderDoc({name: "bad.json", doc: null, error: "not valid JSON"});
assert.strictEqual(broken.html, "");
assert.ok(broken.warnings.includes("not valid JSON"));
assert.ok(R.renderDoc({name: "x.json", doc: {schema_version: 1}}).warnings.includes('missing &quot;current&quot;'));

const port = R.portfolio([{name: "a.json", doc: ex("full.json")}, {name: "b.json", doc: null, error: "not valid JSON"}], 0);
assert.ok(port.includes("Portfolio (2 files)"));
assert.ok(port.includes('data-select="1"'));
assert.ok(port.includes("not valid JSON"));
console.log("render ok");
""" % json.dumps(str(EXAMPLES))
        proc = run_node(js)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("render ok", proc.stdout)
```

- [ ] **Step 3: Correr y verificar que falla** — `WowRender is not defined`.

- [ ] **Step 4: Implementar `<script id="wow-render">`** (reemplaza el tag vacío)

```html
<script id="wow-render">
const WowRender = (() => {
  "use strict";
  const C = WowCore;
  const arr = C.arr;
  const ENT = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"};
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (ch) => ENT[ch]);
  const safeUrl = (u) => (typeof u === "string" && /^https?:\/\//i.test(u) ? u : null);
  const isNum = (v) => typeof v === "number" && Number.isFinite(v);
  const fmt = (n) => (isNum(n) ? Math.round(n).toLocaleString("en-US") : "—");
  const fmtMs = (ms) => (!isNum(ms) ? "—" : ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`);
  const fmtUsd = (n) => `$${n.toFixed(2)}`;
  const RERUN = "this snapshot predates this panel; run wow snapshot again";
  const PLACES = {harness: "Harness (Claude/Codex)", "product-brain": "Product Brain", cursor: "Cursor",
                  human: "Human", terminal: "Terminal"};
  const STATUS = {
    approved: ["good", "✓", "approved"], changes_required: ["serious", "!", "changes required"],
    hitl: ["critical", "⚑", "HITL"], unknown: ["muted", "?", "unknown"], pending: ["muted", "…", "pending"],
    passing: ["good", "✓", "checks passing"], failing: ["critical", "✗", "checks failing"],
    running: ["warning", "…", "checks pending"], none: ["muted", "–", "no checks"],
    ok: ["good", "✓", "ok"], blocker: ["critical", "■", "blocker"],
  };

  function badge(kind, label) {
    const [cls, icon, text] = STATUS[kind] || STATUS.unknown;
    return `<span class="badge ${cls}"><span class="dot" aria-hidden="true"></span><span aria-hidden="true">${icon}</span> ${esc(label ?? text)}</span>`;
  }
  const noData = (reason) => `<div class="nodata" role="note"><strong>No data</strong><span>${esc(reason)}</span></div>`;
  const tip = (text) => `data-tip="${esc(text)}" tabindex="0"`;
  const link = (url, text) => (safeUrl(url) ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(text)}</a>` : esc(text));

  function panel(id, title, body, source, wide) {
    return `<section class="panel${wide ? " wide" : ""}" id="${id}" aria-labelledby="${id}-h">` +
      `<h2 id="${id}-h">${esc(title)}</h2>${body}` +
      (source ? `<p class="source">Source: ${esc(source)}</p>` : "") + `</section>`;
  }

  // ---- 1. Phase map -------------------------------------------------------
  function phaseMap(cur) {
    const plan = cur.plan || {};
    const cell = (state, text) => `<td class="ph ${state}" ${tip(text)}><span class="sr">${esc(state)}</span></td>`;
    const head = C.PHASES.map((p, i) => `<th scope="col">${i} ${esc(p)}</th>`).join("");
    const rows = [`<tr><th scope="row">Plan ${esc(plan.id || "")}</th>` + C.PHASES.map((p, i) => (i > 2
      ? `<td class="ph na"></td>`
      : cell(C.phaseState(plan.phase, i), `Plan · ${i} ${p}: ${C.phaseState(plan.phase, i)}`))).join("") + `</tr>`];
    for (const e of arr(cur.epics)) {
      const unknown = !isNum(e.phase) ? `unknown: ${e.reason || "no reason given"}` : null;
      rows.push(`<tr><th scope="row">${esc(e.id)} ${esc(e.title || "")}</th>` + C.PHASES.map((p, i) => {
        if (i < 3) return `<td class="ph na"></td>`;
        const state = C.phaseState(e.phase, i);
        const extra = state === "current" && e.progress ? ` (${e.progress} tasks)` : "";
        return cell(state, unknown || `${e.id} · ${i} ${p}: ${state}${extra}`);
      }).join("") + `</tr>`);
    }
    const legend = `<div class="legend"><span><i class="ph done"></i>done</span><span><i class="ph current"></i>current</span>` +
      `<span><i class="ph todo"></i>to do</span><span><i class="ph unknown"></i>unknown (source down)</span></div>`;
    const blockers = arr(cur.blockers).length
      ? `<h3>Blockers</h3><ul class="plain">${arr(cur.blockers).map((b) => `<li>${badge("blocker")} ${esc(b)}</li>`).join("")}</ul>`
      : "";
    const body = `<div class="scroll"><table class="phase-table"><thead><tr><th></th>${head}</tr></thead><tbody>${rows.join("")}</tbody></table></div>${legend}${blockers}` +
      (arr(cur.epics).length ? "" : noData("no epics yet: the manifest has none or does not exist"));
    return panel("panel-phase-map", "Phase map", body, "wow state (repo, Product Brain chat copies, Jira)", true);
  }

  // ---- 2. What's missing and where ---------------------------------------
  function nextSteps(cur) {
    const steps = arr(cur.next_steps);
    if (!steps.length) return panel("panel-next-steps", "What's missing and where", `<p>Nothing pending.</p>`, "wow state", true);
    const rows = steps.map((s) => `<tr><td><span class="place ${esc(s.where)}">${esc(PLACES[s.where] || s.where)}</span></td>` +
      `<td>${esc(s.epic ?? "plan")}</td><td class="num">${esc(s.phase)}</td><td>${esc(s.action)}</td>` +
      `<td>${esc(s.model ?? "—")}</td><td><code>${esc(s.command)}</code> <button class="copy" type="button" data-copy="${esc(s.command)}">Copy</button></td>` +
      `<td class="why">${esc(s.why)}</td></tr>`).join("");
    const total = isNum(cur.steps_total) && cur.steps_total > steps.length ? `<p class="source">Showing ${steps.length} of ${cur.steps_total} steps.</p>` : "";
    const body = `<div class="scroll"><table><thead><tr><th>Where</th><th>Epic</th><th class="num">Phase</th><th>Action</th>` +
      `<th>Model</th><th>Command</th><th>Why</th></tr></thead><tbody>${rows}</tbody></table></div>${total}`;
    return panel("panel-next-steps", "What's missing and where", body, "wow state", true);
  }

  // ---- 3. Where things live -----------------------------------------------
  function sourceBadge(value) {
    if (value === "ok") return badge("ok");
    if (value === "disabled" || value === "not_configured") return badge("none", value.replace("_", " "));
    return badge("changes_required", value);
  }
  function whereThingsLive(cur) {
    const sources = cur.sources || {};
    const srcRows = Object.keys(sources).map((k) => `<tr><th scope="row">${esc(k)}</th><td>${sourceBadge(String(sources[k]))}</td></tr>`);
    if (!("confluence" in sources)) srcRows.push(`<tr><th scope="row">confluence</th><td>${badge("none", "no data: not collected yet")}</td></tr>`);
    const epics = arr(cur.epics).map((e) => {
      const l = e.links || {};
      const jiraUrl = l.jira || e.jira_url;
      const jira = e.jira ? (safeUrl(jiraUrl) ? link(jiraUrl, e.jira) : `${esc(e.jira)} <span class="muted">(no URL: Jira not reachable)</span>`) : `<span class="muted">not exported to Jira yet</span>`;
      const prs = arr(l.prs).length
        ? `<ul class="plain">${arr(l.prs).map((p) => `<li>${link(p.url, `#${p.number} ${p.title}`)} <span class="muted">${esc(p.repo || "")} · ${esc(String(p.state || "").toLowerCase())}</span> ${badge(p.checks === "pending" ? "running" : p.checks || "none")}</li>`).join("")}</ul>`
        : `<span class="muted">no linked pull requests</span>`;
      const files = arr(l.files).length ? arr(l.files).map((f) => `<code>${esc(f)}</code>`).join(" ") : `<span class="muted">none yet</span>`;
      return `<h3>${esc(e.id)} ${esc(e.title || "")}</h3><dl class="kv"><dt>Jira</dt><dd>${jira}</dd><dt>Pull requests</dt><dd>${prs}</dd><dt>Repo</dt><dd>${files}</dd></dl>`;
    }).join("");
    const planFiles = arr((cur.plan || {}).links && cur.plan.links.files);
    const plan = `<h3>Plan</h3><p>${planFiles.length ? planFiles.map((f) => `<code>${esc(f)}</code>`).join(" ") : `<span class="muted">no plan files yet</span>`}</p>`;
    const body = `<table class="sources"><tbody>${srcRows.join("")}</tbody></table>${plan}${epics || noData("no epics yet")}`;
    return panel("panel-links", "Where things live", body, "Jira API, gh pr list, repo files (wow snapshot)");
  }

  // ---- 4. Velocity ---------------------------------------------------------
  function lineChart(points, label) {
    const W = 260, H = 120, L = 30, Rr = 34, T = 10, B = 20;
    const maxY = Math.max(1, ...points.map((p) => Math.max(p.done, isNum(p.total) ? p.total : 0)));
    const x = (i) => L + (points.length === 1 ? 0 : (i * (W - L - Rr)) / (points.length - 1));
    const y = (v) => H - B - (v * (H - T - B)) / maxY;
    const path = (key) => points.filter((p) => isNum(p[key])).map((p, i) => `${i ? "L" : "M"}${x(points.indexOf(p)).toFixed(1)},${y(p[key]).toFixed(1)}`).join("");
    const last = points[points.length - 1];
    const hits = points.map((p, i) => `<circle class="hit" cx="${x(i).toFixed(1)}" cy="${y(p.done).toFixed(1)}" r="8" ${tip(`${label} · ${String(p.ts).slice(0, 10)}: ${p.done} of ${fmt(p.total)} tasks · source: history`)}></circle>`).join("");
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)} burn-up: ${last.done} of ${fmt(last.total)} tasks">` +
      `<line class="grid" x1="${L}" x2="${W - Rr}" y1="${y(maxY)}" y2="${y(maxY)}"></line>` +
      `<line class="base" x1="${L}" x2="${W - Rr}" y1="${H - B}" y2="${H - B}"></line>` +
      `<text x="${L - 4}" y="${y(maxY) + 3}" text-anchor="end">${maxY}</text><text x="${L - 4}" y="${H - B + 3}" text-anchor="end">0</text>` +
      `<text x="${L}" y="${H - 4}">${esc(String(points[0].ts).slice(5, 10))}</text><text x="${W - Rr}" y="${H - 4}" text-anchor="end">${esc(String(last.ts).slice(5, 10))}</text>` +
      `<path class="scope" d="${path("total")}"></path><path class="line" d="${path("done")}"></path>` +
      `<circle class="end" cx="${x(points.length - 1).toFixed(1)}" cy="${y(last.done).toFixed(1)}" r="4"></circle>` +
      `<text class="label" x="${(x(points.length - 1) + 6).toFixed(1)}" y="${(y(last.done) + 3).toFixed(1)}">${last.done}/${fmt(last.total)}</text>${hits}</svg>`;
  }
  function roundedTop(x, y, w, h, r) {
    const rr = Math.min(r, w / 2, h);
    return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`;
  }
  function barChart(rows) {
    const W = 520, H = 140, L = 30, T = 16, B = 20;
    const max = Math.max(1, ...rows.map((r) => r.done));
    const step = (W - L) / rows.length;
    const bw = Math.min(40, step - 2);
    const bars = rows.map((r, i) => {
      const h = (r.done * (H - T - B)) / max;
      const x = L + i * step + (step - bw) / 2;
      const y = H - B - h;
      return (h > 0 ? `<path class="bar" d="${roundedTop(x, y, bw, h, 4)}"></path>` : "") +
        `<rect class="hit" x="${x}" y="${T}" width="${bw}" height="${H - T - B}" ${tip(`week of ${r.week}: ${r.done} tasks checked · source: history (tasks.md)`)}></rect>` +
        `<text class="label" x="${x + bw / 2}" y="${y - 4}" text-anchor="middle">${r.done}</text>` +
        `<text x="${x + bw / 2}" y="${H - 6}" text-anchor="middle">${esc(r.week.slice(5))}</text>`;
    }).join("");
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Weekly throughput"><line class="base" x1="${L}" x2="${W}" y1="${H - B}" y2="${H - B}"></line>${bars}</svg>`;
  }
  function velocity(doc) {
    const cur = doc.current;
    const history = arr(doc.history);
    const multiples = arr(cur.epics).map((e) => {
      const pts = C.burnup(history, e.id);
      return `<figure><figcaption>${esc(e.id)} ${esc(e.title || "")}</figcaption>` +
        (pts.length >= 2 ? lineChart(pts, e.id) : noData("needs at least two snapshots with task progress for this epic")) + `</figure>`;
    }).join("");
    const legend = `<div class="legend"><span><i class="swatch s1"></i>tasks done</span><span><i class="swatch dashed"></i>scope (total tasks)</span></div>`;
    const through = C.weeklyThroughput(history);
    const body = `<h3>Burn-up per epic</h3>${multiples ? legend + `<div class="multiples">${multiples}</div>` : noData("no epics yet")}` +
      `<h3>Weekly throughput (tasks checked in tasks.md)</h3>${through.length ? barChart(through) : noData("needs snapshots from at least two different weeks")}` +
      `<h3>Lead time per story</h3>${noData("needs Jira transition dates (not collected yet)")}`;
    return panel("panel-velocity", "Velocity", body, "progress.json history (one point per wow snapshot)");
  }

  // ---- 5. Quality ----------------------------------------------------------
  function quality(cur) {
    if (!Array.isArray(cur.reviews)) return panel("panel-quality", "Quality", noData(RERUN), "wow/reviews/*.json");
    const q = C.quality(cur.reviews);
    if (!q.total) return panel("panel-quality", "Quality", noData("no wow review has been recorded yet"), "wow/reviews/*.json");
    const rate = q.firstPassRate === null ? "—" : `${Math.round(q.firstPassRate * 100)}%`;
    const tiles = `<div class="tiles"><div class="tile"><div class="label">First-pass approval</div><div class="value">${rate}</div><div class="sub">${q.decided} decided reviews</div></div>` +
      `<div class="tile"><div class="label">Escalated to HITL</div><div class="value">${q.hitl}</div><div class="sub">after 3 rounds</div></div>` +
      `<div class="tile"><div class="label">Reviews</div><div class="value">${q.total}</div><div class="sub">story, epic, readiness, claims</div></div></div>`;
    const rows = q.rows.map((r) => {
      const final = r.final === "approved" ? "approved" : r.final === "hitl" ? "hitl" : "pending";
      const width = Math.max(4, (Math.min(3, r.rounds) / 3) * 100);
      return `<tr><td>${esc(r.ref)}</td><td>${esc(r.anchor_set ?? "—")}</td><td><span class="meter" ${tip(`${r.ref}: ${r.rounds} round(s), ${fmt(r.blockers)} blocker(s) · source: wow/reviews/${r.ref}.json`)}><span style="width:${width}%"></span></span> ${esc(r.rounds)}</td>` +
        `<td class="num">${fmt(r.blockers)}</td><td>${badge(final)}</td></tr>`;
    }).join("");
    const body = tiles + `<div class="scroll"><table><thead><tr><th>Ref</th><th>Set</th><th>Rounds (max 3)</th><th class="num">Blockers</th><th>Final</th></tr></thead><tbody>${rows}</tbody></table></div>`;
    return panel("panel-quality", "Quality", body, "wow/reviews/*.json (independent reviewer: Codex or Copilot)");
  }

  // ---- 6. LLM usage --------------------------------------------------------
  function roundedRight(x, y, w, h, r) {
    const rr = Math.min(r, h / 2, w);
    return `M${x},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h - rr}Q${x + w},${y + h} ${x + w - rr},${y + h}H${x}Z`;
  }
  function hbars(rows) {
    const W = 560, rowH = 26, LBL = 170, VAL = 90;
    const value = (r) => C.sumOrNull([r.tokens_in, r.tokens_out]);
    const max = Math.max(1, ...rows.map((r) => value(r) || 0));
    const H = rows.length * rowH + 4;
    const out = rows.map((r, i) => {
      const v = value(r);
      const y = i * rowH + 6;
      const label = `<text class="label" x="${LBL - 8}" y="${y + 11}" text-anchor="end">${esc(r.model ?? "unknown model")}</text>`;
      if (v === null) return label + `<text x="${LBL}" y="${y + 11}">no token data</text>`;
      const w = Math.max(2, (v / max) * (W - LBL - VAL));
      return label + `<path class="vbar v-${C.vendorKey(r.vendor)}" d="${roundedRight(LBL, y, w, 14, 4)}"></path>` +
        `<rect class="hit" x="${LBL}" y="${y - 4}" width="${W - LBL}" height="${rowH - 4}" ${tip(`${r.vendor} · ${r.model}: ${fmt(v)} tokens (in ${fmt(r.tokens_in)}, out ${fmt(r.tokens_out)}) over ${r.count} record(s) · source: wow usage`)}></rect>` +
        `<text class="label" x="${LBL + w + 6}" y="${y + 11}">${fmt(v)}</text>`;
    }).join("");
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Tokens in plus out per model">${out}</svg>`;
  }
  function latency(rows) {
    const timed = rows.filter((r) => isNum(r.median_ms));
    if (!timed.length) return noData("no response times recorded");
    const W = 560, rowH = 26, LBL = 170, VAL = 130;
    const max = Math.max(1, ...timed.map((r) => r.p95_ms));
    const x = (ms) => LBL + (ms / max) * (W - LBL - VAL);
    const out = timed.map((r, i) => {
      const y = i * rowH + 13;
      return `<text class="label" x="${LBL - 8}" y="${y + 4}" text-anchor="end">${esc(r.model)}</text>` +
        `<line class="range v-${C.vendorKey(r.vendor)}" x1="${x(r.median_ms)}" x2="${x(r.p95_ms)}" y1="${y}" y2="${y}"></line>` +
        `<circle class="dotm v-${C.vendorKey(r.vendor)}" cx="${x(r.median_ms)}" cy="${y}" r="4.5" ${tip(`${r.model}: median ${fmtMs(r.median_ms)}, p95 ${fmtMs(r.p95_ms)} over ${r.count} record(s) · source: wow usage`)}></circle>` +
        `<text class="label" x="${x(r.p95_ms) + 8}" y="${y + 4}">p50 ${fmtMs(r.median_ms)} · p95 ${fmtMs(r.p95_ms)}</text>`;
    }).join("");
    return `<svg viewBox="0 0 ${W} ${timed.length * rowH + 4}" role="img" aria-label="Response time per model">${out}</svg>`;
  }
  function usagePanel(doc) {
    const usage = arr(doc.usage);
    if (!usage.length) return panel("panel-usage", "LLM usage", noData("no usage records: run wow usage, then wow snapshot"), "wow usage", true);
    const rows = C.usageByModel(usage);
    const pools = C.poolTotals(usage);
    const cost = C.estimateCost(usage, doc.current.pricing);
    const costSub = (name) => (cost.available ? `${fmtUsd(cost.byPool[name])} estimated` : "cost: no data");
    const tiles = `<div class="tiles">` +
      `<div class="tile"><div class="label">Own accounts (Claude + Codex)</div><div class="value">${fmt(C.sumOrNull([pools.own.tokens_in, pools.own.tokens_out]))}</div><div class="sub">tokens in + out · ${pools.own.count} records · ${costSub("own")}</div></div>` +
      `<div class="tile pool-cursor"><div class="label">Cursor pool</div><div class="value">${fmt(C.sumOrNull([pools.cursor.tokens_in, pools.cursor.tokens_out]))}</div><div class="sub">tokens in + out · ${pools.cursor.count} runs · ${costSub("cursor")}</div></div></div>`;
    const costNote = cost.available
      ? `<p class="source">Costs are estimated from the price table as of ${esc(cost.as_of || "an unknown date")}; ${cost.unpriced} record(s) have no price and are excluded.</p>`
      : noData(cost.reason);
    const vendorsShown = [...new Set(rows.map((r) => C.vendorKey(r.vendor)))];
    const names = {anthropic: "Anthropic (Claude)", openai: "OpenAI (Codex)", cursor: "Cursor", other: "Other"};
    const legend = `<div class="legend">${vendorsShown.map((v) => `<span><i class="swatch v-${v}"></i>${names[v]}</span>`).join("")}</div>`;
    const table = `<div class="scroll"><table><thead><tr><th>Vendor</th><th>Model</th><th class="num">Records</th><th class="num">In</th><th class="num">Out</th>` +
      `<th class="num">Cache read</th><th class="num">Cache write</th><th class="num">Reasoning</th><th class="num">Median</th><th class="num">p95</th></tr></thead><tbody>` +
      rows.map((r) => `<tr><td>${esc(r.vendor)}</td><td>${esc(r.model)}</td><td class="num">${r.count}</td><td class="num">${fmt(r.tokens_in)}</td><td class="num">${fmt(r.tokens_out)}</td>` +
        `<td class="num">${fmt(r.cache_read)}</td><td class="num">${fmt(r.cache_write)}</td><td class="num">${fmt(r.reasoning_out)}</td><td class="num">${fmtMs(r.median_ms)}</td><td class="num">${fmtMs(r.p95_ms)}</td></tr>`).join("") +
      `</tbody></table></div><p class="source">Counters are shown as each tool reports them: Claude input excludes cache (see cache columns); Codex input includes cached tokens. "—" means the tool did not report it.</p>`;
    const epics = C.usageByEpic(usage);
    const epicTable = `<div class="scroll"><table><thead><tr><th>Epic (from ref)</th><th class="num">Own accounts</th><th class="num">Cursor pool</th></tr></thead><tbody>` +
      epics.map((e) => `<tr><td>${esc(e.epic)}</td><td class="num">${fmt(e.own)}</td><td class="num">${fmt(e.cursor)}</td></tr>`).join("") + `</tbody></table></div>`;
    const body = tiles + costNote + `<h3>Tokens in + out per model</h3>${legend}${hbars(rows)}` +
      `<h3>Response time per model (median to p95)</h3>${latency(rows)}<h3>All counters</h3>${table}<h3>Split by epic</h3>${epicTable}`;
    return panel("panel-usage", "LLM usage", body, "Claude Code transcripts, Codex sessions, cursor-agent JSON (wow usage)", true);
  }

  // ---- 7. Product Brain ----------------------------------------------------
  function productBrain(cur) {
    if (!cur.pb || typeof cur.pb !== "object") return panel("panel-pb", "Product Brain", noData(RERUN), "wow/pb/chats/");
    const rows = Object.keys(cur.pb).map((doc) => {
      const s = cur.pb[doc] || {};
      if (!s.present) return `<tr><td>${esc(doc)}</td><td colspan="6" class="muted">no local chat copy yet (wow/pb/chats/${esc(doc)}.md)</td></tr>`;
      const audit = s.audit ? badge(s.audit === "approved" ? "approved" : s.audit === "changes_required" ? "changes_required" : "unknown") : badge("pending", "not audited");
      return `<tr><td>${esc(doc)}</td><td>${s.closed ? "closed" : "open"}</td><td class="num">${isNum(s.completion_pct) ? `${s.completion_pct}%` : "—"}</td><td>${audit}</td>` +
        `<td class="num">${fmt(s.inventions)}</td><td class="num">${fmt(s.missing_anchors)}</td><td class="num">${fmt(s.open_questions)}</td></tr>`;
    }).join("");
    const body = `<div class="scroll"><table><thead><tr><th>Document</th><th>Chat</th><th class="num">PB completion</th><th>Audit</th>` +
      `<th class="num">Inventions</th><th class="num">Missing anchors</th><th class="num">Open questions</th></tr></thead><tbody>${rows}</tbody></table></div>` +
      `<p class="source">A closed chat is not done until its audit is approved: Product Brain checklists are not evidence.</p>`;
    return panel("panel-pb", "Product Brain", body, "wow/pb/chats/*.md and *.audit.json (wow pbchat audit)");
  }

  function renderAll(doc) {
    const cur = doc.current;
    return [phaseMap(cur), nextSteps(cur), whereThingsLive(cur), velocity(doc), quality(cur), usagePanel(doc), productBrain(cur)];
  }

  const warn = (list) => list.map((w) => `<div class="warn" role="alert">${esc(w)}</div>`).join("");

  function renderDoc(entry) {
    if (entry.error || !entry.doc) return {warnings: warn([`${entry.name}: ${entry.error || "empty file"}`]), html: ""};
    const v = C.validate(entry.doc);
    const warnings = warn(v.warnings.map((w) => `${entry.name}: ${w}`));
    return {warnings, html: v.ok ? renderAll(entry.doc).join("") : ""};
  }

  function portfolio(entries, active) {
    const rows = entries.map((e, i) => {
      const cur = e.doc && e.doc.current;
      const tokens = e.doc ? C.sumOrNull(arr(e.doc.usage).flatMap((r) => [r && r.tokens_in, r && r.tokens_out])) : null;
      const status = e.error ? esc(e.error) : esc(C.validate(e.doc).warnings.join("; ") || "ok");
      return `<tr${i === active ? ' aria-current="true"' : ""}><td><button type="button" data-select="${i}">${esc(e.name)}</button></td>` +
        `<td>${esc(cur && cur.plan ? cur.plan.id ?? "—" : "—")}</td><td class="num">${esc(cur && cur.plan ? cur.plan.phase : "—")}</td>` +
        `<td class="num">${cur ? arr(cur.epics).length : "—"}</td><td class="num">${cur ? arr(cur.next_steps).length : "—"}</td>` +
        `<td class="num">${fmt(tokens)}</td><td>${status}</td></tr>`;
    }).join("");
    return `<section class="panel wide" id="panel-portfolio"><h2>Portfolio (${entries.length} files)</h2><div class="scroll"><table><thead><tr>` +
      `<th>File</th><th>Plan</th><th class="num">Plan phase</th><th class="num">Epics</th><th class="num">Next steps</th><th class="num">Tokens</th><th>Status</th>` +
      `</tr></thead><tbody>${rows}</tbody></table></div></section>`;
  }

  return {esc, safeUrl, renderAll, renderDoc, portfolio};
})();
</script>
```

> Nota: el ejemplo `partial.json` trae `pb` pero no `reviews` ni `pricing`. Por eso Quality muestra "run wow snapshot again" y el costo sale "No data", que es justo el caso del Review Focus 3.

- [ ] **Step 5: Correr ambas suites** — exit 0. `RenderTest` imprime `render ok`.

- [ ] **Step 6: Commit (solo con ambas suites en 0)**

```bash
python3 -m unittest discover -s tests && /usr/bin/python3 -m unittest discover -s tests && \
git add dashboard/ tests/test_dashboard.py && \
git commit -m "feat(dashboard): render the seven panels from progress.json with example snapshots"
```

---

### Task 4: `wow-app`, estilos, README y verificación visual

**Files:**
- Modify: `dashboard/wow-dashboard.html` (`<style>` completo y `<script id="wow-app">`), `tests/test_dashboard.py`, `README.md`

**Interfaces:**
- Consumes: `WowRender.renderDoc` y `WowRender.portfolio` (Task 3).
- Produces el comportamiento del DOM:
  - drag&drop y selector de archivos (varios a la vez);
  - pestañas de portfolio vía `data-select`;
  - copiar vía `data-copy`, con fallback `execCommand`;
  - tooltip para `[data-tip]` en hover y foco, escrito siempre con `textContent`;
  - tema guardado en `localStorage` bajo `wow-theme`, dentro de try/catch;
  - imprimir.

- [ ] **Step 1: Escribir el test que falla** (agregar a `tests/test_dashboard.py`)

```python
class AppStaticTest(unittest.TestCase):
    def test_app_wiring_and_theme_tokens(self):
        app = script("wow-app")
        for needle in ("dragover", "drop", "data-select", "data-copy", "textContent", "wow-theme", "window.print"):
            self.assertIn(needle, app, needle)
        self.assertNotIn("innerHTML = entry", app)
        text = html_text()
        for needle in ('@media (prefers-color-scheme: dark)', ':root[data-theme="dark"]', "@media print",
                       "repeating-linear-gradient(45deg", "#1baf7a", "#199e70", "forced-colors"):
            self.assertIn(needle, text, needle)
```

- [ ] **Step 2: Correr y verificar que falla** — el `<script id="wow-app">` está vacío.

- [ ] **Step 3: Reemplazar el `<style>` mínimo por el definitivo**

```html
<style>
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11, 11, 11, 0.10); --hatch: rgba(11, 11, 11, 0.16);
  --s1: #2a78d6; --s2: #eb6834; --s3: #1baf7a;
  --good: #0ca30c; --warning: #fab219; --serious: #ec835a; --critical: #d03b3b;
  --v-anthropic: var(--s1); --v-openai: var(--s2); --v-cursor: var(--s3); --v-other: var(--muted);
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --border: rgba(255, 255, 255, 0.10); --hatch: rgba(255, 255, 255, 0.16);
    --s1: #3987e5; --s2: #d95926; --s3: #199e70;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19; --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #383835; --border: rgba(255, 255, 255, 0.10); --hatch: rgba(255, 255, 255, 0.16);
  --s1: #3987e5; --s2: #d95926; --s3: #199e70;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink); font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
a { color: var(--s1); }
header { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; justify-content: space-between; padding: 16px; }
header h1 { font-size: 18px; margin: 0; }
.controls { display: flex; flex-wrap: wrap; gap: 8px; }
button, .file { font: inherit; color: var(--ink); background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 6px 10px; cursor: pointer; }
button:focus-visible, .file:focus-within, [data-tip]:focus-visible { outline: 2px solid var(--s1); outline-offset: 2px; }
.file { position: relative; }
.file input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.drop { margin: 0 16px 16px; padding: 24px; border: 2px dashed var(--axis); border-radius: 10px; text-align: center; color: var(--ink-2); background: var(--surface); }
.drop.over { border-color: var(--s1); color: var(--ink); }
#warnings:empty, #portfolio:empty { display: none; }
.warn { margin: 0 16px 12px; padding: 10px 12px; border-left: 4px solid var(--warning); border-radius: 4px; background: var(--surface); }
#portfolio { padding: 0 16px 16px; }
main { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 520px), 1fr)); gap: 16px; padding: 0 16px 32px; }
.panel { min-width: 0; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }
.panel.wide { grid-column: 1 / -1; }
.panel h2 { font-size: 15px; margin: 0 0 12px; }
.panel h3 { font-size: 13px; font-weight: 600; margin: 18px 0 8px; color: var(--ink-2); }
.source, .muted { color: var(--muted); }
.source { margin: 12px 0 0; font-size: 12px; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--grid); vertical-align: top; }
th { color: var(--ink-2); font-weight: 600; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
td.why { color: var(--ink-2); min-width: 220px; }
tr[aria-current="true"] td { background: var(--page); }
code { font: 12px ui-monospace, SFMono-Regular, Menlo, monospace; word-break: break-word; }
ul.plain { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }
dl.kv { display: grid; grid-template-columns: max-content 1fr; gap: 4px 12px; margin: 0; }
dl.kv dt { color: var(--ink-2); }
dl.kv dd { margin: 0; min-width: 0; }
table.sources { width: auto; }
.nodata { display: flex; flex-direction: column; gap: 2px; padding: 14px 16px; border: 1px solid var(--border); border-radius: 8px; color: var(--ink-2); background: repeating-linear-gradient(45deg, var(--hatch) 0 2px, transparent 2px 8px); }
.nodata strong { color: var(--ink); }
.badge { display: inline-flex; align-items: center; gap: 4px; padding: 1px 8px; border: 1px solid var(--border); border-radius: 999px; font-size: 12px; white-space: nowrap; }
.badge .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--muted); }
.badge.good .dot { background: var(--good); }
.badge.warning .dot { background: var(--warning); }
.badge.serious .dot { background: var(--serious); }
.badge.critical .dot { background: var(--critical); }
.place { display: inline-block; padding: 1px 8px; border: 1px solid var(--border); border-radius: 4px; font-size: 12px; white-space: nowrap; }
.place.cursor { box-shadow: inset 4px 0 0 var(--v-cursor); padding-left: 10px; }
.copy { padding: 1px 6px; font-size: 12px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 8px; margin-bottom: 8px; }
.tile { padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; }
.tile .label { font-size: 12px; color: var(--ink-2); }
.tile .value { font-size: 22px; font-weight: 600; }
.tile .sub { font-size: 12px; color: var(--muted); }
.tile.pool-cursor { box-shadow: inset 4px 0 0 var(--v-cursor); }
.phase-table td.ph { min-width: 56px; height: 28px; border: 2px solid var(--surface); border-radius: 6px; }
.ph.done { background: var(--s1); }
.ph.current { background: var(--surface); box-shadow: inset 0 0 0 2px var(--s1); }
td.ph.current::after { content: ""; display: block; width: 8px; height: 8px; margin: auto; border-radius: 50%; background: var(--s1); }
.ph.todo { background: var(--grid); }
.ph.unknown { background: repeating-linear-gradient(45deg, var(--hatch) 0 2px, transparent 2px 8px); box-shadow: inset 0 0 0 1px var(--border); }
.ph.na { background: transparent; }
.legend { display: flex; flex-wrap: wrap; gap: 12px; margin: 8px 0; font-size: 12px; color: var(--ink-2); }
.legend i { display: inline-block; width: 12px; height: 12px; margin-right: 4px; vertical-align: -2px; border-radius: 3px; }
.legend i.ph.current { box-shadow: inset 0 0 0 2px var(--s1); }
.swatch.s1 { background: var(--s1); }
.swatch.dashed { height: 0 !important; border-top: 2px dashed var(--muted); border-radius: 0 !important; vertical-align: 3px !important; }
.swatch.v-anthropic { background: var(--v-anthropic); }
.swatch.v-openai { background: var(--v-openai); }
.swatch.v-cursor { background: var(--v-cursor); }
.swatch.v-other { background: var(--v-other); }
.meter { display: inline-block; width: 90px; height: 8px; border-radius: 4px; background: var(--grid); vertical-align: middle; }
.meter span { display: block; height: 100%; border-radius: 4px; background: var(--s1); }
.multiples { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 240px), 1fr)); gap: 12px; }
figure { margin: 0; }
figcaption { font-size: 12px; color: var(--ink-2); margin-bottom: 4px; }
svg { display: block; width: 100%; height: auto; overflow: visible; }
svg text { fill: var(--muted); font-size: 10px; }
svg text.label { fill: var(--ink-2); }
svg .grid { stroke: var(--grid); stroke-width: 1; }
svg .base { stroke: var(--axis); stroke-width: 1; }
svg .scope { fill: none; stroke: var(--muted); stroke-width: 1.5; stroke-dasharray: 4 3; }
svg .line { fill: none; stroke: var(--s1); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
svg .end { fill: var(--s1); stroke: var(--surface); stroke-width: 2; }
svg .bar { fill: var(--s1); }
svg .vbar.v-anthropic, svg .dotm.v-anthropic { fill: var(--v-anthropic); }
svg .vbar.v-openai, svg .dotm.v-openai { fill: var(--v-openai); }
svg .vbar.v-cursor, svg .dotm.v-cursor { fill: var(--v-cursor); }
svg .vbar.v-other, svg .dotm.v-other { fill: var(--v-other); }
svg .dotm { stroke: var(--surface); stroke-width: 2; }
svg .range { stroke-width: 2; stroke-linecap: round; }
svg .range.v-anthropic { stroke: var(--v-anthropic); }
svg .range.v-openai { stroke: var(--v-openai); }
svg .range.v-cursor { stroke: var(--v-cursor); }
svg .range.v-other { stroke: var(--v-other); }
svg .hit { fill: transparent; cursor: default; }
svg .hit:hover, svg .hit:focus { fill: var(--s1); fill-opacity: 0.12; outline: none; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
#tip { position: fixed; z-index: 10; max-width: 340px; padding: 6px 8px; border-radius: 6px; background: var(--ink); color: var(--surface); font-size: 12px; pointer-events: none; }
@media print {
  :root, :root[data-theme] {
    color-scheme: light;
    --page: #ffffff; --surface: #ffffff; --ink: #0b0b0b; --ink-2: #52514e; --grid: #e1e0d9; --axis: #c3c2b7;
    --border: rgba(11, 11, 11, 0.10); --hatch: rgba(11, 11, 11, 0.16); --s1: #2a78d6; --s2: #eb6834; --s3: #1baf7a;
  }
  header .controls, .drop, #tip, .copy, #portfolio { display: none !important; }
  main { display: block; padding: 0; }
  .panel { margin-bottom: 12px; break-inside: avoid; }
}
@media (forced-colors: active) {
  .ph.done { background: CanvasText; }
  .ph.current { box-shadow: inset 0 0 0 2px CanvasText; }
  .nodata, .ph.unknown { border: 1px dashed CanvasText; }
}
</style>
```

- [ ] **Step 4: Implementar `<script id="wow-app">`** (reemplaza el tag vacío)

```html
<script id="wow-app">
(() => {
  "use strict";
  const state = {docs: [], active: 0};
  const $ = (sel) => document.querySelector(sel);
  const root = document.documentElement;
  const tipEl = $("#tip");

  function setTheme(theme) {
    root.dataset.theme = theme;
    try { localStorage.setItem("wow-theme", theme); } catch (e) { /* storage unavailable: theme lasts this visit */ }
  }
  try {
    const saved = localStorage.getItem("wow-theme");
    if (saved === "light" || saved === "dark") root.dataset.theme = saved;
  } catch (e) { /* storage unavailable */ }

  $("#theme").addEventListener("click", () => {
    const current = root.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    setTheme(current === "dark" ? "light" : "dark");
  });
  $("#print").addEventListener("click", () => window.print());

  function render() {
    $("#portfolio").innerHTML = state.docs.length > 1 ? WowRender.portfolio(state.docs, state.active) : "";
    const current = state.docs[state.active];
    const out = current ? WowRender.renderDoc(current) : {warnings: "", html: ""};
    $("#warnings").innerHTML = out.warnings;
    $("#panels").innerHTML = out.html;
  }

  async function load(files) {
    const list = [...files].filter(Boolean);
    if (!list.length) return;
    for (const file of list) {
      try {
        state.docs.push({name: file.name, doc: JSON.parse(await file.text())});
      } catch (e) {
        state.docs.push({name: file.name, doc: null, error: "not valid JSON"});
      }
    }
    state.active = state.docs.length - 1;
    render();
  }

  const drop = $("#drop");
  for (const type of ["dragenter", "dragover"]) {
    document.addEventListener(type, (event) => { event.preventDefault(); drop.classList.add("over"); });
  }
  document.addEventListener("dragleave", (event) => { if (!event.relatedTarget) drop.classList.remove("over"); });
  document.addEventListener("drop", (event) => {
    event.preventDefault();
    drop.classList.remove("over");
    load(event.dataTransfer ? event.dataTransfer.files : []);
  });
  $("#file").addEventListener("change", (event) => { load(event.target.files); event.target.value = ""; });

  function copy(text, button) {
    const done = () => { button.textContent = "Copied"; setTimeout(() => { button.textContent = "Copy"; }, 1200); };
    const fallback = () => {
      const area = document.createElement("textarea");
      area.value = text;
      document.body.appendChild(area);
      area.select();
      try { document.execCommand("copy"); done(); } catch (e) { button.textContent = "Select and copy"; }
      area.remove();
    };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, fallback);
    else fallback();
  }

  document.addEventListener("click", (event) => {
    const copyButton = event.target.closest("[data-copy]");
    if (copyButton) { copy(copyButton.getAttribute("data-copy"), copyButton); return; }
    const select = event.target.closest("[data-select]");
    if (select) { state.active = Number(select.getAttribute("data-select")); render(); }
  });

  function showTip(target, x, y) {
    tipEl.textContent = target.getAttribute("data-tip");
    tipEl.hidden = false;
    const box = tipEl.getBoundingClientRect();
    tipEl.style.left = `${Math.max(8, Math.min(x + 12, innerWidth - box.width - 8))}px`;
    tipEl.style.top = `${Math.max(8, Math.min(y + 12, innerHeight - box.height - 8))}px`;
  }
  document.addEventListener("mousemove", (event) => {
    const target = event.target.closest && event.target.closest("[data-tip]");
    if (target) showTip(target, event.clientX, event.clientY); else tipEl.hidden = true;
  });
  document.addEventListener("focusin", (event) => {
    const target = event.target.closest && event.target.closest("[data-tip]");
    if (!target) { tipEl.hidden = true; return; }
    const r = target.getBoundingClientRect();
    showTip(target, r.left, r.bottom);
  });
  document.addEventListener("focusout", () => { tipEl.hidden = true; });
})();
</script>
```

- [ ] **Step 5: Agregar a `README.md`** (sección nueva después del bloque de uso)

````markdown
## Dashboard

Abrí `dashboard/wow-dashboard.html` en el navegador y arrastrá uno o varios `wow/progress.json`
(los genera `wow snapshot`). No usa red: una Content-Security-Policy bloquea toda conexión saliente.
Con varios archivos aparece la vista de portfolio. En `dashboard/examples/` hay tres snapshots de ejemplo.

Para ver costos estimados, cargá una tabla de precios (USD por millón de tokens) en `.wow/config.json`:

```json
{"pricing": {"as_of": "2026-10-01", "per_mtok": {"claude-opus-5-5": {"in": 15, "out": 75, "cache_read": 1.5, "cache_write": 18.75}}}}
```
````

- [ ] **Step 6: Verificación visual (dataviz paso 7)**

Abrir `file://…/dashboard/wow-dashboard.html` con el navegador del harness (Playwright) y cargar los tres ejemplos con el input de archivo. Revisar, con capturas:
1. **`full.json` en tema claro:** sin etiquetas pisadas, sin scroll horizontal de página a 390 px de ancho, tooltip visible al pasar sobre una barra.
2. **`full.json` en tema oscuro** (botón Toggle theme).
3. **Los tres archivos a la vez:** aparece el portfolio y cambia la vista al tocar un nombre.
4. **`empty.json`:** "No data" rayado con motivo.

Si algo se ve mal, corregir el CSS o el render en esta misma tarea, antes del commit.

- [ ] **Step 7: Correr ambas suites** — exit 0.

- [ ] **Step 8: Commit (solo con ambas suites en 0)**

```bash
python3 -m unittest discover -s tests && /usr/bin/python3 -m unittest discover -s tests && \
git add dashboard/wow-dashboard.html tests/test_dashboard.py README.md && \
git commit -m "feat(dashboard): add drag-and-drop loading, theming, tooltips and print styles"
```

---

## Fuera de este plan

- Throughput y lead time con fechas de transición de Jira (requiere ampliar `JiraClient`).
- Reparto de consumo por fase (requiere que los registros de uso traigan la fase).
- Fuente Confluence.
- Actualizar `docs/site/way-of-work.html` del repo SPECKIT con capturas del dashboard.
