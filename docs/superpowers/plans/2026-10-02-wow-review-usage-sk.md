# WayOfWork · Plan 2: review independiente, consumo de LLM y Spec-Kit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar al CLI `wow` el protocolo de review anclado (`wow review`), la medición de consumo de Claude, Codex y Cursor (`wow usage` + snapshot), la ejecución medida de Work Units (`wow run-wu`) y la preparación de comandos de Spec-Kit (`wow sk`), con las skills `wow-review` y `wow-sk-prep`.

**Architecture:** Mismos módulos planos de `wow/` del Plan 1. El review se parte en tres módulos con una responsabilidad cada uno: `review.py` (parseo y reglas de rondas, puro), `packets.py` (anclas y contenido a revisar, lee repo y git) y `reviewers.py` (invoca el CLI revisor con dry-run). Todo proceso externo (`git`, `codex`, `copilot`, `cursor-agent`) se invoca con un `runner` inyectable, así los tests no llaman modelos reales.

**Tech Stack:** Python 3.9+ stdlib (`subprocess`, `shutil`, `shlex`, `tempfile`, `hashlib`, `json`, `re`, `datetime`, `unittest`).

**Spec:** `docs/superpowers/specs/2026-10-01-wayofwork-design.md` (secciones 7.2, 7.3, 9, 9.1, 9.4, 10, 11, 12). Plan anterior: `docs/superpowers/plans/2026-10-01-wow-core-guide.md` (ya implementado: `config`, `manifest`, `sources/*`, `state`, `snapshot`, `cli`).

## Global Constraints

- Python compatible con **3.9** (`/usr/bin/python3` = 3.9.6) y con el `python3` de Homebrew; `from __future__ import annotations` en todo módulo; sin `match` ni `X | Y` en runtime.
- Solo biblioteca estándar; tests con `unittest`. Ningún test llama un modelo real ni la red: los procesos externos se reemplazan con scripts Python temporales o con un `runner` falso.
- Código, comentarios, mensajes, schemas y `SKILL.md` en **inglés**; README en **castellano**.
- Exit codes (D8): `0` OK · `1` hallazgos/cambios requeridos/HITL · `2` no pude evaluar.
- `wow` nunca escribe en Jira, Confluence ni artefactos de Spec-Kit. Escrituras permitidas en este plan: `wow/reviews/*.json`, `.wow/reviews/**` (crudo, gitignored), `wow/plan/manifest.json` (solo `plan.readiness`), `harness/runs/*.json`, `wow/progress.json`.
- Revisores (D7): orden de `cfg["reviewers"]` (por defecto `codex`, `copilot`); los nombres `claude` y `cursor` se ignoran siempre (autorrevisión y pool escaso). Sin revisor disponible → exit 2.
- Privacidad (D11): los registros de consumo y de corridas guardan **solo números y metadatos**, nunca texto de prompts ni respuestas.
- Sin dato = `null`, nunca `0` (D12).
- Commits: Conventional Commits **sin** atribución de IA, uno por tarea, en `main` del repo `WayOfWork` (el operador autorizó commitear).
- Suite completa: `python3 -m unittest discover -s tests` y `/usr/bin/python3 -m unittest discover -s tests`, desde la raíz de `WayOfWork/`.

## Review Focus

1. **El revisor devuelve texto que no respeta el formato** (sin línea `VERDICT:`) → `wow review` sale con `2`, guarda el crudo y **no** registra una ronda. Test en Task 4.
2. **Se relanza el review sin haber cambiado el diff** después de un BLOCKER válido → no abre ronda nueva, sale con `1` y dice qué ronda sigue abierta. Test en Task 1 y Task 4.
3. **Transcript de Claude con un mismo mensaje partido en varias líneas** (mismo `message.id`, una línea por bloque de contenido) → se cuenta una sola vez. Test en Task 5.
4. **Sesión de Codex con eventos `token_count` repetidos con el mismo total** → los tokens del turno no se duplican. Test en Task 5.
5. **`cursor-agent` no instalado o con salida que no es JSON** → `wow run-wu` sale con `2` (no instalado) o registra la corrida con `result: null` (salida inválida), sin guardar el texto de la respuesta. Test en Task 7.

---

## File Structure

```
WayOfWork/
├── wow/
│   ├── review.py          parseo de veredicto, anclas, rondas, resumen — Task 1
│   ├── packets.py         anclas + contenido por conjunto, git diff, prompt — Task 2
│   ├── reviewers.py       comandos de revisores, dry-run, selección — Task 3
│   ├── usage.py           colectores Claude / Codex / Cursor — Task 5
│   ├── runwu.py           wrapper medido de cursor-agent — Task 7
│   ├── sk.py              estado y comandos de Spec-Kit — Task 8
│   ├── snapshot.py        (modificar) build acepta usage — Task 6
│   └── cli.py             (modificar) review, usage, run-wu, sk — Tasks 4, 6, 7, 8
├── schemas/progress.schema.json   (modificar) usage-record — Task 6
├── skills/wow-review/SKILL.md     Task 4
├── skills/wow-sk-prep/SKILL.md    Task 8
├── README.md                      (modificar) Task 8
└── tests/
    ├── test_review.py      Task 1
    ├── test_packets.py     Task 2
    ├── test_reviewers.py   Task 3
    ├── test_usage.py       Task 5
    ├── test_runwu.py       Task 7
    ├── test_sk.py          Task 8
    ├── test_snapshot.py    (modificar) Task 6
    └── test_cli.py         (modificar) Tasks 4, 6, 7, 8
```

---

### Task 1: `review.py` — veredicto, anclas y reglas de rondas

**Files:**
- Create: `wow/review.py`, `tests/test_review.py`

**Interfaces:**
- Produces:
  - `review.MAX_ROUNDS = 3`
  - `review.ReviewOutputError(Exception)`
  - `review.parse_verdict(text: str) -> dict` → `{"verdict": "APPROVED"|"CHANGES_REQUIRED"|None, "blockers": [{"anchor", "path_line", "text"}], "warnings": [{"path_line", "text"}], "nits": [str]}`. Acepta `—`, `–` o `-` como separador.
  - `review.new_summary(ref: str, anchor_set: str) -> dict` → `{"schema_version": 1, "ref", "anchor_set", "rounds": [], "final": None}`
  - `review.load_summary(project: Path, ref: str, anchor_set: str) -> dict` (de `wow/reviews/<ref>.json`; ausente o inválido → `new_summary`)
  - `review.save_summary(project: Path, summary: dict) -> Path`
  - `review.next_action(summary: dict, diff_hash: str) -> str` ∈ `{"done", "hitl", "wait_for_changes", "run"}`
  - `review.record_round(summary: dict, parsed: dict, anchors: Iterable[str], diff_hash: str) -> dict` (copia; si `parsed["verdict"] is None` → `ReviewOutputError`). Un BLOCKER con ancla desconocida pasa a WARNING con prefijo `[downgraded: unknown anchor X] `. La ronda queda `APPROVED` con cero BLOCKER válidos (aunque el revisor haya dicho otra cosa); `final = "approved"` en ese caso, `final = "hitl"` si la ronda 3 tiene BLOCKER válidos.

- [ ] **Step 1: Escribir el test que falla**

`tests/test_review.py`:

```python
from __future__ import annotations

import unittest

from helpers import make_project, write
import review

OUTPUT = """Some preface the model added.
VERDICT: CHANGES_REQUIRED
BLOCKER AC1 src/api.py:42 — returns 500 instead of 404 for a missing id
BLOCKER AC9 src/api.py:50 - not an existing anchor
WARNING src/api.py:10 – long function
NIT — rename variable x
"""


class ParseTest(unittest.TestCase):
    def test_parses_all_kinds_and_separators(self):
        parsed = review.parse_verdict(OUTPUT)
        self.assertEqual(parsed["verdict"], "CHANGES_REQUIRED")
        self.assertEqual(parsed["blockers"], [
            {"anchor": "AC1", "path_line": "src/api.py:42", "text": "returns 500 instead of 404 for a missing id"},
            {"anchor": "AC9", "path_line": "src/api.py:50", "text": "not an existing anchor"},
        ])
        self.assertEqual(parsed["warnings"], [{"path_line": "src/api.py:10", "text": "long function"}])
        self.assertEqual(parsed["nits"], ["rename variable x"])

    def test_missing_verdict(self):
        self.assertIsNone(review.parse_verdict("looks fine to me")["verdict"])


class RoundsTest(unittest.TestCase):
    def test_unknown_anchor_is_downgraded_and_round_recorded(self):
        summary = review.record_round(review.new_summary("IRIS-41", "story"),
                                      review.parse_verdict(OUTPUT), {"AC1", "AC2"}, "h1")
        rnd = summary["rounds"][0]
        self.assertEqual((rnd["n"], rnd["verdict"], rnd["diff_hash"]), (1, "CHANGES_REQUIRED", "h1"))
        self.assertEqual([b["anchor"] for b in rnd["blockers"]], ["AC1"])
        self.assertTrue(rnd["warnings"][0]["text"].startswith("[downgraded: unknown anchor AC9] "))
        self.assertIsNone(summary["final"])

    def test_zero_valid_blockers_approves_even_if_model_said_changes(self):
        text = "VERDICT: CHANGES_REQUIRED\nBLOCKER AC9 a.py:1 — prose only\n"
        summary = review.record_round(review.new_summary("IRIS-41", "story"), review.parse_verdict(text), {"AC1"}, "h")
        self.assertEqual(summary["rounds"][0]["verdict"], "APPROVED")
        self.assertEqual(summary["final"], "approved")

    def test_unparseable_output_raises(self):
        with self.assertRaises(review.ReviewOutputError):
            review.record_round(review.new_summary("x", "story"), review.parse_verdict("hello"), set(), "h")

    def test_third_round_with_blocker_escalates_to_hitl(self):
        summary = review.new_summary("IRIS-41", "story")
        blocked = review.parse_verdict("VERDICT: CHANGES_REQUIRED\nBLOCKER AC1 a.py:1 — still broken\n")
        for n in range(3):
            summary = review.record_round(summary, blocked, {"AC1"}, f"h{n}")
        self.assertEqual(summary["final"], "hitl")
        self.assertEqual(review.next_action(summary, "h9"), "hitl")

    def test_next_action_rules(self):
        empty = review.new_summary("IRIS-41", "story")
        self.assertEqual(review.next_action(empty, "h1"), "run")
        blocked = review.record_round(empty, review.parse_verdict("VERDICT: CHANGES_REQUIRED\nBLOCKER AC1 a:1 — x\n"),
                                      {"AC1"}, "h1")
        self.assertEqual(review.next_action(blocked, "h1"), "wait_for_changes")
        self.assertEqual(review.next_action(blocked, "h2"), "run")
        approved = review.record_round(empty, review.parse_verdict("VERDICT: APPROVED\n"), {"AC1"}, "h1")
        self.assertEqual(review.next_action(approved, "h1"), "done")

    def test_summary_round_trip_and_invalid_file(self):
        project = make_project()
        summary = review.record_round(review.new_summary("E1", "epic"), review.parse_verdict("VERDICT: APPROVED\n"),
                                      {"E1.C1"}, "h")
        review.save_summary(project, summary)
        self.assertEqual(review.load_summary(project, "E1", "epic")["final"], "approved")
        write(project, "wow/reviews/E2.json", "{bad")
        self.assertEqual(review.load_summary(project, "E2", "epic"), review.new_summary("E2", "epic"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `python3 -m unittest discover -s tests`
Expected: ERROR `No module named 'review'`.

- [ ] **Step 3: Implementar `wow/review.py`**

```python
"""Anchored review protocol: verdict parsing and round rules (spec 9.1, D6)."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Iterable

MAX_ROUNDS = 3
_SEP = r"\s+[—–-]+\s*"
_VERDICT_RE = re.compile(r"^\s*VERDICT:\s*(APPROVED|CHANGES_REQUIRED)\s*$", re.MULTILINE)
_BLOCKER_RE = re.compile(r"^\s*BLOCKER\s+(\S+)\s+(\S+)" + _SEP + r"(.+?)\s*$")
_WARNING_RE = re.compile(r"^\s*WARNING\s+(\S+)" + _SEP + r"(.+?)\s*$")
_NIT_RE = re.compile(r"^\s*NIT" + _SEP + r"(.+?)\s*$")


class ReviewOutputError(Exception):
    """The reviewer output has no VERDICT line, so no round can be recorded."""


def parse_verdict(text: str) -> dict:
    verdict = _VERDICT_RE.search(text)
    parsed = {"verdict": verdict.group(1) if verdict else None, "blockers": [], "warnings": [], "nits": []}
    for line in text.splitlines():
        blocker = _BLOCKER_RE.match(line)
        if blocker:
            parsed["blockers"].append({"anchor": blocker.group(1), "path_line": blocker.group(2),
                                       "text": blocker.group(3)})
            continue
        warning = _WARNING_RE.match(line)
        if warning:
            parsed["warnings"].append({"path_line": warning.group(1), "text": warning.group(2)})
            continue
        nit = _NIT_RE.match(line)
        if nit:
            parsed["nits"].append(nit.group(1))
    return parsed


def new_summary(ref: str, anchor_set: str) -> dict:
    return {"schema_version": 1, "ref": ref, "anchor_set": anchor_set, "rounds": [], "final": None}


def _path(project: Path, ref: str) -> Path:
    return project / "wow" / "reviews" / f"{ref}.json"


def load_summary(project: Path, ref: str, anchor_set: str) -> dict:
    path = _path(project, ref)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "rounds" in data:
                return data
        except json.JSONDecodeError:
            pass
    return new_summary(ref, anchor_set)


def save_summary(project: Path, summary: dict) -> Path:
    path = _path(project, summary["ref"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def next_action(summary: dict, diff_hash: str) -> str:
    if summary["final"] == "approved":
        return "done"
    if summary["final"] == "hitl":
        return "hitl"
    rounds = summary["rounds"]
    if rounds and rounds[-1]["blockers"] and rounds[-1]["diff_hash"] == diff_hash:
        return "wait_for_changes"
    return "run"


def record_round(summary: dict, parsed: dict, anchors: Iterable[str], diff_hash: str) -> dict:
    if parsed["verdict"] is None:
        raise ReviewOutputError("reviewer output has no 'VERDICT:' line")
    known = set(anchors)
    valid = [b for b in parsed["blockers"] if b["anchor"] in known]
    warnings = list(parsed["warnings"])
    for blocker in parsed["blockers"]:
        if blocker["anchor"] not in known:
            warnings.append({"path_line": blocker["path_line"],
                             "text": f"[downgraded: unknown anchor {blocker['anchor']}] {blocker['text']}"})
    result = copy.deepcopy(summary)
    number = len(result["rounds"]) + 1
    result["rounds"].append({"n": number, "verdict": "CHANGES_REQUIRED" if valid else "APPROVED",
                             "blockers": valid, "warnings": warnings, "nits": list(parsed["nits"]),
                             "diff_hash": diff_hash})
    if not valid:
        result["final"] = "approved"
    elif number >= MAX_ROUNDS:
        result["final"] = "hitl"
    return result
```

- [ ] **Step 4: Correr y verificar que pasa** — `python3 -m unittest discover -s tests` → todo OK.

- [ ] **Step 5: Commit**

```bash
python3 -m unittest discover -s tests && /usr/bin/python3 -m unittest discover -s tests
git add wow/review.py tests/test_review.py
git commit -m "feat(review): parse anchored verdicts and apply round rules"
```

---

### Task 2: `packets.py` — anclas y contenido por conjunto

**Files:**
- Create: `wow/packets.py`, `tests/test_packets.py`

**Interfaces:**
- Consumes: `manifest.load` (Plan 1).
- Produces:
  - `packets.PacketError(Exception)`
  - `packets.READINESS: dict[str, str]` — R1–R5. **R5 difiere de `ic` v2**: el manifiesto de WayOfWork no tiene `verify` (es solo upstream), así que R5 = "every task has estimate, priority and labels", que es lo que `/spec-kit.sync` audita.
  - `packets.Packet` = `dict` con `{"anchor_set", "ref", "anchors": {id: text}, "body": str, "cwd": Path}`.
  - `packets.readiness_packet(project: Path) -> Packet` (body = `wow/plan/PLAN.md` si existe + manifiesto)
  - `packets.story_packet(project: Path, key: str, repo: Path, base: str, runner=subprocess.run) -> Packet` (anclas `ACn` de la sección de `specs/*/spec.md` cuyo encabezado contiene la key; body = `git diff <base>` en `repo`)
  - `packets.epic_packet(project: Path, epic_id: str, repo: Path, base: str, runner=subprocess.run) -> Packet` (anclas = `done_when` del manifiesto)
  - `packets.claims_packet(doc: Path, repo: Path) -> Packet` (anclas `Cn` de líneas `C12: …`, `- C12: …` o `**C12**: …`; body = el documento; el revisor verifica contra el código de `repo`)
  - `packets.git_diff(repo: Path, base: str, runner=subprocess.run) -> str` (error de git o diff vacío → `PacketError`)
  - `packets.diff_hash(text: str) -> str` (16 hex de SHA-256)
  - `packets.build_prompt(packet: Packet) -> str`

- [ ] **Step 1: Escribir el test que falla**

`tests/test_packets.py`:

```python
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from helpers import make_project, write
import manifest
import packets
from test_manifest import valid_doc

SPEC = """# Spec
## User stories
### Story 1: [IRIS-41] Analyst curates a case
Acceptance criteria:
- AC1: the case moves to curated
- AC2: an audit row is written
### Story 2: [IRIS-42] Export
- AC1: CSV is produced
"""


def git_repo_with_change() -> Path:
    repo = make_project()
    run = lambda *a: subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *a],
                                    check=True, capture_output=True, text=True)
    run("init", "-q", "-b", "main")
    write(repo, "app.py", "print('v1')\n")
    run("add", "-A")
    run("commit", "-q", "-m", "base")
    write(repo, "app.py", "print('v2')\n")
    return repo


class StoryPacketTest(unittest.TestCase):
    def test_anchors_from_story_section_and_diff(self):
        project = make_project()
        write(project, "specs/001-x/spec.md", SPEC)
        packet = packets.story_packet(project, "IRIS-41", git_repo_with_change(), "main")
        self.assertEqual(packet["anchors"], {"AC1": "the case moves to curated", "AC2": "an audit row is written"})
        self.assertIn("+print('v2')", packet["body"])

    def test_story_without_anchors_raises(self):
        project = make_project()
        write(project, "specs/001-x/spec.md", "### Story 9: [IRIS-49] nothing\n")
        with self.assertRaises(packets.PacketError):
            packets.story_packet(project, "IRIS-49", git_repo_with_change(), "main")

    def test_empty_diff_raises(self):
        project = make_project()
        write(project, "specs/001-x/spec.md", SPEC)
        repo = git_repo_with_change()
        subprocess.run(["git", "-C", str(repo), "checkout", "--", "app.py"], check=True)
        with self.assertRaises(packets.PacketError):
            packets.story_packet(project, "IRIS-41", repo, "main")


class OtherPacketsTest(unittest.TestCase):
    def test_epic_anchors_from_manifest(self):
        project = make_project()
        manifest.save(project, valid_doc())
        packet = packets.epic_packet(project, "E1", git_repo_with_change(), "main")
        self.assertEqual(packet["anchors"], {"E1.C1": "analysts can curate"})

    def test_readiness_anchors_and_body(self):
        project = make_project()
        manifest.save(project, valid_doc())
        write(project, "wow/plan/PLAN.md", "## Brief\n- Goal: x\n")
        packet = packets.readiness_packet(project)
        self.assertEqual(sorted(packet["anchors"]), ["R1", "R2", "R3", "R4", "R5"])
        self.assertIn("## Brief", packet["body"])
        self.assertIn('"0001-iris-v2"', packet["body"])

    def test_claims_anchor_formats(self):
        project = make_project()
        doc = write(project, "wow/context-pack/facts.md",
                    "C1: auth uses Nucleus profiles [MEDIDO]\n- C2: no API gateway\n**C3**: DynamoDB pk+sk\nnot a claim\n")
        packet = packets.claims_packet(doc, project)
        self.assertEqual(sorted(packet["anchors"]), ["C1", "C2", "C3"])

    def test_prompt_contains_anchors_format_and_body(self):
        project = make_project()
        write(project, "specs/001-x/spec.md", SPEC)
        prompt = packets.build_prompt(packets.story_packet(project, "IRIS-41", git_repo_with_change(), "main"))
        self.assertIn("AC1: the case moves to curated", prompt)
        self.assertIn("VERDICT: APPROVED | CHANGES_REQUIRED", prompt)
        self.assertIn("+print('v2')", prompt)

    def test_diff_hash_is_stable(self):
        self.assertEqual(packets.diff_hash("a"), packets.diff_hash("a"))
        self.assertEqual(len(packets.diff_hash("a")), 16)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Correr y verificar que falla** — ERROR `No module named 'packets'`.

- [ ] **Step 3: Implementar `wow/packets.py`**

```python
"""Anchors and review content for each anchor set (spec 9.1)."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Callable, Dict

import manifest

READINESS: Dict[str, str] = {
    "R1": "every task has at least one verifiable acceptance criterion",
    "R2": "depends_on forms a DAG over existing task ids",
    "R3": "the Brief has no blocking open question",
    "R4": "every epic has done_when criteria",
    "R5": "every task has estimate, priority and labels",
}
_AC_RE = re.compile(r"\b(AC[0-9]+):\s*(.+?)\s*$")
_CLAIM_RE = re.compile(r"^\s*(?:[-*]\s*)?\**(C[0-9]+)\**\s*[:.)]\s*(.+?)\s*$")
_HEADER_RE = re.compile(r"^(#+)\s")


class PacketError(Exception):
    """The packet cannot be built (no anchors, no diff, git failure)."""


def diff_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def git_diff(repo: Path, base: str, runner: Callable = subprocess.run) -> str:
    proc = runner(["git", "-C", str(repo), "diff", base], capture_output=True, text=True)
    if proc.returncode != 0:
        raise PacketError(f"git diff {base} failed in {repo}: {proc.stderr.strip()[:200]}")
    if not proc.stdout.strip():
        raise PacketError(f"empty diff against {base} in {repo}")
    return proc.stdout


def _story_anchors(project: Path, key: str) -> Dict[str, str]:
    anchors: Dict[str, str] = {}
    for spec in sorted((project / "specs").glob("*/spec.md")):
        level = None
        for line in spec.read_text(encoding="utf-8").splitlines():
            header = _HEADER_RE.match(line)
            if header:
                if level is not None and len(header.group(1)) <= level:
                    level = None
                if key in line:
                    level = len(header.group(1))
                continue
            if level is not None:
                match = _AC_RE.search(line)
                if match:
                    anchors.setdefault(match.group(1), match.group(2))
    return anchors


def story_packet(project: Path, key: str, repo: Path, base: str, runner: Callable = subprocess.run) -> dict:
    anchors = _story_anchors(project, key)
    if not anchors:
        raise PacketError(f"no acceptance criteria with AC ids found for {key} in specs/*/spec.md")
    return {"anchor_set": "story", "ref": key, "anchors": anchors,
            "body": git_diff(repo, base, runner), "cwd": repo}


def epic_packet(project: Path, epic_id: str, repo: Path, base: str, runner: Callable = subprocess.run) -> dict:
    doc = manifest.load(project)
    epic = next((e for e in doc["epics"] if e["id"] == epic_id), None)
    if epic is None:
        raise PacketError(f"epic {epic_id} not found in the manifest")
    anchors = {item.split(":", 1)[0]: item.split(":", 1)[1].strip() for item in epic["done_when"]}
    if not anchors:
        raise PacketError(f"epic {epic_id} has no done_when criteria")
    return {"anchor_set": "epic", "ref": epic_id, "anchors": anchors,
            "body": git_diff(repo, base, runner), "cwd": repo}


def readiness_packet(project: Path) -> dict:
    doc = manifest.load(project)
    # plan.readiness is review state written by every round: excluding it keeps the diff hash stable.
    doc = dict(doc, plan={k: v for k, v in doc["plan"].items() if k != "readiness"})
    plan_md = project / "wow" / "plan" / "PLAN.md"
    body = (plan_md.read_text(encoding="utf-8") if plan_md.is_file() else "(no PLAN.md)") + \
        "\n\n--- manifest.json ---\n" + json.dumps(doc, indent=2, ensure_ascii=False)
    return {"anchor_set": "readiness", "ref": "plan", "anchors": dict(READINESS), "body": body, "cwd": project}


def claims_packet(doc: Path, repo: Path) -> dict:
    text = doc.read_text(encoding="utf-8")
    anchors: Dict[str, str] = {}
    for line in text.splitlines():
        match = _CLAIM_RE.match(line)
        if match:
            anchors.setdefault(match.group(1), match.group(2))
    if not anchors:
        raise PacketError(f"no claim ids (C1, C2, …) found in {doc}")
    return {"anchor_set": "claims", "ref": doc.stem, "anchors": anchors, "body": text, "cwd": repo}


_PROMPT = """You are an independent reviewer. Review the CONTENT below ONLY against these anchors:
{anchors}

{task}

Output format, exactly, with no other text:
VERDICT: APPROVED | CHANGES_REQUIRED
BLOCKER <anchor-id> <path:line> — <what fails and why it breaks the anchor>
WARNING <path:line> — <...>
NIT — <...>

A finding that breaks no listed anchor is a WARNING or a NIT, never a BLOCKER.
Do not modify any file.

--- CONTENT ({anchor_set} {ref}) ---
{body}
"""

_TASKS = {
    "story": "The content is the diff of one Work Unit. Check that it satisfies each acceptance criterion.",
    "epic": "The content is the cumulative diff of an epic. Check each done_when criterion.",
    "readiness": "The content is a plan (Brief + manifest). Check each readiness criterion.",
    "claims": "The content is a document of claims. Verify each claim against the code in the current "
              "directory; a false or unsupported claim is a BLOCKER on its id.",
}


def build_prompt(packet: dict) -> str:
    anchors = "\n".join(f"- {key}: {text}" for key, text in packet["anchors"].items())
    return _PROMPT.format(anchors=anchors, task=_TASKS[packet["anchor_set"]], anchor_set=packet["anchor_set"],
                          ref=packet["ref"], body=packet["body"])
```

- [ ] **Step 4: Correr y verificar que pasa** — todo OK.

- [ ] **Step 5: Commit**

```bash
python3 -m unittest discover -s tests && /usr/bin/python3 -m unittest discover -s tests
git add wow/packets.py tests/test_packets.py
git commit -m "feat(review): build anchored packets for readiness, story, epic and claims"
```

---

### Task 3: `reviewers.py` — invocación, dry-run y selección

**Files:**
- Create: `wow/reviewers.py`, `tests/test_reviewers.py`

**Interfaces:**
- Produces:
  - `reviewers.DEFAULT_COMMANDS`:
    - `codex`: `{"argv": ["codex", "exec", "-C", "{cwd}", "-s", "read-only", "--ephemeral", "-o", "{out}", "-"], "stdin": True, "output": "file"}`
    - `copilot`: `{"argv": ["copilot", "-s", "-p", "{prompt}"], "stdin": False, "output": "stdout"}`
  - `reviewers.EXCLUDED = {"claude", "cursor"}`
  - `reviewers.NoReviewer(Exception)`, `reviewers.ReviewerFailed(Exception)`
  - `reviewers.command_spec(cfg: dict, name: str) -> dict | None` (`cfg["reviewer_commands"][name]` pisa al default)
  - `reviewers.run_backend(spec: dict, prompt: str, cwd: Path, runner=subprocess.run, which=shutil.which, timeout: int = 1800) -> str`. Reemplaza `{cwd}`, `{out}` y `{prompt}` en cada argumento; ejecutable ausente → `FileNotFoundError`; exit distinto de 0 → `ReviewerFailed`.
  - `reviewers.dry_run_ok(spec, cwd, runner=..., which=...) -> bool` (salida sin espacios == `OK`; cualquier excepción → `False`)
  - `reviewers.pick_reviewer(cfg: dict, cwd: Path, runner=..., which=...) -> tuple[str, dict]` (primer nombre de `cfg["reviewers"]` no excluido cuyo dry-run da OK; ninguno → `NoReviewer` con los nombres probados)

- [ ] **Step 1: Escribir el test que falla**

`tests/test_reviewers.py`:

```python
from __future__ import annotations

import sys
import unittest

from helpers import make_project, write
import reviewers

FAKE = """import sys
data = sys.stdin.read()
out = sys.argv[1]
text = "OK" if "Reply with exactly OK" in data else "VERDICT: APPROVED"
open(out, "w").write(text)
"""


def fake_cfg(project, names=("codex",)):
    script = write(project, "fake_reviewer.py", FAKE)
    spec = {"argv": [sys.executable, str(script), "{out}"], "stdin": True, "output": "file"}
    return {"reviewers": list(names), "reviewer_commands": {"codex": spec}}


class BackendTest(unittest.TestCase):
    def test_run_backend_reads_output_file(self):
        project = make_project()
        spec = reviewers.command_spec(fake_cfg(project), "codex")
        self.assertEqual(reviewers.run_backend(spec, "review this", project).strip(), "VERDICT: APPROVED")

    def test_stdout_backend_with_prompt_placeholder(self):
        spec = {"argv": [sys.executable, "-c", "import sys; print(sys.argv[1].upper())", "{prompt}"],
                "stdin": False, "output": "stdout"}
        self.assertEqual(reviewers.run_backend(spec, "ok", make_project()).strip(), "OK")

    def test_missing_executable_and_failure(self):
        with self.assertRaises(FileNotFoundError):
            reviewers.run_backend({"argv": ["no-such-reviewer-cli"], "stdin": False, "output": "stdout"}, "x",
                                  make_project())
        failing = {"argv": [sys.executable, "-c", "import sys; sys.exit(3)"], "stdin": False, "output": "stdout"}
        with self.assertRaises(reviewers.ReviewerFailed):
            reviewers.run_backend(failing, "x", make_project())


class PickTest(unittest.TestCase):
    def test_picks_first_with_ok_dry_run(self):
        project = make_project()
        name, _ = reviewers.pick_reviewer(fake_cfg(project), project)
        self.assertEqual(name, "codex")

    def test_excluded_names_are_never_used(self):
        project = make_project()
        cfg = fake_cfg(project, names=("claude", "cursor"))
        cfg["reviewer_commands"]["claude"] = cfg["reviewer_commands"]["codex"]
        with self.assertRaises(reviewers.NoReviewer):
            reviewers.pick_reviewer(cfg, project)

    def test_no_reviewer_lists_tried_names(self):
        cfg = {"reviewers": ["codex"], "reviewer_commands": {
            "codex": {"argv": ["no-such-reviewer-cli"], "stdin": False, "output": "stdout"}}}
        with self.assertRaises(reviewers.NoReviewer) as ctx:
            reviewers.pick_reviewer(cfg, make_project())
        self.assertIn("codex", str(ctx.exception))

    def test_defaults_exist_for_codex_and_copilot(self):
        self.assertIn("{out}", reviewers.command_spec({}, "codex")["argv"])
        self.assertIn("{prompt}", reviewers.command_spec({}, "copilot")["argv"])
        self.assertIsNone(reviewers.command_spec({}, "unknown"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Correr y verificar que falla** — ERROR `No module named 'reviewers'`.

- [ ] **Step 3: Implementar `wow/reviewers.py`**

```python
"""Independent reviewer CLIs: command templates, dry run and selection (spec D7)."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Optional, Tuple

DEFAULT_COMMANDS = {
    "codex": {"argv": ["codex", "exec", "-C", "{cwd}", "-s", "read-only", "--ephemeral", "-o", "{out}", "-"],
              "stdin": True, "output": "file"},
    "copilot": {"argv": ["copilot", "-s", "-p", "{prompt}"], "stdin": False, "output": "stdout"},
}
EXCLUDED = {"claude", "cursor"}
_DRY_RUN_PROMPT = "Reply with exactly OK and nothing else."


class NoReviewer(Exception):
    """No configured reviewer passed the dry run."""


class ReviewerFailed(Exception):
    """The reviewer process exited with a non-zero code."""


def command_spec(cfg: dict, name: str) -> Optional[dict]:
    return (cfg.get("reviewer_commands") or {}).get(name) or DEFAULT_COMMANDS.get(name)


def run_backend(spec: dict, prompt: str, cwd: Path, runner: Callable = subprocess.run,
                which: Callable = shutil.which, timeout: int = 1800) -> str:
    if which(spec["argv"][0]) is None:
        raise FileNotFoundError(spec["argv"][0])
    fd, out = tempfile.mkstemp(prefix="wow-review-", suffix=".md")
    os.close(fd)
    try:
        argv = [a.replace("{cwd}", str(cwd)).replace("{out}", out).replace("{prompt}", prompt) for a in spec["argv"]]
        proc = runner(argv, input=prompt if spec.get("stdin") else None, capture_output=True, text=True,
                      timeout=timeout, cwd=str(cwd))
        if proc.returncode != 0:
            raise ReviewerFailed(f"{spec['argv'][0]} exited with {proc.returncode}")
        if spec.get("output") == "file":
            return Path(out).read_text(encoding="utf-8")
        return proc.stdout
    finally:
        Path(out).unlink(missing_ok=True)


def dry_run_ok(spec: dict, cwd: Path, runner: Callable = subprocess.run, which: Callable = shutil.which) -> bool:
    try:
        return run_backend(spec, _DRY_RUN_PROMPT, cwd, runner, which, timeout=300).strip() == "OK"
    except Exception:  # noqa: BLE001 — any failure means "not available"
        return False


def pick_reviewer(cfg: dict, cwd: Path, runner: Callable = subprocess.run,
                  which: Callable = shutil.which) -> Tuple[str, dict]:
    tried = []
    for name in cfg.get("reviewers", []):
        if name in EXCLUDED:
            continue
        spec = command_spec(cfg, name)
        if spec is None:
            continue
        tried.append(name)
        if dry_run_ok(spec, cwd, runner, which):
            return name, spec
    raise NoReviewer(f"no reviewer available (tried: {', '.join(tried) or 'none'})")
```

Nota: `Path.unlink(missing_ok=True)` existe desde Python 3.8, así que corre en 3.9.

- [ ] **Step 4: Correr y verificar que pasa** — todo OK.

- [ ] **Step 5: Commit**

```bash
python3 -m unittest discover -s tests && /usr/bin/python3 -m unittest discover -s tests
git add wow/reviewers.py tests/test_reviewers.py
git commit -m "feat(review): run reviewer CLIs with dry run and codex-first selection"
```

---

### Task 4: comando `wow review` y skill `wow-review`

**Files:**
- Create: `skills/wow-review/SKILL.md`
- Modify: `wow/cli.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `review.*` (Task 1), `packets.*` (Task 2), `reviewers.*` (Task 3), `manifest.load/save` (Plan 1).
- Produces: `wow review --set {readiness,story,epic,claims} --ref REF [--repo DIR] [--base REF] [--doc PATH] [--project DIR]`.
  1. Construye el packet (`--repo` por defecto = proyecto; `--base` por defecto `main`; `claims` requiere `--doc`). `PacketError`/`ManifestError` → exit 2.
  2. `next_action`: `done` → imprime `approved` y exit 0; `hitl` → imprime los BLOCKER de la última ronda y exit 1; `wait_for_changes` → imprime `round N has open BLOCKERs and the diff did not change` y exit 1.
  3. `pick_reviewer` → `NoReviewer` → exit 2. `run_backend` (en `packet["cwd"]`) → falla → exit 2.
  4. Guarda el crudo en `.wow/reviews/<ref>/round-<n>.md`. Sin `VERDICT:` → exit 2, sin registrar ronda.
  5. `record_round` + `save_summary`. Si el conjunto es `readiness`, escribe `plan.readiness = {"verdict": "approved"|"hitl"|"changes_required", "rounds": n}` en el manifiesto.
  6. Imprime `round N: APPROVED|CHANGES_REQUIRED (reviewer: <name>)` y una línea por BLOCKER válido; exit 0 si `final == "approved"`, si no 1.

- [ ] **Step 1: Escribir el test que falla**

Agregar a `tests/test_cli.py`:

```python
import sys as _sys  # noqa: E402

_FAKE_REVIEWER = """import sys, pathlib
data = sys.stdin.read()
out = sys.argv[1]
answer = pathlib.Path(sys.argv[2]).read_text()
open(out, "w").write("OK" if "Reply with exactly OK" in data else answer)
"""


def _review_project(answer: str):
    project = make_project()
    script = write(project, "fake_reviewer.py", _FAKE_REVIEWER)
    answer_file = write(project, "answer.txt", answer)
    spec = {"argv": [_sys.executable, str(script), "{out}", str(answer_file)], "stdin": True, "output": "file"}
    write(project, ".wow/config.json", _json.dumps({"reviewers": ["codex"], "reviewer_commands": {"codex": spec}}))
    _manifest.save(project, valid_doc())
    write(project, "wow/plan/PLAN.md", "## Brief\n- Goal: x\n")
    return project, answer_file


class ReviewCommandTest(unittest.TestCase):
    def test_readiness_approved_updates_manifest(self):
        project, _ = _review_project("VERDICT: APPROVED\n")
        code, out, _ = run_cli(["review", "--set", "readiness", "--ref", "plan", "--project", str(project)])
        self.assertEqual(code, 0)
        self.assertIn("round 1: APPROVED (reviewer: codex)", out)
        saved = _json.loads((project / "wow/plan/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["plan"]["readiness"], {"verdict": "approved", "rounds": 1})
        self.assertTrue((project / ".wow/reviews/plan/round-1.md").is_file())

    def test_blocker_then_same_diff_waits(self):
        project, _ = _review_project("VERDICT: CHANGES_REQUIRED\nBLOCKER R1 manifest.json:1 — task 1.1 has no AC\n")
        args = ["review", "--set", "readiness", "--ref", "plan", "--project", str(project)]
        code, out, _ = run_cli(args)
        self.assertEqual(code, 1)
        self.assertIn("BLOCKER R1", out)
        code, out, _ = run_cli(args)
        self.assertEqual(code, 1)
        self.assertIn("round 1 has open BLOCKERs and the diff did not change", out)

    def test_unparseable_output_exits_2_without_recording(self):
        project, _ = _review_project("I think it is fine")
        code, _, err = run_cli(["review", "--set", "readiness", "--ref", "plan", "--project", str(project)])
        self.assertEqual(code, 2)
        self.assertIn("VERDICT", err)
        self.assertFalse((project / "wow/reviews/plan.json").exists())

    def test_no_reviewer_exits_2(self):
        project, _ = _review_project("VERDICT: APPROVED\n")
        write(project, ".wow/config.json", _json.dumps({"reviewers": ["claude"]}))
        code, _, err = run_cli(["review", "--set", "readiness", "--ref", "plan", "--project", str(project)])
        self.assertEqual(code, 2)
        self.assertIn("no reviewer available", err)

    def test_claims_requires_doc(self):
        project, _ = _review_project("VERDICT: APPROVED\n")
        self.assertEqual(run_cli(["review", "--set", "claims", "--ref", "facts", "--project", str(project)])[0], 2)
```

- [ ] **Step 2: Correr y verificar que falla** — los 5 tests fallan con exit 2 por subcomando desconocido (`invalid choice: 'review'`).

- [ ] **Step 3: Implementar el subcomando en `wow/cli.py`**

Agregar imports al principio: `import packets`, `import review as review_mod`, `import reviewers`. Agregar:

```python
def _cmd_review(args) -> int:
    project = _project(args)
    try:
        cfg = config.load_config(project)
        repo = Path(args.repo).resolve() if args.repo else project
        if args.set == "readiness":
            packet = packets.readiness_packet(project)
        elif args.set == "story":
            packet = packets.story_packet(project, args.ref, repo, args.base)
        elif args.set == "epic":
            packet = packets.epic_packet(project, args.ref, repo, args.base)
        else:
            if not args.doc:
                sys.stderr.write("wow: --set claims requires --doc PATH\n")
                return exitcodes.CANNOT_EVALUATE
            packet = packets.claims_packet(Path(args.doc).resolve(), repo)
    except (config.ConfigError, packets.PacketError, manifest.ManifestError) as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE

    ref = args.ref
    summary = review_mod.load_summary(project, ref, args.set)
    dhash = packets.diff_hash(packet["body"])
    action = review_mod.next_action(summary, dhash)
    if action == "done":
        print(f"{ref}: approved")
        return exitcodes.OK
    if action in ("hitl", "wait_for_changes"):
        last = summary["rounds"][-1]
        if action == "hitl":
            print(f"{ref}: hitl after {last['n']} rounds — decide as a human:")
        else:
            print(f"round {last['n']} has open BLOCKERs and the diff did not change; fix them first:")
        for blocker in last["blockers"]:
            print(f"BLOCKER {blocker['anchor']} {blocker['path_line']} — {blocker['text']}")
        return exitcodes.FINDINGS

    try:
        name, spec = reviewers.pick_reviewer(cfg, packet["cwd"])
        text = reviewers.run_backend(spec, packets.build_prompt(packet), packet["cwd"])
    except reviewers.NoReviewer as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    except (reviewers.ReviewerFailed, FileNotFoundError, OSError) as exc:
        sys.stderr.write(f"wow: reviewer failed: {exc}\n")
        return exitcodes.CANNOT_EVALUATE

    number = len(summary["rounds"]) + 1
    raw = project / ".wow" / "reviews" / ref / f"round-{number}.md"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(text, encoding="utf-8")
    parsed = review_mod.parse_verdict(text)
    try:
        summary = review_mod.record_round(summary, parsed, packet["anchors"], dhash)
    except review_mod.ReviewOutputError as exc:
        sys.stderr.write(f"wow: {exc}; raw output kept in {raw.relative_to(project)}\n")
        return exitcodes.CANNOT_EVALUATE
    review_mod.save_summary(project, summary)

    if args.set == "readiness":
        doc = manifest.load(project)
        verdict = {"approved": "approved", "hitl": "hitl"}.get(summary["final"], "changes_required")
        doc["plan"]["readiness"] = {"verdict": verdict, "rounds": len(summary["rounds"])}
        manifest.save(project, doc)

    last = summary["rounds"][-1]
    print(f"round {last['n']}: {last['verdict']} (reviewer: {name})")
    for blocker in last["blockers"]:
        print(f"BLOCKER {blocker['anchor']} {blocker['path_line']} — {blocker['text']}")
    if summary["final"] == "hitl":
        print("escalated to HITL: decide as a human, no new round will open")
    return exitcodes.OK if summary["final"] == "approved" else exitcodes.FINDINGS
```

En `build_parser`, antes de `return parser`:

```python
    rv = with_project(sub.add_parser("review", help="run an anchored independent review"))
    rv.add_argument("--set", required=True, choices=["readiness", "story", "epic", "claims"])
    rv.add_argument("--ref", required=True, help="plan | Jira story key | epic id | claims doc name")
    rv.add_argument("--repo", default=None, help="repository to diff or to verify claims against")
    rv.add_argument("--base", default="main", help="git base for story/epic diffs (default: main)")
    rv.add_argument("--doc", default=None, help="claims document (required for --set claims)")
    rv.set_defaults(handler=_cmd_review)
```

- [ ] **Step 4: Escribir `skills/wow-review/SKILL.md`**

```markdown
---
name: wow-review
description: Run an independent, anchored review with a different model (Codex, else Copilot) for a plan's readiness, a Jira story's diff, an epic's cumulative diff, or a document of claims. Use when a phase needs an independent verdict, when the user says "review this story/epic/plan", or when wow-guide recommends `wow review`.
---

# wow-review

The host model never reviews its own work. This skill only runs the command and reports.

## Commands

- `wow review --set readiness --ref plan` — anchors R1–R5 over PLAN.md + manifest.
- `wow review --set story --ref <JIRA-KEY> --repo <child-repo>` — anchors: the story's AC ids in specs/*/spec.md.
- `wow review --set epic --ref <E1> --repo <child-repo>` — anchors: the epic's done_when.
- `wow review --set claims --ref <name> --doc <path> --repo <repo>` — anchors: C1, C2… claim ids.

Use `--base <ref>` when the diff base is not `main`.

## Reading the result

- Exit 0: approved. Report it and stop.
- Exit 1: changes required, waiting for a changed diff, or escalated to HITL. Quote each BLOCKER line
  verbatim. Fix only valid BLOCKERs; WARNING and NIT never reopen a review.
  In Spec-Kit projects, fixes go through `/spec-kit.refactor` so they stay on record.
- Exit 2: could not evaluate (no reviewer, no anchors, empty diff, unparseable output). Report the message.

## Rules

- Never rerun a review without changing the diff after a BLOCKER: wow refuses and so should you.
- After 3 rounds with a BLOCKER the review is HITL: present the BLOCKERs to the user and stop.
- Do not argue with the reviewer across rounds.
```

Agregar a `tests/test_cli.py` el contrato de la skill:

```python
class ReviewSkillContractTest(unittest.TestCase):
    def test_review_skill_frontmatter(self):
        text = (ROOT / "skills/wow-review/SKILL.md").read_text(encoding="utf-8")
        front = _re.match(r"^---\nname: (.+)\ndescription: (.+)\n---\n", text)
        self.assertEqual(front.group(1), "wow-review")
        self.assertLessEqual(len(text.splitlines()), 80)
```

- [ ] **Step 5: Correr y verificar que pasa** — todo OK.

- [ ] **Step 6: Commit**

```bash
python3 -m unittest discover -s tests && /usr/bin/python3 -m unittest discover -s tests
git add wow/cli.py tests/test_cli.py skills/wow-review/SKILL.md
git commit -m "feat(review): add wow review command and wow-review skill"
```

---

### Task 5: `usage.py` — colectores de Claude, Codex y Cursor

**Files:**
- Create: `wow/usage.py`, `tests/test_usage.py`

**Interfaces:**
- Produces:
  - `usage.RECORD_KEYS = ["ts", "vendor", "tool", "model", "tokens_in", "tokens_out", "cache_read", "cache_write", "reasoning_out", "duration_ms", "scope", "ref", "source"]`
  - `usage.claude_slug(path: Path) -> str` (todo carácter no alfanumérico → `-`; así nombra Claude Code la carpeta del proyecto, ej. `/Users/a.b/X` → `-Users-a-b-X`)
  - `usage.parse_ts(text: str) -> datetime` (acepta `Z` y fracciones de 1–9 dígitos, en 3.9)
  - `usage.claude_records(root: Path, project: Path) -> list[dict]`: lee `root/<slug>/*.jsonl`; una línea `type == "assistant"` con `message.usage` da un registro; **dedupe por `message.id`** (se queda con la última línea); `duration_ms` = desde la línea `type == "user"` anterior.
  - `usage.codex_records(root: Path, project: Path) -> list[dict]`: recorre `root/**/*.jsonl`; solo sesiones cuyo `session_meta.payload.cwd` está dentro de `project`; un registro por turno en `task_complete`, con tokens = diferencia de `info.total_token_usage` entre `task_started` y `task_complete` (inmune a `token_count` repetidos), `model` del último `turn_context`, `duration_ms` del evento.
  - `usage.cursor_records(project: Path) -> list[dict]`: `harness/runs/*.json` escritos por `wow run-wu` (Task 7).
  - `usage.collect(project: Path, cfg: dict, claude_root: Path | None = None, codex_root: Path | None = None) -> list[dict]` (raíces por defecto `~/.claude/projects` y `~/.codex/sessions`, o `cfg["usage"]["claude_root"|"codex_root"]`; ordenado por `ts`).
  - `usage.summarize(records: list[dict]) -> list[dict]` → por `(vendor, model)`: `{"vendor", "model", "count", "tokens_in", "tokens_out", "median_ms"}` (sumas ignoran `null`; `median_ms` `null` si no hay duraciones).

- [ ] **Step 1: Escribir el test que falla**

`tests/test_usage.py`:

```python
from __future__ import annotations

import json
import unittest

from helpers import make_project, write
import usage


def jl(*rows):
    return "\n".join(json.dumps(r) for r in rows) + "\n"


class ClaudeTest(unittest.TestCase):
    def test_dedupes_split_message_and_measures_response_time(self):
        project, root = make_project(), make_project()
        slug = usage.claude_slug(project)
        u = {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 7}
        write(root, f"{slug}/s1.jsonl", jl(
            {"type": "user", "timestamp": "2026-10-01T10:00:00.000Z", "message": {"role": "user"}},
            {"type": "assistant", "timestamp": "2026-10-01T10:00:02.500Z",
             "message": {"id": "m1", "model": "claude-opus-5-5", "usage": u}},
            {"type": "assistant", "timestamp": "2026-10-01T10:00:03.000Z",
             "message": {"id": "m1", "model": "claude-opus-5-5", "usage": u}},
        ))
        [rec] = usage.claude_records(root, project)
        self.assertEqual((rec["vendor"], rec["model"], rec["tokens_in"], rec["tokens_out"]),
                         ("anthropic", "claude-opus-5-5", 10, 5))
        self.assertEqual((rec["cache_read"], rec["cache_write"], rec["reasoning_out"]), (100, 7, None))
        self.assertEqual(rec["duration_ms"], 3000)
        self.assertEqual(sorted(rec), sorted(usage.RECORD_KEYS))

    def test_other_projects_are_ignored(self):
        root = make_project()
        write(root, "-Other-project/s.jsonl", jl({"type": "assistant", "timestamp": "2026-10-01T10:00:00Z",
                                                   "message": {"id": "x", "model": "m", "usage": {}}}))
        self.assertEqual(usage.claude_records(root, make_project()), [])

    def test_slug(self):
        from pathlib import Path
        self.assertEqual(usage.claude_slug(Path("/Users/josefigueredo/CurrentCode/SPECKIT")),
                         "-Users-josefigueredo-CurrentCode-SPECKIT")


class CodexTest(unittest.TestCase):
    def test_turn_delta_ignores_repeated_token_counts(self):
        project, root = make_project(), make_project()

        def tc(inp, out, reason):
            return {"type": "event_msg", "timestamp": "2026-10-01T10:00:01Z", "payload": {
                "type": "token_count", "info": {"total_token_usage": {
                    "input_tokens": inp, "cached_input_tokens": 0, "output_tokens": out,
                    "reasoning_output_tokens": reason, "total_tokens": inp + out}}}}

        write(root, "2026/10/01/rollout.jsonl", jl(
            {"type": "session_meta", "timestamp": "2026-10-01T10:00:00Z", "payload": {"cwd": str(project / "sub")}},
            {"type": "turn_context", "timestamp": "2026-10-01T10:00:00Z", "payload": {"model": "gpt-5.3-codex"}},
            tc(100, 10, 4),
            {"type": "event_msg", "timestamp": "2026-10-01T10:00:00Z", "payload": {"type": "task_started"}},
            tc(300, 30, 9),
            tc(300, 30, 9),
            {"type": "event_msg", "timestamp": "2026-10-01T10:00:05Z",
             "payload": {"type": "task_complete", "duration_ms": 4200}},
        ))
        [rec] = usage.codex_records(root, project)
        self.assertEqual((rec["vendor"], rec["tool"], rec["model"]), ("openai", "codex", "gpt-5.3-codex"))
        self.assertEqual((rec["tokens_in"], rec["tokens_out"], rec["reasoning_out"]), (200, 20, 5))
        self.assertEqual((rec["duration_ms"], rec["scope"]), (4200, "turn"))

    def test_sessions_outside_project_are_ignored(self):
        root = make_project()
        write(root, "s.jsonl", jl({"type": "session_meta", "timestamp": "2026-10-01T10:00:00Z",
                                   "payload": {"cwd": "/somewhere/else"}}))
        self.assertEqual(usage.codex_records(root, make_project()), [])


class CursorAndSummaryTest(unittest.TestCase):
    def test_cursor_runs_and_summary(self):
        project = make_project()
        write(project, "harness/runs/WU-001-1.json", json.dumps({
            "schema_version": 1, "work_unit": "WU-001", "ref": "E1/WU-001", "model": "composer-2.5",
            "started_at": "2026-10-01T10:00:00Z", "ended_at": "2026-10-01T10:01:00Z", "exit_code": 0,
            "result": {"duration_ms": 60000, "usage": {"inputTokens": 1000, "outputTokens": 50,
                                                       "cacheReadTokens": 800, "cacheWriteTokens": 0}}}))
        write(project, "harness/runs/WU-002-1.json", json.dumps({
            "schema_version": 1, "work_unit": "WU-002", "ref": "WU-002", "model": "composer-2.5",
            "started_at": "2026-10-01T11:00:00Z", "ended_at": "2026-10-01T11:00:10Z", "exit_code": 1, "result": None}))
        records = usage.cursor_records(project)
        self.assertEqual([r["ref"] for r in records], ["E1/WU-001", "WU-002"])
        self.assertEqual((records[0]["tokens_in"], records[0]["duration_ms"]), (1000, 60000))
        self.assertIsNone(records[1]["tokens_in"])
        [row] = usage.summarize(records)
        self.assertEqual(row, {"vendor": "cursor", "model": "composer-2.5", "count": 2,
                               "tokens_in": 1000, "tokens_out": 50, "median_ms": 60000})

    def test_parse_ts_variants(self):
        self.assertEqual(usage.parse_ts("2026-10-01T10:00:00.1234567Z").microsecond, 123456)
        self.assertEqual(usage.parse_ts("2026-10-01T10:00:00Z").second, 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Correr y verificar que falla** — ERROR `No module named 'usage'`.

- [ ] **Step 3: Implementar `wow/usage.py`**

```python
"""LLM usage collectors (spec 7.3). Records hold numbers and metadata only, never content."""
from __future__ import annotations

import json
import re
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

RECORD_KEYS = ["ts", "vendor", "tool", "model", "tokens_in", "tokens_out", "cache_read", "cache_write",
               "reasoning_out", "duration_ms", "scope", "ref", "source"]
_FRACTION_RE = re.compile(r"\.(\d+)")


def claude_slug(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def parse_ts(text: str) -> datetime:
    value = text.replace("Z", "+00:00")
    value = _FRACTION_RE.sub(lambda m: "." + (m.group(1) + "000000")[:6], value, count=1)
    return datetime.fromisoformat(value)


def _ms(start: Optional[str], end: str) -> Optional[int]:
    if not start:
        return None
    return int(round((parse_ts(end) - parse_ts(start)).total_seconds() * 1000))


def _record(**values) -> dict:
    record = {key: None for key in RECORD_KEYS}
    record.update(values)
    return record


def _lines(path: Path):
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            yield json.loads(raw)
        except json.JSONDecodeError:
            continue


def claude_records(root: Path, project: Path) -> List[dict]:
    folder = root / claude_slug(project)  # Claude Code names the folder after the path as typed, not resolved
    by_id: Dict[str, dict] = {}
    for path in sorted(folder.glob("*.jsonl")) if folder.is_dir() else []:
        last_user: Optional[str] = None
        for row in _lines(path):
            if row.get("type") == "user":
                last_user = row.get("timestamp") or last_user
                continue
            message = row.get("message") if isinstance(row.get("message"), dict) else {}
            if row.get("type") != "assistant" or not message.get("usage"):
                continue
            used = message["usage"]
            key = message.get("id") or f"{path.name}:{row.get('timestamp')}"
            by_id[key] = _record(
                ts=row.get("timestamp"), vendor="anthropic", tool="claude-code", model=message.get("model"),
                tokens_in=used.get("input_tokens"), tokens_out=used.get("output_tokens"),
                cache_read=used.get("cache_read_input_tokens"), cache_write=used.get("cache_creation_input_tokens"),
                duration_ms=_ms(last_user, row["timestamp"]) if row.get("timestamp") else None,
                scope="message", source="claude-transcript")
    return list(by_id.values())


def _inside(child: str, parent: Path) -> bool:
    try:
        Path(child).resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def codex_records(root: Path, project: Path) -> List[dict]:
    records: List[dict] = []
    for path in sorted(root.rglob("*.jsonl")) if root.is_dir() else []:
        rows = list(_lines(path))
        meta = next((r for r in rows if r.get("type") == "session_meta"), None)
        if not meta or not _inside((meta.get("payload") or {}).get("cwd", ""), project):
            continue
        model, total, start = None, {}, {}
        for row in rows:
            payload = row.get("payload") or {}
            kind = payload.get("type")
            if row.get("type") == "turn_context":
                model = payload.get("model") or model
            elif kind == "token_count" and payload.get("info"):
                total = payload["info"].get("total_token_usage") or total
            elif kind == "task_started":
                start = dict(total)
            elif kind == "task_complete":
                delta = {k: total.get(k, 0) - start.get(k, 0) for k in total}
                records.append(_record(
                    ts=row.get("timestamp"), vendor="openai", tool="codex", model=model,
                    tokens_in=delta.get("input_tokens"), tokens_out=delta.get("output_tokens"),
                    cache_read=delta.get("cached_input_tokens"), reasoning_out=delta.get("reasoning_output_tokens"),
                    duration_ms=payload.get("duration_ms"), scope="turn", source="codex-session"))
    return records


def cursor_records(project: Path) -> List[dict]:
    records: List[dict] = []
    for path in sorted((project / "harness" / "runs").glob("*.json")):
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        result = run.get("result") or {}
        used = result.get("usage") or {}
        records.append(_record(
            ts=run.get("ended_at"), vendor="cursor", tool="cursor-agent", model=run.get("model"),
            tokens_in=used.get("inputTokens"), tokens_out=used.get("outputTokens"),
            cache_read=used.get("cacheReadTokens"), cache_write=used.get("cacheWriteTokens"),
            duration_ms=result.get("duration_ms"), scope="task", ref=run.get("ref"), source="cursor-run"))
    return records


def collect(project: Path, cfg: dict, claude_root: Optional[Path] = None, codex_root: Optional[Path] = None) -> List[dict]:
    roots = cfg.get("usage") or {}
    claude_root = claude_root or Path(roots.get("claude_root", Path.home() / ".claude" / "projects")).expanduser()
    codex_root = codex_root or Path(roots.get("codex_root", Path.home() / ".codex" / "sessions")).expanduser()
    records = claude_records(claude_root, project) + codex_records(codex_root, project) + cursor_records(project)
    return sorted(records, key=lambda r: r["ts"] or "")


def summarize(records: List[dict]) -> List[dict]:
    groups: Dict[tuple, List[dict]] = {}
    for record in records:
        groups.setdefault((record["vendor"], record["model"]), []).append(record)
    rows = []
    for (vendor, model), items in sorted(groups.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
        durations = [r["duration_ms"] for r in items if r["duration_ms"] is not None]
        rows.append({"vendor": vendor, "model": model, "count": len(items),
                     "tokens_in": sum(r["tokens_in"] or 0 for r in items),
                     "tokens_out": sum(r["tokens_out"] or 0 for r in items),
                     "median_ms": int(statistics.median(durations)) if durations else None})
    return rows
```

- [ ] **Step 4: Correr y verificar que pasa** — todo OK.

- [ ] **Step 5: Commit**

```bash
python3 -m unittest discover -s tests && /usr/bin/python3 -m unittest discover -s tests
git add wow/usage.py tests/test_usage.py
git commit -m "feat(usage): collect Claude, Codex and Cursor usage as content-free records"
```

---

### Task 6: consumo en el snapshot y comando `wow usage`

**Files:**
- Modify: `wow/snapshot.py`, `schemas/progress.schema.json`, `wow/cli.py`, `tests/test_snapshot.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `usage.collect`, `usage.summarize`, `usage.RECORD_KEYS` (Task 5).
- Produces:
  - `snapshot.build(state: dict, previous: dict | None, now: str, usage: list[dict] | None = None) -> dict` — si se pasa `usage`, **reemplaza** el del snapshot anterior (se recalcula entero cada vez; así no hay duplicados); si es `None`, conserva el anterior.
  - `progress.schema.json`: cada ítem de `usage` requiere las 13 claves de `RECORD_KEYS`.
  - `wow snapshot` recalcula el consumo con `usage.collect`.
  - `wow usage [--project DIR]` imprime una línea por `(vendor, model)`: `vendor model count=N in=X out=Y median_ms=Z|-` y sale con `0`.

- [ ] **Step 1: Escribir el test que falla**

Agregar a `tests/test_snapshot.py`:

```python
class UsageInSnapshotTest(unittest.TestCase):
    def test_usage_param_replaces_previous(self):
        import usage as usage_mod
        record = {k: None for k in usage_mod.RECORD_KEYS}
        record.update({"ts": "t", "vendor": "cursor", "model": "composer-2.5", "scope": "task", "source": "cursor-run"})
        previous = {"history": [], "usage": [{"stale": True}]}
        snap = snapshot.build(fake_state(), previous, "2026-10-02T10:00:00Z", usage=[record])
        self.assertEqual(snap["usage"], [record])
        self.assertEqual(schema.validate(snap, schema.load_schema("progress")), [])

    def test_schema_rejects_incomplete_usage_record(self):
        snap = snapshot.build(fake_state(), None, "2026-10-02T10:00:00Z", usage=[{"vendor": "x"}])
        self.assertTrue(schema.validate(snap, schema.load_schema("progress")))
```

Agregar a `tests/test_cli.py`:

```python
class UsageCommandTest(unittest.TestCase):
    def test_usage_prints_cursor_rows_and_snapshot_includes_them(self):
        project = make_project()
        write(project, ".wow/config.json", _json.dumps({"usage": {"claude_root": str(project / "none-c"),
                                                                    "codex_root": str(project / "none-x")}}))
        write(project, "harness/runs/WU-001-1.json", _json.dumps({
            "schema_version": 1, "work_unit": "WU-001", "ref": "WU-001", "model": "composer-2.5",
            "started_at": "2026-10-01T10:00:00Z", "ended_at": "2026-10-01T10:01:00Z", "exit_code": 0,
            "result": {"duration_ms": 60000, "usage": {"inputTokens": 1000, "outputTokens": 50}}}))
        code, out, _ = run_cli(["usage", "--project", str(project)])
        self.assertEqual(code, 0)
        self.assertIn("cursor composer-2.5 count=1 in=1000 out=50 median_ms=60000", out)
        run_cli(["snapshot", "--project", str(project)])
        saved = _json.loads((project / "wow/progress.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["usage"][0]["model"], "composer-2.5")
```

- [ ] **Step 2: Correr y verificar que falla** — `TypeError: build() got an unexpected keyword argument 'usage'` y `invalid choice: 'usage'`.

- [ ] **Step 3: Implementar**

`wow/snapshot.py`, reemplazar `build`:

```python
def build(state: dict, previous: Optional[dict], now: str, usage: Optional[list] = None) -> dict:
    previous = previous or {}
    return {"schema_version": 1, "generated_at": now, "current": state,
            "history": list(previous.get("history", [])) + [history_point(state, now)],
            "usage": list(usage) if usage is not None else list(previous.get("usage", []))}
```

`schemas/progress.schema.json`, reemplazar la propiedad `usage`:

```json
    "usage": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["ts", "vendor", "tool", "model", "tokens_in", "tokens_out", "cache_read", "cache_write",
                     "reasoning_out", "duration_ms", "scope", "ref", "source"]
      }
    }
```

`wow/cli.py`: agregar `import usage as usage_mod`; en `_cmd_snapshot` reemplazar la línea `snap = …` por:

```python
    records = usage_mod.collect(project, cfg)
    snap = snapshot_mod.build(result, snapshot_mod.load_previous(project), _now(), usage=records)
```

Agregar el handler y registrarlo en `build_parser` antes de `return parser`:

```python
def _cmd_usage(args) -> int:
    project = _project(args)
    try:
        cfg = config.load_config(project)
    except config.ConfigError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    for row in usage_mod.summarize(usage_mod.collect(project, cfg)):
        median = row["median_ms"] if row["median_ms"] is not None else "-"
        print(f"{row['vendor']} {row['model']} count={row['count']} in={row['tokens_in']} "
              f"out={row['tokens_out']} median_ms={median}")
    return exitcodes.OK
```

```python
    with_project(sub.add_parser("usage", help="summarize LLM usage by vendor and model")).set_defaults(handler=_cmd_usage)
```

Además, para que el test existente `SnapshotCommandTest` no lea los transcripts reales del operador, agregarle al principio del test la misma config de raíces vacías:

```python
        write(project, ".wow/config.json", _json.dumps({"usage": {"claude_root": str(project / "none-c"),
                                                                    "codex_root": str(project / "none-x")}}))
```

- [ ] **Step 4: Correr y verificar que pasa** — todo OK.

- [ ] **Step 5: Commit**

```bash
python3 -m unittest discover -s tests && /usr/bin/python3 -m unittest discover -s tests
git add wow/snapshot.py wow/cli.py schemas/progress.schema.json tests/test_snapshot.py tests/test_cli.py
git commit -m "feat(usage): add usage to the snapshot and a wow usage summary"
```

---

### Task 7: `runwu.py` y comando `wow run-wu`

**Files:**
- Create: `wow/runwu.py`, `tests/test_runwu.py`
- Modify: `wow/cli.py`, `tests/test_cli.py`

**Interfaces:**
- Produces:
  - `runwu.KEEP_RESULT_KEYS = ("type", "subtype", "is_error", "duration_ms", "duration_api_ms", "usage")`
  - `runwu.build_command(wu: str, model: str, worktree: bool) -> list[str]` → `["cursor-agent", "-p", f"/spec-kit.implement {wu} --max-iterations 5", "--model", model, "--trust", "--force", "--output-format", "json"]` más `["--worktree", f"wu-{wu}"]` si `worktree`.
  - `runwu.run(project: Path, wu: str, model: str, epic: str | None = None, worktree: bool = False, runner=subprocess.run, which=shutil.which, now=<utc iso>) -> tuple[int, Path]`: `cursor-agent` ausente → `FileNotFoundError`; corre con `TMPDIR` nuevo; parsea stdout como JSON y **conserva solo** `KEEP_RESULT_KEYS` (nunca el texto de la respuesta); stdout no-JSON → `result: None`; escribe `harness/runs/<wu>-<YYYYmmddTHHMMSSZ>.json` con `{"schema_version": 1, "work_unit", "ref", "model", "started_at", "ended_at", "exit_code", "result"}` (`ref` = `"E1/WU-001"` si hay epic, si no `"WU-001"`); devuelve `(exit_code, path)`.
  - CLI: `wow run-wu WU [--model M] [--epic E1] [--worktree] [--dry-run] [--project DIR]`. Modelo por defecto `cfg["models"]["cursor_generate"]`. `--dry-run` imprime el comando (`shlex.join`) y sale con `0`. Sin `cursor-agent` → exit 2. Si no, imprime `run recorded: harness/runs/…` y sale `0` si cursor salió 0, si no `1`.

- [ ] **Step 1: Escribir el test que falla**

`tests/test_runwu.py`:

```python
from __future__ import annotations

import json
import subprocess
import unittest

from helpers import make_project
import runwu


def fake_runner(stdout, code=0, seen=None):
    def run(argv, cwd=None, env=None, capture_output=None, text=None):
        if seen is not None:
            seen.update({"argv": argv, "cwd": cwd, "tmpdir": env.get("TMPDIR")})
        return subprocess.CompletedProcess(argv, code, stdout, "stderr secret")
    return run


class RunTest(unittest.TestCase):
    def test_records_numbers_only_and_isolates_tmpdir(self):
        project, seen = make_project(), {}
        payload = json.dumps({"type": "result", "subtype": "success", "is_error": False, "duration_ms": 9123,
                              "result": "THE AGENT ANSWER TEXT", "session_id": "s1",
                              "usage": {"inputTokens": 11861, "outputTokens": 68}})
        code, path = runwu.run(project, "WU-001", "composer-2.5", epic="E1",
                               runner=fake_runner(payload, seen=seen), which=lambda n: "/bin/" + n,
                               now=lambda: "2026-10-02T10:00:00Z")
        self.assertEqual(code, 0)
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved["ref"], "E1/WU-001")
        self.assertEqual(saved["result"]["usage"]["inputTokens"], 11861)
        self.assertNotIn("result", saved["result"])
        self.assertNotIn("THE AGENT ANSWER TEXT", path.read_text(encoding="utf-8"))
        self.assertNotIn("stderr secret", path.read_text(encoding="utf-8"))
        self.assertTrue(seen["tmpdir"])
        self.assertEqual(seen["argv"][:3], ["cursor-agent", "-p", "/spec-kit.implement WU-001 --max-iterations 5"])

    def test_non_json_output_records_null_result(self):
        code, path = runwu.run(make_project(), "WU-002", "composer-2.5", runner=fake_runner("oops", code=1),
                               which=lambda n: "/bin/" + n, now=lambda: "2026-10-02T10:00:00Z")
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual((code, saved["result"], saved["ref"]), (1, None, "WU-002"))

    def test_missing_cursor_agent(self):
        with self.assertRaises(FileNotFoundError):
            runwu.run(make_project(), "WU-1", "m", which=lambda n: None)

    def test_worktree_flag(self):
        self.assertEqual(runwu.build_command("WU-3", "m", True)[-2:], ["--worktree", "wu-WU-3"])


if __name__ == "__main__":
    unittest.main()
```

Agregar a `tests/test_cli.py`:

```python
class RunWuCommandTest(unittest.TestCase):
    def test_dry_run_prints_command_with_default_model(self):
        code, out, _ = run_cli(["run-wu", "WU-008", "--dry-run", "--project", str(make_project())])
        self.assertEqual(code, 0)
        self.assertIn("cursor-agent -p '/spec-kit.implement WU-008 --max-iterations 5' --model composer-2.5", out)
```

- [ ] **Step 2: Correr y verificar que falla** — ERROR `No module named 'runwu'`.

- [ ] **Step 3: Implementar `wow/runwu.py` y el subcomando**

```python
"""Measured Cursor runs: wrap cursor-agent and keep only usage numbers (spec 9.4)."""
from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, List, Optional, Tuple

KEEP_RESULT_KEYS = ("type", "subtype", "is_error", "duration_ms", "duration_api_ms", "usage")


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_command(wu: str, model: str, worktree: bool) -> List[str]:
    cmd = ["cursor-agent", "-p", f"/spec-kit.implement {wu} --max-iterations 5", "--model", model,
           "--trust", "--force", "--output-format", "json"]
    if worktree:
        cmd += ["--worktree", f"wu-{wu}"]
    return cmd


def run(project: Path, wu: str, model: str, epic: Optional[str] = None, worktree: bool = False,
        runner: Callable = subprocess.run, which: Callable = shutil.which,
        now: Callable[[], str] = _utc_now) -> Tuple[int, Path]:
    if which("cursor-agent") is None:
        raise FileNotFoundError("cursor-agent")
    env = dict(os.environ, TMPDIR=tempfile.mkdtemp(prefix="wow-run-"))
    started = now()
    proc = runner(build_command(wu, model, worktree), cwd=str(project), env=env, capture_output=True, text=True)
    ended = now()
    try:
        data = json.loads(proc.stdout)
        result = {k: data[k] for k in KEEP_RESULT_KEYS if k in data} if isinstance(data, dict) else None
    except (json.JSONDecodeError, TypeError):
        result = None
    record = {"schema_version": 1, "work_unit": wu, "ref": f"{epic}/{wu}" if epic else wu, "model": model,
              "started_at": started, "ended_at": ended, "exit_code": proc.returncode, "result": result}
    stamp = ended.replace("-", "").replace(":", "")
    path = project / "harness" / "runs" / f"{wu}-{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return proc.returncode, path
```

En `wow/cli.py`: `import shlex` y `import runwu`, más:

```python
def _cmd_run_wu(args) -> int:
    project = _project(args)
    try:
        cfg = config.load_config(project)
    except config.ConfigError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    model = args.model or cfg["models"]["cursor_generate"]
    if args.dry_run:
        print(shlex.join(runwu.build_command(args.wu, model, args.worktree)))
        return exitcodes.OK
    try:
        code, path = runwu.run(project, args.wu, model, epic=args.epic, worktree=args.worktree)
    except FileNotFoundError:
        sys.stderr.write("wow: cursor-agent not found on PATH\n")
        return exitcodes.CANNOT_EVALUATE
    print(f"run recorded: {path.relative_to(project)}")
    return exitcodes.OK if code == 0 else exitcodes.FINDINGS
```

```python
    rw = with_project(sub.add_parser("run-wu", help="run /spec-kit.implement headless and record usage"))
    rw.add_argument("wu")
    rw.add_argument("--model", default=None)
    rw.add_argument("--epic", default=None)
    rw.add_argument("--worktree", action="store_true")
    rw.add_argument("--dry-run", action="store_true")
    rw.set_defaults(handler=_cmd_run_wu)
```

- [ ] **Step 4: Correr y verificar que pasa** — todo OK.

- [ ] **Step 5: Commit**

```bash
python3 -m unittest discover -s tests && /usr/bin/python3 -m unittest discover -s tests
git add wow/runwu.py wow/cli.py tests/test_runwu.py tests/test_cli.py
git commit -m "feat(run-wu): run work units headless and record content-free usage"
```

---

### Task 8: `sk.py`, comando `wow sk` y skill `wow-sk-prep`

**Files:**
- Create: `wow/sk.py`, `tests/test_sk.py`, `skills/wow-sk-prep/SKILL.md`
- Modify: `wow/cli.py`, `tests/test_cli.py`, `README.md`

**Interfaces:**
- Consumes: `speckit.features` (Plan 1).
- Produces:
  - `sk.STEPS = ("sync", "clarify", "plan", "tasks")`
  - `sk.commands_for(step: str, cfg: dict, epic: str | None = None, feature: str | None = None) -> list[str]` (cada elemento es una línea de shell lista para copiar):
    - `sync` (requiere `epic`): `/spec-kit.sync --epic-key <EPIC>` con `cursor_generate`.
    - `clarify` (requiere `feature`): `/spec-kit.clarify Use the answers in wow/sk/<name>/clarify-answers.md` con `cursor_reason`.
    - `plan`: `/spec-kit.plan Use wow/sk/<name>/plan-draft.md as the design input` con `cursor_reason`.
    - `tasks`: dos líneas, `/spec-kit.tasks` y `/spec-kit.tasks.shape`, con `cursor_reason`.
    - Formato: `shlex.join(["cursor-agent", "-p", slash, "--model", model, "--trust", "--output-format", "json"])`. Paso desconocido o falta de `epic`/`feature` → `ValueError`.
  - `sk.orphan_tasks(text: str) -> int` (tareas sin `- jira:` dentro de secciones `##` que tienen al menos una key; mismo criterio que `push_status.py`).
  - `sk.status(project: Path, feature: str | None = None) -> dict` → `{"import_warnings": int, "features": [{"dir", "epic_key", "missing": [...], "orphan_tasks": int}]}`. `import_warnings` cuenta líneas con `⚠` o `warning` en `.spec-kit/import_report.md`. `missing` lista los faltantes entre `plan.md`, `tasks.md`, `work-units.json`, `wow/sk/<name>/clarify-answers.md` y `wow/sk/<name>/plan-draft.md`.
  - CLI: `wow sk cmd STEP [--epic KEY] [--feature DIR]` imprime las líneas y sale con `0` (`ValueError` → `2`); `wow sk status [--feature DIR]` imprime el JSON y sale con `1` si hay warnings o huérfanas, si no `0`.

- [ ] **Step 1: Escribir el test que falla**

`tests/test_sk.py`:

```python
from __future__ import annotations

import unittest

from helpers import make_project, write
import config
import sk

TASKS = ("## Phase 1: Setup\n- [x] T001 scaffold\n"
         "## Phase 3: Story 1\n- [ ] T010 model\n  - jira: IRIS-41\n- [ ] T011 orphan without key\n")


class CommandsTest(unittest.TestCase):
    def test_sync_uses_generate_model(self):
        [line] = sk.commands_for("sync", config.DEFAULTS, epic="IRIS-40")
        self.assertEqual(line, "cursor-agent -p '/spec-kit.sync --epic-key IRIS-40' --model composer-2.5 "
                               "--trust --output-format json")

    def test_plan_points_to_draft_and_uses_reason_model(self):
        [line] = sk.commands_for("plan", config.DEFAULTS, feature="specs/001-curation")
        self.assertIn("wow/sk/001-curation/plan-draft.md", line)
        self.assertIn("--model claude-sonnet-5-5-high", line)

    def test_tasks_returns_two_lines(self):
        lines = sk.commands_for("tasks", config.DEFAULTS, feature="specs/001-curation")
        self.assertEqual(len(lines), 2)
        self.assertIn("/spec-kit.tasks.shape", lines[1])

    def test_missing_argument_and_unknown_step(self):
        with self.assertRaises(ValueError):
            sk.commands_for("sync", config.DEFAULTS)
        with self.assertRaises(ValueError):
            sk.commands_for("deploy", config.DEFAULTS, feature="x")


class StatusTest(unittest.TestCase):
    def test_orphans_only_in_sections_with_keys(self):
        self.assertEqual(sk.orphan_tasks(TASKS), 1)

    def test_status_counts_warnings_missing_and_orphans(self):
        project = make_project()
        write(project, ".spec-kit/import_report.md", "ok\n⚠ IRIS-43 has no acceptance criteria\nWarning: x\n")
        write(project, "specs/001-curation/spec.md", "**Jira Epic:** IRIS-40\n")
        write(project, "specs/001-curation/tasks.md", TASKS)
        write(project, "wow/sk/001-curation/plan-draft.md", "draft")
        result = sk.status(project)
        self.assertEqual(result["import_warnings"], 2)
        [feature] = result["features"]
        self.assertEqual(feature["orphan_tasks"], 1)
        self.assertEqual(feature["missing"], ["plan.md", "work-units.json", "wow/sk/001-curation/clarify-answers.md"])


if __name__ == "__main__":
    unittest.main()
```

Agregar a `tests/test_cli.py`:

```python
class SkCommandTest(unittest.TestCase):
    def test_sk_cmd_and_status_codes(self):
        project = make_project()
        code, out, _ = run_cli(["sk", "cmd", "sync", "--epic", "IRIS-40", "--project", str(project)])
        self.assertEqual(code, 0)
        self.assertIn("/spec-kit.sync --epic-key IRIS-40", out)
        self.assertEqual(run_cli(["sk", "cmd", "sync", "--project", str(project)])[0], 2)
        self.assertEqual(run_cli(["sk", "status", "--project", str(project)])[0], 0)
        write(project, ".spec-kit/import_report.md", "⚠ missing AC\n")
        self.assertEqual(run_cli(["sk", "status", "--project", str(project)])[0], 1)

    def test_sk_prep_skill_frontmatter(self):
        text = (ROOT / "skills/wow-sk-prep/SKILL.md").read_text(encoding="utf-8")
        front = _re.match(r"^---\nname: (.+)\ndescription: (.+)\n---\n", text)
        self.assertEqual(front.group(1), "wow-sk-prep")
        self.assertLessEqual(len(text.splitlines()), 80)
```

- [ ] **Step 2: Correr y verificar que falla** — ERROR `No module named 'sk'`.

- [ ] **Step 3: Implementar `wow/sk.py` y el subcomando**

```python
"""Spec-Kit preparation: exact cursor-agent commands and artifact status (spec 9.4)."""
from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import List, Optional

from sources import speckit

STEPS = ("sync", "clarify", "plan", "tasks")
_SECTION_RE = re.compile(r"^##\s")
_TASK_RE = re.compile(r"^\s*-\s*\[[ xX]\]")
_JIRA_RE = re.compile(r"^\s*-\s*jira:\s*[A-Z][A-Z0-9]*-\d+\s*$", re.IGNORECASE)


def _line(slash: str, model: str) -> str:
    return shlex.join(["cursor-agent", "-p", slash, "--model", model, "--trust", "--output-format", "json"])


def commands_for(step: str, cfg: dict, epic: Optional[str] = None, feature: Optional[str] = None) -> List[str]:
    models = cfg["models"]
    if step not in STEPS:
        raise ValueError(f"unknown step {step!r}; expected one of {', '.join(STEPS)}")
    if step == "sync":
        if not epic:
            raise ValueError("step 'sync' needs --epic KEY")
        return [_line(f"/spec-kit.sync --epic-key {epic}", models["cursor_generate"])]
    if not feature:
        raise ValueError(f"step '{step}' needs --feature DIR")
    name = Path(feature).name
    reason = models["cursor_reason"]
    if step == "clarify":
        return [_line(f"/spec-kit.clarify Use the answers in wow/sk/{name}/clarify-answers.md", reason)]
    if step == "plan":
        return [_line(f"/spec-kit.plan Use wow/sk/{name}/plan-draft.md as the design input", reason)]
    return [_line("/spec-kit.tasks", reason), _line("/spec-kit.tasks.shape", reason)]


def orphan_tasks(text: str) -> int:
    sections: List[dict] = [{"keys": 0, "orphans": 0}]
    pending = False
    for raw in text.splitlines():
        if _SECTION_RE.match(raw):
            if pending:
                sections[-1]["orphans"] += 1
            sections.append({"keys": 0, "orphans": 0})
            pending = False
        elif _TASK_RE.match(raw):
            if pending:
                sections[-1]["orphans"] += 1
            pending = True
        elif _JIRA_RE.match(raw) and pending:
            sections[-1]["keys"] += 1
            pending = False
    if pending:
        sections[-1]["orphans"] += 1
    return sum(s["orphans"] for s in sections if s["keys"])


def status(project: Path, feature: Optional[str] = None) -> dict:
    report = project / ".spec-kit" / "import_report.md"
    warnings = 0
    if report.is_file():
        warnings = sum(1 for line in report.read_text(encoding="utf-8").splitlines()
                       if "⚠" in line or "warning" in line.lower())
    out = []
    for item in speckit.features(project):
        if feature and item["dir"] != feature.rstrip("/"):
            continue
        folder, name = project / item["dir"], Path(item["dir"]).name
        missing = [f for f in ("plan.md", "tasks.md") if not (folder / f).is_file()]
        if not item["has_work_units"]:
            missing.append("work-units.json")
        for draft in ("clarify-answers.md", "plan-draft.md"):
            if not (project / "wow" / "sk" / name / draft).is_file():
                missing.append(f"wow/sk/{name}/{draft}")
        tasks = folder / "tasks.md"
        orphans = orphan_tasks(tasks.read_text(encoding="utf-8")) if tasks.is_file() else 0
        out.append({"dir": item["dir"], "epic_key": item["epic_key"], "missing": missing, "orphan_tasks": orphans})
    return {"import_warnings": warnings, "features": out}
```

En `wow/cli.py`: `import sk`, más:

```python
def _cmd_sk_cmd(args) -> int:
    project = _project(args)
    try:
        lines = sk.commands_for(args.step, config.load_config(project), epic=args.epic, feature=args.feature)
    except (ValueError, config.ConfigError) as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    for line in lines:
        print(line)
    return exitcodes.OK


def _cmd_sk_status(args) -> int:
    result = sk.status(_project(args), args.feature)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    dirty = result["import_warnings"] or any(f["orphan_tasks"] for f in result["features"])
    return exitcodes.FINDINGS if dirty else exitcodes.OK
```

```python
    skp = sub.add_parser("sk", help="prepare Spec-Kit steps")
    sksub = skp.add_subparsers(dest="sk_command", parser_class=_Parser)
    skc = with_project(sksub.add_parser("cmd"))
    skc.add_argument("step", choices=list(sk.STEPS))
    skc.add_argument("--epic", default=None)
    skc.add_argument("--feature", default=None)
    skc.set_defaults(handler=_cmd_sk_cmd)
    sks = with_project(sksub.add_parser("status"))
    sks.add_argument("--feature", default=None)
    sks.set_defaults(handler=_cmd_sk_status)
```

Nota: `choices=list(sk.STEPS)` hace que un paso desconocido salga con `2` desde argparse; el `ValueError` cubre la falta de `--epic`/`--feature`.

- [ ] **Step 4: Escribir `skills/wow-sk-prep/SKILL.md`**

```markdown
---
name: wow-sk-prep
description: Prepare each Spec-Kit step so Cursor only ratifies: pre-chew clarify answers and a plan draft with the host model, print the exact cursor-agent command with the right model, and run work units with usage recorded. Use before /spec-kit.sync, clarify, plan, tasks or implement, or when wow-guide recommends `wow sk cmd` or `wow run-wu`.
---

# wow-sk-prep

Goal: spend the scarce Cursor pool only on ratifying and generating, never on thinking.

## Steps

1. Run `wow sk status` (add `--feature specs/<dir>` to focus). Exit 1 means import warnings or tasks
   without `jira:` keys: report them; warnings are Product Brain debt, fix them there, not in the spec.
2. Before clarify or plan, write the inputs yourself with the strongest host model:
   - `wow/sk/<feature-name>/clarify-answers.md`: answers to the ambiguities, citing the RFC and the
     manifest; mark unknowns as [SIN DEFINIR].
   - `wow/sk/<feature-name>/plan-draft.md`: the design decisions, alternatives and contracts.
3. Print the exact command with `wow sk cmd <sync|clarify|plan|tasks> --epic <KEY> | --feature specs/<dir>`
   and hand it to the user. Do not run Spec-Kit commands yourself unless asked.
4. For implementation, use `wow run-wu <WU-ID>` (add `--epic E1`, `--model ...` to escalate,
   `--dry-run` to preview). It records tokens and duration in `harness/runs/`.

## Rules

- Never replace a `/spec-kit.*` command with your own implementation: telemetry must see it.
- Escalate a work unit to `--model claude-sonnet-5-5-medium` after its third NEEDS_REVISION, not before.
- `wow run-wu` exit 2 means cursor-agent is not installed; exit 1 means the run failed: read its report.
```

- [ ] **Step 5: Actualizar `README.md`**

Agregar al bloque de uso, después de `wow plan freeze …`:

```bash
wow review --set story --ref IRIS-41 --repo ../backend-api   # review independiente anclado (Codex)
wow usage                                                   # consumo por marca y modelo
wow sk status | wow sk cmd plan --feature specs/001-x       # preparar pasos de Spec-Kit
wow run-wu WU-008 --epic E1                                 # implementar una WU midiendo el consumo
```

- [ ] **Step 6: Correr y verificar que pasa** — todo OK.

- [ ] **Step 7: Commit**

```bash
python3 -m unittest discover -s tests && /usr/bin/python3 -m unittest discover -s tests
git add wow/sk.py wow/cli.py tests/test_sk.py tests/test_cli.py skills/wow-sk-prep/SKILL.md README.md
git commit -m "feat(sk): add wow sk status/cmd and the wow-sk-prep skill"
```

---

## Fuera de este plan

- **Plan 3:** `wow pack` + `wow-pack`, `wow pbchat parse/audit` + `wow-pb-audit`, `wow context scan/check` + `wow-context`, skill `wow-plan`, fuente GitHub y links en el snapshot.
- **Plan 4:** `dashboard/wow-dashboard.html`.
