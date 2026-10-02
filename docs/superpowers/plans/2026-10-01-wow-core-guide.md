# WayOfWork · Plan 1: núcleo + guía — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un CLI `wow` (Python stdlib) que lee el repo, Spec-Kit, las copias de chats de Product Brain y Jira, deduce la fase del plan y de cada épica, y escribe `wow/progress.json`; más la skill `wow-guide` que lo explica.

**Architecture:** Módulos planos dentro de `wow/` (sin paquete instalable): un entrypoint `wow/wow` agrega su carpeta al `sys.path` e invoca `cli.main`. Las fuentes viven en `wow/sources/` y nunca escriben afuera. `state.py` combina fuentes en un dict determinista; `snapshot.py` lo persiste con historia. Validación de JSON con un validador mínimo propio (`schema.py`), porque no se pueden usar dependencias.

**Tech Stack:** Python 3.9+ solo biblioteca estándar (`json`, `re`, `pathlib`, `urllib`, `argparse`, `unittest`, `hashlib`, `base64`).

**Spec:** `docs/superpowers/specs/2026-10-01-wayofwork-design.md` (secciones 4, 5, 6, 7.1, 10, 11, 12). Este plan cubre los pasos 1 y 2 del orden de construcción y la skill `wow-guide`. Fuera de este plan: `wow usage`, `review`, `pack`, `pbchat audit`, `context`, `sk`, `run-wu`, fuente GitHub (Plan 2) y el dashboard (Plan 3).

## Global Constraints

- Python: compatible con **3.9** (`/usr/bin/python3` = 3.9.6) y con el `python3` de Homebrew (3.14). `from __future__ import annotations` en todo módulo; sin `match`, sin uniones `X | Y` en runtime.
- Solo biblioteca estándar. **Prohibido** importar PyYAML, requests, pytest u otra dependencia en código de producción. Tests con `unittest`.
- Idioma: código, comentarios, nombres, schemas, mensajes del CLI y `SKILL.md` en **inglés**. README y documentación humana en **castellano**.
- Exit codes (D8): `0` OK · `1` hallazgos · `2` no pude evaluar. Un `2` nunca se reporta como verde.
- `wow` **nunca escribe** en Jira, Confluence ni en artefactos de Spec-Kit. En este plan solo escribe `wow/plan/manifest.json` (comandos `plan`) y `wow/progress.json` (`snapshot`).
- Credenciales: variables `IC_JIRA_*` (shell → `.env.local` → `JIRA_*` de `.spec-kit/.env`). Ningún mensaje, log, `repr` ni excepción puede contener el token.
- Métricas sin dato: `null` / `"unknown"` con motivo, nunca `0` (D12).
- **No commitear.** El operador commitea cuando lo pide. Cada tarea cierra con un *checkpoint* (suite completa en verde) en lugar de `git commit`.
- Suite completa: `python3 -m unittest discover -s tests -v` y `/usr/bin/python3 -m unittest discover -s tests -v`, desde la raíz de `WayOfWork/`.

## Review Focus

1. **Manifiesto con JSON inválido** → `wow manifest validate` sale con `2` y un mensaje de línea/columna, nunca un traceback. **Con BOM** → se acepta (lo agregan editores en Windows). Tests en Task 4.
2. **Jira devuelve 401/403/timeout** → la fuente queda `unavailable` con motivo, las épicas que dependen de Jira quedan `"unknown"` y `wow snapshot` igual escribe el archivo y sale con `0`. Tests en Task 8 y Task 9.
3. **Proyecto recién creado, sin carpeta `wow/`** → `wow state` devuelve fase 0 con el paso "build the context pack", sin excepción. Test en Task 9.
4. **`tasks.md` con fin de línea CRLF y `- jira:` indentado con tabs** → se cuentan bien tareas, hechas y keys. Test en Task 7.
5. **El token de Jira nunca aparece** en `repr(creds)`, en mensajes de error HTTP ni en la salida de `wow state`. Tests en Task 3 y Task 8.

---

## File Structure

```
WayOfWork/
├── .gitignore                    (existe: .env.local, .wow/reviews/) — Task 1 agrega __pycache__/
├── install.sh                    Task 11
├── README.md                     Task 11 (castellano)
├── schemas/
│   ├── manifest.schema.json      Task 4
│   └── progress.schema.json      Task 10
├── skills/wow-guide/SKILL.md     Task 11
├── wow/
│   ├── wow                       entrypoint ejecutable — Task 1
│   ├── cli.py                    argparse y dispatch — Task 1, ampliado en 4, 9, 10
│   ├── exitcodes.py              OK / FINDINGS / CANNOT_EVALUATE — Task 1
│   ├── config.py                 config + credenciales — Task 3
│   ├── schema.py                 validador mínimo — Task 2
│   ├── manifest.py               load/validate/lint/init/freeze — Task 4
│   ├── state.py                  fases + próximos pasos — Task 9
│   ├── snapshot.py               progress.json con historia — Task 10
│   └── sources/
│       ├── __init__.py           SourceUnavailable — Task 5
│       ├── repo.py               context pack + paquetes PB — Task 5
│       ├── pbchat.py             copias de chats de PB — Task 6
│       ├── speckit.py          specs/, tasks.md, work-units.json — Task 7
│       └── jira.py               cliente REST de solo lectura — Task 8
└── tests/
    ├── helpers.py                sys.path + armado de proyectos temporales — Task 1
    ├── test_cli.py               Task 1, 4, 9, 10
    ├── test_schema.py            Task 2
    ├── test_config.py            Task 3
    ├── test_manifest.py          Task 4
    ├── test_repo.py              Task 5
    ├── test_pbchat.py            Task 6
    ├── test_speckit.py         Task 7
    ├── test_jira.py              Task 8
    ├── test_state.py             Task 9
    └── test_snapshot.py          Task 10
```

---

### Task 1: Esqueleto del CLI, exit codes y helpers de test

**Files:**
- Create: `wow/wow`, `wow/cli.py`, `wow/exitcodes.py`, `tests/helpers.py`, `tests/test_cli.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `exitcodes.OK = 0`, `exitcodes.FINDINGS = 1`, `exitcodes.CANNOT_EVALUATE = 2`; `cli.main(argv: list[str]) -> int`; `cli.VERSION = "0.1.0"`; `tests/helpers.py`: `WOW_DIR`, `ROOT`, `make_project() -> Path` (crea un directorio temporal vacío y lo devuelve), `write(project: Path, rel: str, text: str) -> Path`, `run_cli(args: list[str]) -> tuple[int, str, str]`.

- [ ] **Step 1: Agregar `__pycache__/` al `.gitignore`**

```
.env.local
.wow/reviews/
__pycache__/
```

- [ ] **Step 2: Escribir `tests/helpers.py`**

```python
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
```

- [ ] **Step 3: Escribir el test que falla**

`tests/test_cli.py`:

```python
from __future__ import annotations

import subprocess
import sys
import unittest

from helpers import ROOT, run_cli


class VersionTest(unittest.TestCase):
    def test_version_flag_prints_version_and_exits_ok(self):
        code, out, _ = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "wow 0.1.0")

    def test_unknown_subcommand_exits_cannot_evaluate(self):
        code, _, err = run_cli(["nope"])
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_entrypoint_script_runs(self):
        proc = subprocess.run([sys.executable, str(ROOT / "wow" / "wow"), "--version"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "wow 0.1.0")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Correr el test y verificar que falla**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL / ERROR con `ModuleNotFoundError: No module named 'cli'`.

- [ ] **Step 5: Implementar `wow/exitcodes.py`, `wow/cli.py` y `wow/wow`**

`wow/exitcodes.py`:

```python
"""Exit codes shared by every wow command (spec D8)."""
OK = 0
FINDINGS = 1
CANNOT_EVALUATE = 2
```

`wow/cli.py`:

```python
"""wow command line entrypoint."""
from __future__ import annotations

import argparse
import sys
from typing import List

import exitcodes

VERSION = "0.1.0"


class _Parser(argparse.ArgumentParser):
    """ArgumentParser that returns CANNOT_EVALUATE instead of calling sys.exit(2) on bad usage."""

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        sys.stderr.write(f"wow: error: {message}\n")
        raise _UsageError()


class _UsageError(Exception):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="wow", description="WayOfWork CLI")
    parser.add_argument("--version", action="store_true", help="print the version and exit")
    parser.add_subparsers(dest="command", parser_class=_Parser)
    return parser


def main(argv: List[str]) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except _UsageError:
        return exitcodes.CANNOT_EVALUATE
    if args.version:
        print(f"wow {VERSION}")
        return exitcodes.OK
    if not args.command:
        parser.print_usage(sys.stderr)
        return exitcodes.CANNOT_EVALUATE
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_usage(sys.stderr)
        return exitcodes.CANNOT_EVALUATE
    return handler(args)
```

`wow/wow` (y después `chmod +x wow/wow`):

```python
#!/usr/bin/env python3
"""Executable entrypoint: puts the wow module folder on sys.path and runs the CLI."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cli import main  # noqa: E402

sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 6: Correr los tests y verificar que pasan**

Run: `chmod +x wow/wow && python3 -m unittest discover -s tests -v`
Expected: 3 tests OK.

- [ ] **Step 7: Checkpoint (sin commit)**

Run: `/usr/bin/python3 -m unittest discover -s tests -v`
Expected: 3 tests OK también con 3.9.6. No commitear.

---

### Task 2: Validador mínimo de JSON Schema

**Files:**
- Create: `wow/schema.py`, `tests/test_schema.py`

**Interfaces:**
- Produces: `schema.validate(instance: Any, schema: dict, path: str = "$") -> list[str]` (lista vacía = válido); `schema.load_schema(name: str) -> dict` (lee `schemas/<name>.schema.json`); `schema.SCHEMA_DIR: Path`.
- Soporta: `type` (string o lista: `object`, `array`, `string`, `integer`, `number`, `boolean`, `null`), `enum`, `pattern`, `minimum`, `maximum`, `required`, `properties`, `additionalProperties` (`false` o un schema), `items`, `minItems`. `True`/`False` **no** cuentan como `integer`.

- [ ] **Step 1: Escribir el test que falla**

`tests/test_schema.py`:

```python
from __future__ import annotations

import unittest

import helpers  # noqa: F401  (sets sys.path)
import schema

PERSON = {
    "type": "object",
    "required": ["name", "age"],
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string", "pattern": "^[A-Z]"},
        "age": {"type": "integer", "minimum": 0, "maximum": 150},
        "tags": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        "role": {"type": ["string", "null"], "enum": [None, "dev", "lead"]},
        "extra": {"type": "object", "additionalProperties": {"type": "integer"}},
    },
}


class ValidateTest(unittest.TestCase):
    def test_valid_instance_has_no_errors(self):
        self.assertEqual(schema.validate({"name": "Ana", "age": 30, "tags": ["x"], "role": None}, PERSON), [])

    def test_missing_required_key(self):
        self.assertEqual(schema.validate({"name": "Ana"}, PERSON), ["$: missing required key 'age'"])

    def test_wrong_type_reports_path(self):
        self.assertEqual(schema.validate({"name": "Ana", "age": "30"}, PERSON), ["$.age: expected integer"])

    def test_boolean_is_not_integer(self):
        self.assertEqual(schema.validate({"name": "Ana", "age": True}, PERSON), ["$.age: expected integer"])

    def test_enum_pattern_minimum_maximum(self):
        errors = schema.validate({"name": "ana", "age": 200, "role": "boss"}, PERSON)
        self.assertIn("$.name: 'ana' does not match ^[A-Z]", errors)
        self.assertIn("$.age: 200 is greater than maximum 150", errors)
        self.assertIn("$.role: 'boss' not in [None, 'dev', 'lead']", errors)

    def test_additional_properties_false_and_schema(self):
        errors = schema.validate({"name": "Ana", "age": 1, "x": 1, "extra": {"a": "no"}}, PERSON)
        self.assertIn("$: unexpected key 'x'", errors)
        self.assertIn("$.extra.a: expected integer", errors)

    def test_array_min_items_and_item_errors(self):
        self.assertEqual(schema.validate({"name": "Ana", "age": 1, "tags": []}, PERSON),
                         ["$.tags: expected at least 1 item(s)"])
        self.assertEqual(schema.validate({"name": "Ana", "age": 1, "tags": [3]}, PERSON),
                         ["$.tags[0]: expected string"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `python3 -m unittest tests.test_schema -v` (desde la raíz, con `PYTHONPATH=tests` si hace falta: `PYTHONPATH=tests python3 -m unittest discover -s tests -p test_schema.py -v`)
Expected: ERROR `No module named 'schema'`.

- [ ] **Step 3: Implementar `wow/schema.py`**

```python
"""Minimal JSON Schema subset validator (stdlib only)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, List

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"

_PY_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _is_type(value: Any, name: str) -> bool:
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _PY_TYPES[name])


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate(instance: Any, schema: dict, path: str = "$") -> List[str]:
    expected = schema.get("type")
    if expected is not None:
        names = expected if isinstance(expected, list) else [expected]
        if not any(_is_type(instance, name) for name in names):
            return [f"{path}: expected {'|'.join(names)}"]

    errors: List[str] = []
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in {schema['enum']!r}")
    if isinstance(instance, str) and "pattern" in schema and not re.search(schema["pattern"], instance):
        errors.append(f"{path}: {instance!r} does not match {schema['pattern']}")
    if _is_number(instance):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance} is less than minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: {instance} is greater than maximum {schema['maximum']}")

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required key '{key}'")
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties")
        for key, value in instance.items():
            if key in properties:
                errors.extend(validate(value, properties[key], f"{path}.{key}"))
            elif extra is False:
                errors.append(f"{path}: unexpected key '{key}'")
            elif isinstance(extra, dict):
                errors.extend(validate(value, extra, f"{path}.{key}"))

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: expected at least {schema['minItems']} item(s)")
        if "items" in schema:
            for index, item in enumerate(instance):
                errors.extend(validate(item, schema["items"], f"{path}[{index}]"))
    return errors


def load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))
```

Nota para el implementador: el test de `enum` espera `"$.role: 'boss' not in [None, 'dev', 'lead']"`; `{schema['enum']!r}` produce exactamente eso.

- [ ] **Step 4: Correr y verificar que pasa**

Run: `python3 -m unittest discover -s tests -v`
Expected: todos OK (3 de Task 1 + 7 nuevos).

- [ ] **Step 5: Checkpoint (sin commit)**

Run: `/usr/bin/python3 -m unittest discover -s tests -v` → todos OK.

---

### Task 3: Config y credenciales de Jira

**Files:**
- Create: `wow/config.py`, `tests/test_config.py`

**Interfaces:**
- Produces:
  - `config.DEFAULTS: dict` (ver código).
  - `config.ConfigError(Exception)`.
  - `config.load_config(project: Path) -> dict`: `DEFAULTS` fusionado en profundidad con `.wow/config.json` si existe; JSON inválido → `ConfigError`.
  - `config.parse_dotenv(text: str) -> dict[str, str]`.
  - `config.JiraCreds` con atributos `base_url, email, token, project_key, child_mode`; `repr()` nunca muestra el token.
  - `config.resolve_jira_credentials(project: Path, environ: Mapping[str, str] | None = None) -> JiraCreds | None`.

- [ ] **Step 1: Escribir el test que falla**

`tests/test_config.py`:

```python
from __future__ import annotations

import unittest

from helpers import make_project, write
import config

SECRET = "tok-SECRET-123"


class LoadConfigTest(unittest.TestCase):
    def test_defaults_when_no_file(self):
        cfg = config.load_config(make_project())
        self.assertEqual(cfg["models"]["cursor_generate"], "composer-2.5")
        self.assertEqual(cfg["reviewers"], ["codex", "copilot"])

    def test_file_overrides_are_deep_merged(self):
        project = make_project()
        write(project, ".wow/config.json", '{"models": {"cursor_generate": "grok-4.7-medium"}}')
        cfg = config.load_config(project)
        self.assertEqual(cfg["models"]["cursor_generate"], "grok-4.7-medium")
        self.assertEqual(cfg["models"]["author"], "claude-opus")

    def test_invalid_json_raises_config_error(self):
        project = make_project()
        write(project, ".wow/config.json", "{nope")
        with self.assertRaises(config.ConfigError):
            config.load_config(project)


class DotenvTest(unittest.TestCase):
    def test_parses_export_quotes_and_comments(self):
        text = '# c\nexport A="1"\nB=\'two\'\nC=3=4\n\n'
        self.assertEqual(config.parse_dotenv(text), {"A": "1", "B": "two", "C": "3=4"})


class CredentialsTest(unittest.TestCase):
    def test_shell_environment_wins(self):
        project = make_project()
        write(project, ".env.local", "IC_JIRA_BASE_URL=https://file.example\n")
        env = {"IC_JIRA_BASE_URL": "https://shell.example", "IC_JIRA_USER_EMAIL": "a@b.c",
               "IC_JIRA_API_TOKEN": SECRET}
        creds = config.resolve_jira_credentials(project, env)
        self.assertEqual(creds.base_url, "https://shell.example")
        self.assertEqual(creds.child_mode, "parent")

    def test_env_local_then_spec_kit_fallback_per_key(self):
        project = make_project()
        write(project, ".env.local", "IC_JIRA_USER_EMAIL=local@b.c\nIC_JIRA_PROJECT_KEY=IRIS\n")
        write(project, ".spec-kit/.env", f"JIRA_BASE_URL=https://sk.example\nJIRA_EMAIL=sk@b.c\nJIRA_API_TOKEN={SECRET}\n")
        creds = config.resolve_jira_credentials(project, {})
        self.assertEqual((creds.base_url, creds.email, creds.project_key),
                         ("https://sk.example", "local@b.c", "IRIS"))
        self.assertEqual(creds.token, SECRET)

    def test_missing_required_returns_none(self):
        self.assertIsNone(config.resolve_jira_credentials(make_project(), {"IC_JIRA_BASE_URL": "x"}))

    def test_repr_never_contains_token(self):
        env = {"IC_JIRA_BASE_URL": "https://x", "IC_JIRA_USER_EMAIL": "a@b.c", "IC_JIRA_API_TOKEN": SECRET}
        creds = config.resolve_jira_credentials(make_project(), env)
        self.assertNotIn(SECRET, repr(creds))
        self.assertNotIn(SECRET, str(creds))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `python3 -m unittest discover -s tests -v`
Expected: ERROR `No module named 'config'`.

- [ ] **Step 3: Implementar `wow/config.py`**

```python
"""Project configuration and Jira credential resolution. Never prints secrets."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Dict, Mapping, Optional

DEFAULTS: dict = {
    "schema_version": 1,
    "reviewers": ["codex", "copilot"],
    "models": {
        "author": "claude-opus",
        "reviewer": "codex",
        "product_brain": "gemini-3.1-pro",
        "cursor_generate": "composer-2.5",
        "cursor_reason": "claude-sonnet-5-5-high",
    },
}

_SPEC_KIT_MAP = {
    "JIRA_BASE_URL": "IC_JIRA_BASE_URL",
    "JIRA_EMAIL": "IC_JIRA_USER_EMAIL",
    "JIRA_API_TOKEN": "IC_JIRA_API_TOKEN",
}


class ConfigError(Exception):
    """Raised when .wow/config.json cannot be read."""


def _merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(project: Path) -> dict:
    path = project / ".wow" / "config.json"
    if not path.is_file():
        return copy.deepcopy(DEFAULTS)
    try:
        override = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f".wow/config.json is not valid JSON: line {exc.lineno} column {exc.colno}: {exc.msg}")
    if not isinstance(override, dict):
        raise ConfigError(".wow/config.json must contain a JSON object")
    return _merge(DEFAULTS, override)


def parse_dotenv(text: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _read_dotenv(path: Path) -> Dict[str, str]:
    if not path.is_file():
        return {}
    return parse_dotenv(path.read_text(encoding="utf-8-sig"))


class JiraCreds:
    """Resolved Jira credentials. repr/str never expose the token."""

    __slots__ = ("base_url", "email", "token", "project_key", "child_mode")

    def __init__(self, base_url: str, email: str, token: str,
                 project_key: Optional[str], child_mode: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.token = token
        self.project_key = project_key
        self.child_mode = child_mode

    def __repr__(self) -> str:
        return (f"JiraCreds(base_url={self.base_url!r}, email={self.email!r}, token='***', "
                f"project_key={self.project_key!r}, child_mode={self.child_mode!r})")

    __str__ = __repr__


def resolve_jira_credentials(project: Path, environ: Optional[Mapping[str, str]] = None) -> Optional[JiraCreds]:
    env = dict(os.environ if environ is None else environ)
    spec_kit = {_SPEC_KIT_MAP[k]: v for k, v in _read_dotenv(project / ".spec-kit" / ".env").items()
                  if k in _SPEC_KIT_MAP}
    layers = [env, _read_dotenv(project / ".env.local"), spec_kit]

    def pick(name: str) -> Optional[str]:
        for layer in layers:
            value = layer.get(name)
            if value:
                return value
        return None

    base_url, email, token = pick("IC_JIRA_BASE_URL"), pick("IC_JIRA_USER_EMAIL"), pick("IC_JIRA_API_TOKEN")
    if not (base_url and email and token):
        return None
    return JiraCreds(base_url, email, token, pick("IC_JIRA_PROJECT_KEY"),
                     pick("IC_JIRA_EPIC_CHILD_MODE") or "parent")
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `python3 -m unittest discover -s tests -v` → todos OK.

- [ ] **Step 5: Checkpoint (sin commit)**

Run: `/usr/bin/python3 -m unittest discover -s tests -v` → todos OK.

---

### Task 4: Schema del manifiesto, `manifest.py` y comandos `manifest` / `plan`

**Files:**
- Create: `schemas/manifest.schema.json`, `wow/manifest.py`, `tests/test_manifest.py`
- Modify: `wow/cli.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `schema.validate`, `schema.load_schema` (Task 2); `exitcodes` (Task 1).
- Produces:
  - `manifest.MANIFEST_REL = Path("wow/plan/manifest.json")`
  - `manifest.ManifestError(Exception)` (falta o no parsea), `manifest.FrozenError(Exception)`
  - `manifest.load(project: Path) -> dict`
  - `manifest.save(project: Path, doc: dict) -> None` (indent 2, `ensure_ascii=False`, newline final)
  - `manifest.manifest_hash(project: Path) -> str` (16 hex del SHA-256 de los bytes del archivo)
  - `manifest.validate(doc: dict) -> list[str]`, `manifest.lint(doc: dict) -> list[str]`
  - `manifest.new_manifest(plan_id: str, title: str, created: str) -> dict`
  - `manifest.parse_epic_keys(text: str) -> dict[str, str]` (`"E1=IRIS-40,E2=IRIS-41"`; error → `ValueError`)
  - `manifest.freeze(doc: dict, epic_keys: dict[str, str], now: str) -> dict` (devuelve copia; suma keys aunque ya esté congelado)
  - `manifest.ensure_writable(doc: dict, reopen_reason: str | None) -> None` (congelado sin motivo → `FrozenError`)
  - CLI: `wow manifest validate|lint [--project DIR]`, `wow plan init PLAN_ID --title T [--project DIR]`, `wow plan freeze --epics E1=KEY[,…] [--project DIR]`.

- [ ] **Step 1: Escribir `schemas/manifest.schema.json`**

```json
{
  "type": "object",
  "required": ["schema_version", "plan", "epics"],
  "additionalProperties": false,
  "properties": {
    "schema_version": {"type": "integer", "enum": [1]},
    "plan": {
      "type": "object",
      "required": ["id", "title", "created", "readiness", "export"],
      "additionalProperties": false,
      "properties": {
        "id": {"type": "string", "pattern": "^[0-9]{4}-[a-z0-9-]+$"},
        "title": {"type": "string"},
        "created": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"},
        "readiness": {
          "type": "object",
          "required": ["verdict", "rounds"],
          "additionalProperties": false,
          "properties": {
            "verdict": {"type": ["string", "null"], "enum": [null, "approved", "changes_required", "hitl"]},
            "rounds": {"type": "integer", "minimum": 0, "maximum": 3}
          }
        },
        "export": {
          "type": "object",
          "required": ["frozen", "at", "epics"],
          "additionalProperties": false,
          "properties": {
            "frozen": {"type": "boolean"},
            "at": {"type": ["string", "null"]},
            "epics": {"type": "object", "additionalProperties": {"type": "string", "pattern": "^[A-Z][A-Z0-9]*-[0-9]+$"}}
          }
        }
      }
    },
    "epics": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["id", "title", "done_when", "tasks"],
        "additionalProperties": false,
        "properties": {
          "id": {"type": "string", "pattern": "^E[0-9]+$"},
          "title": {"type": "string"},
          "done_when": {"type": "array", "items": {"type": "string", "pattern": "^E[0-9]+\\.C[0-9]+: "}},
          "tasks": {
            "type": "array",
            "minItems": 1,
            "items": {
              "type": "object",
              "required": ["id", "title", "acceptance", "depends_on", "subtasks", "estimate", "priority", "labels"],
              "additionalProperties": false,
              "properties": {
                "id": {"type": "string", "pattern": "^[0-9]+\\.[0-9]+$"},
                "title": {"type": "string"},
                "acceptance": {"type": "array", "items": {"type": "string", "pattern": "^AC[0-9]+: "}},
                "depends_on": {"type": "array", "items": {"type": "string"}},
                "subtasks": {"type": "array", "items": {"type": "string"}},
                "estimate": {"type": ["integer", "null"], "minimum": 0},
                "priority": {"type": ["string", "null"], "enum": [null, "high", "medium", "low"]},
                "labels": {"type": "array", "items": {"type": "string"}}
              }
            }
          }
        }
      }
    }
  }
}
```

Nota: es el modelo de `ic` v2 sin estado de ejecución por tarea (el manifiesto es solo upstream, D3) y con `estimate`, `priority`, `labels`, `readiness` y `export` del spec.

- [ ] **Step 2: Escribir el test que falla**

`tests/test_manifest.py`:

```python
from __future__ import annotations

import copy
import json
import unittest

from helpers import make_project, write
import manifest


def valid_doc() -> dict:
    return {
        "schema_version": 1,
        "plan": {"id": "0001-iris-v2", "title": "IRIS v2", "created": "2026-10-01",
                 "readiness": {"verdict": None, "rounds": 0},
                 "export": {"frozen": False, "at": None, "epics": {}}},
        "epics": [
            {"id": "E1", "title": "Curation", "done_when": ["E1.C1: analysts can curate"],
             "tasks": [
                 {"id": "1.1", "title": "Model", "acceptance": ["AC1: schema exists"], "depends_on": [],
                  "subtasks": ["write schema"], "estimate": 3, "priority": "high", "labels": ["backend"]},
                 {"id": "1.2", "title": "API", "acceptance": ["AC1: endpoint returns 200"], "depends_on": ["1.1"],
                  "subtasks": [], "estimate": 2, "priority": "medium", "labels": ["backend"]},
             ]},
        ],
    }


class ValidateTest(unittest.TestCase):
    def test_valid_doc(self):
        self.assertEqual(manifest.validate(valid_doc()), [])

    def test_schema_error_short_circuits(self):
        doc = valid_doc()
        doc["plan"]["readiness"]["rounds"] = 4
        self.assertEqual(manifest.validate(doc), ["$.plan.readiness.rounds: 4 is greater than maximum 3"])

    def test_duplicate_task_id_and_missing_dependency(self):
        doc = valid_doc()
        doc["epics"][0]["tasks"][1]["id"] = "1.1"
        doc["epics"][0]["tasks"][1]["depends_on"] = ["9.9"]
        errors = manifest.validate(doc)
        self.assertIn("duplicate task id '1.1'", errors)
        self.assertIn("task 1.1 depends on unknown task '9.9'", errors)

    def test_dependency_cycle(self):
        doc = valid_doc()
        doc["epics"][0]["tasks"][0]["depends_on"] = ["1.2"]
        self.assertIn("dependency cycle involving task '1.1'", manifest.validate(doc))

    def test_done_when_must_match_epic_and_ac_ids_unique(self):
        doc = valid_doc()
        doc["epics"][0]["done_when"] = ["E2.C1: wrong epic"]
        doc["epics"][0]["tasks"][0]["acceptance"] = ["AC1: a", "AC1: b"]
        errors = manifest.validate(doc)
        self.assertIn("epic E1: done_when 'E2.C1' does not belong to E1", errors)
        self.assertIn("task 1.1: duplicate acceptance id 'AC1'", errors)


class LintTest(unittest.TestCase):
    def test_lint_flags_missing_planning_fields(self):
        doc = valid_doc()
        task = doc["epics"][0]["tasks"][0]
        task.update({"acceptance": [], "estimate": None, "priority": None, "labels": []})
        doc["epics"][0]["done_when"] = []
        self.assertEqual(manifest.lint(doc), [
            "E1/1.1: no acceptance criteria",
            "E1/1.1: no estimate (story points)",
            "E1/1.1: no priority",
            "E1/1.1: no labels",
            "E1: no done_when",
        ])


class LoadSaveFreezeTest(unittest.TestCase):
    def test_load_missing_raises(self):
        with self.assertRaises(manifest.ManifestError):
            manifest.load(make_project())

    def test_load_invalid_json_reports_position(self):
        project = make_project()
        write(project, "wow/plan/manifest.json", '{"plan": ,}')
        with self.assertRaises(manifest.ManifestError) as ctx:
            manifest.load(project)
        self.assertIn("line 1 column", str(ctx.exception))

    def test_load_accepts_bom(self):
        project = make_project()
        (project / "wow/plan").mkdir(parents=True)
        (project / "wow/plan/manifest.json").write_bytes(b"\xef\xbb\xbf" + json.dumps(valid_doc()).encode())
        self.assertEqual(manifest.load(project)["plan"]["id"], "0001-iris-v2")

    def test_save_roundtrip_and_hash_changes(self):
        project = make_project()
        manifest.save(project, valid_doc())
        first = manifest.manifest_hash(project)
        self.assertEqual(len(first), 16)
        doc = manifest.load(project)
        doc["plan"]["title"] = "IRIS v2 b"
        manifest.save(project, doc)
        self.assertNotEqual(first, manifest.manifest_hash(project))
        self.assertTrue((project / manifest.MANIFEST_REL).read_text(encoding="utf-8").endswith("\n"))

    def test_parse_epic_keys(self):
        self.assertEqual(manifest.parse_epic_keys("E1=IRIS-40, E2=IRIS-41"), {"E1": "IRIS-40", "E2": "IRIS-41"})
        with self.assertRaises(ValueError):
            manifest.parse_epic_keys("E1:IRIS-40")

    def test_freeze_adds_keys_and_keeps_existing(self):
        doc = manifest.freeze(valid_doc(), {"E1": "IRIS-40"}, "2026-10-02T10:00:00Z")
        self.assertEqual(doc["plan"]["export"], {"frozen": True, "at": "2026-10-02T10:00:00Z", "epics": {"E1": "IRIS-40"}})
        again = manifest.freeze(doc, {}, "2026-10-03T10:00:00Z")
        self.assertEqual(again["plan"]["export"]["at"], "2026-10-02T10:00:00Z")

    def test_freeze_rejects_unknown_epic(self):
        with self.assertRaises(ValueError):
            manifest.freeze(valid_doc(), {"E9": "IRIS-1"}, "2026-10-02T10:00:00Z")

    def test_ensure_writable(self):
        frozen = manifest.freeze(valid_doc(), {"E1": "IRIS-40"}, "2026-10-02T10:00:00Z")
        manifest.ensure_writable(valid_doc(), None)
        manifest.ensure_writable(frozen, "owner changed scope")
        with self.assertRaises(manifest.FrozenError) as ctx:
            manifest.ensure_writable(frozen, None)
        self.assertIn("/spec-kit.amend", str(ctx.exception))

    def test_new_manifest_validates_but_lints_with_findings(self):
        doc = manifest.new_manifest("0002-demo", "Demo", "2026-10-01")
        self.assertEqual(manifest.validate(doc), [])
        self.assertTrue(manifest.lint(doc))


if __name__ == "__main__":
    unittest.main()
```

Agregar a `tests/test_cli.py` (dentro del mismo archivo, después de `VersionTest`):

```python
import json as _json

from helpers import make_project, write
import manifest as _manifest
from test_manifest import valid_doc


class ManifestCommandsTest(unittest.TestCase):
    def test_validate_missing_manifest_exits_2(self):
        code, _, err = run_cli(["manifest", "validate", "--project", str(make_project())])
        self.assertEqual(code, 2)
        self.assertIn("manifest not found", err)

    def test_validate_invalid_json_exits_2_without_traceback(self):
        project = make_project()
        write(project, "wow/plan/manifest.json", "{bad")
        code, _, err = run_cli(["manifest", "validate", "--project", str(project)])
        self.assertEqual(code, 2)
        self.assertNotIn("Traceback", err)

    def test_validate_and_lint_codes(self):
        project = make_project()
        _manifest.save(project, valid_doc())
        self.assertEqual(run_cli(["manifest", "validate", "--project", str(project)])[0], 0)
        self.assertEqual(run_cli(["manifest", "lint", "--project", str(project)])[0], 0)
        doc = valid_doc()
        doc["epics"][0]["tasks"][0]["labels"] = []
        _manifest.save(project, doc)
        code, out, _ = run_cli(["manifest", "lint", "--project", str(project)])
        self.assertEqual(code, 1)
        self.assertIn("E1/1.1: no labels", out)

    def test_plan_init_refuses_existing(self):
        project = make_project()
        self.assertEqual(run_cli(["plan", "init", "0001-demo", "--title", "Demo", "--project", str(project)])[0], 0)
        self.assertEqual(run_cli(["plan", "init", "0001-demo", "--title", "Demo", "--project", str(project)])[0], 1)

    def test_plan_freeze_records_keys(self):
        project = make_project()
        _manifest.save(project, valid_doc())
        code, _, _ = run_cli(["plan", "freeze", "--epics", "E1=IRIS-40", "--project", str(project)])
        self.assertEqual(code, 0)
        saved = _json.loads((project / "wow/plan/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["plan"]["export"]["epics"], {"E1": "IRIS-40"})
        self.assertTrue(saved["plan"]["export"]["frozen"])
```

- [ ] **Step 3: Correr y verificar que falla**

Run: `python3 -m unittest discover -s tests -v`
Expected: ERROR `No module named 'manifest'`.

- [ ] **Step 4: Implementar `wow/manifest.py`**

```python
"""Upstream kanban manifest: load, validate, lint, init and freeze (spec D3, 9.2)."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import schema as schema_mod

MANIFEST_REL = Path("wow/plan/manifest.json")


class ManifestError(Exception):
    """The manifest is missing or is not parseable JSON."""


class FrozenError(Exception):
    """A write was attempted on a frozen manifest without --reopen."""


def _path(project: Path) -> Path:
    return project / MANIFEST_REL


def load(project: Path) -> dict:
    path = _path(project)
    if not path.is_file():
        raise ManifestError(f"manifest not found: {MANIFEST_REL}")
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest is not valid JSON: line {exc.lineno} column {exc.colno}: {exc.msg}")


def save(project: Path, doc: dict) -> None:
    path = _path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def manifest_hash(project: Path) -> str:
    return hashlib.sha256(_path(project).read_bytes()).hexdigest()[:16]


def _tasks(doc: dict) -> Iterator[Tuple[dict, dict]]:
    for epic in doc["epics"]:
        for task in epic["tasks"]:
            yield epic, task


def validate(doc: dict) -> List[str]:
    errors = schema_mod.validate(doc, schema_mod.load_schema("manifest"))
    if errors:
        return errors
    seen_epics, tasks_by_id = set(), {}
    for epic in doc["epics"]:
        if epic["id"] in seen_epics:
            errors.append(f"duplicate epic id '{epic['id']}'")
        seen_epics.add(epic["id"])
        for item in epic["done_when"]:
            anchor = item.split(":", 1)[0]
            if not anchor.startswith(epic["id"] + "."):
                errors.append(f"epic {epic['id']}: done_when '{anchor}' does not belong to {epic['id']}")
    for _, task in _tasks(doc):
        if task["id"] in tasks_by_id:
            errors.append(f"duplicate task id '{task['id']}'")
        tasks_by_id[task["id"]] = task
        ac_ids = [item.split(":", 1)[0] for item in task["acceptance"]]
        for ac in sorted({a for a in ac_ids if ac_ids.count(a) > 1}):
            errors.append(f"task {task['id']}: duplicate acceptance id '{ac}'")
    for _, task in _tasks(doc):
        for dep in task["depends_on"]:
            if dep not in tasks_by_id:
                errors.append(f"task {task['id']} depends on unknown task '{dep}'")
    errors.extend(_cycles(tasks_by_id))
    return errors


def _cycles(tasks_by_id: Dict[str, dict]) -> List[str]:
    state: Dict[str, int] = {}  # 1 = visiting, 2 = done
    found: List[str] = []

    def visit(task_id: str) -> None:
        state[task_id] = 1
        for dep in tasks_by_id[task_id]["depends_on"]:
            if dep not in tasks_by_id:
                continue
            if state.get(dep) == 1:
                message = f"dependency cycle involving task '{dep}'"
                if message not in found:
                    found.append(message)
            elif state.get(dep) is None:
                visit(dep)
        state[task_id] = 2

    for task_id in tasks_by_id:
        if state.get(task_id) is None:
            visit(task_id)
    return found


def lint(doc: dict) -> List[str]:
    findings: List[str] = []
    for epic in doc["epics"]:
        for task in epic["tasks"]:
            ref = f"{epic['id']}/{task['id']}"
            if not task["acceptance"]:
                findings.append(f"{ref}: no acceptance criteria")
            if task["estimate"] is None:
                findings.append(f"{ref}: no estimate (story points)")
            if task["priority"] is None:
                findings.append(f"{ref}: no priority")
            if not task["labels"]:
                findings.append(f"{ref}: no labels")
        if not epic["done_when"]:
            findings.append(f"{epic['id']}: no done_when")
    return findings


def new_manifest(plan_id: str, title: str, created: str) -> dict:
    return {
        "schema_version": 1,
        "plan": {"id": plan_id, "title": title, "created": created,
                 "readiness": {"verdict": None, "rounds": 0},
                 "export": {"frozen": False, "at": None, "epics": {}}},
        "epics": [{
            "id": "E1", "title": "Replace with the first epic title", "done_when": [],
            "tasks": [{"id": "1.1", "title": "Replace with the first task title", "acceptance": [],
                       "depends_on": [], "subtasks": [], "estimate": None, "priority": None, "labels": []}],
        }],
    }


def parse_epic_keys(text: str) -> Dict[str, str]:
    keys: Dict[str, str] = {}
    for part in [p.strip() for p in text.split(",") if p.strip()]:
        if "=" not in part:
            raise ValueError(f"expected EPIC=KEY, got {part!r}")
        epic_id, key = [s.strip() for s in part.split("=", 1)]
        keys[epic_id] = key
    return keys


def freeze(doc: dict, epic_keys: Dict[str, str], now: str) -> dict:
    result = copy.deepcopy(doc)
    known = {epic["id"] for epic in result["epics"]}
    unknown = sorted(set(epic_keys) - known)
    if unknown:
        raise ValueError(f"unknown epic id(s): {', '.join(unknown)}")
    export = result["plan"]["export"]
    export["epics"].update(epic_keys)
    if not export["frozen"]:
        export["frozen"] = True
        export["at"] = now
    return result


def ensure_writable(doc: dict, reopen_reason: Optional[str]) -> None:
    export = doc["plan"]["export"]
    if export["frozen"] and not reopen_reason:
        raise FrozenError(
            f"manifest is frozen since {export['at']}: change scope through Product Brain (Artifact Engine) "
            f"and /spec-kit.amend, or pass --reopen \"<reason>\"")
```

- [ ] **Step 5: Agregar los subcomandos a `wow/cli.py`**

Reemplazar `build_parser` y agregar los handlers:

```python
import datetime as _dt
from pathlib import Path

import manifest


def _project(args) -> Path:
    return Path(args.project).resolve()


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cmd_manifest_validate(args) -> int:
    try:
        doc = manifest.load(_project(args))
    except manifest.ManifestError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    errors = manifest.validate(doc)
    for line in errors:
        print(line)
    return exitcodes.FINDINGS if errors else exitcodes.OK


def _cmd_manifest_lint(args) -> int:
    try:
        doc = manifest.load(_project(args))
    except manifest.ManifestError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    errors = manifest.validate(doc)
    if errors:
        for line in errors:
            print(line)
        return exitcodes.FINDINGS
    findings = manifest.lint(doc)
    for line in findings:
        print(line)
    return exitcodes.FINDINGS if findings else exitcodes.OK


def _cmd_plan_init(args) -> int:
    project = _project(args)
    if (project / manifest.MANIFEST_REL).exists():
        sys.stderr.write(f"wow: {manifest.MANIFEST_REL} already exists\n")
        return exitcodes.FINDINGS
    manifest.save(project, manifest.new_manifest(args.plan_id, args.title, _now()[:10]))
    print(f"created {manifest.MANIFEST_REL}")
    return exitcodes.OK


def _cmd_plan_freeze(args) -> int:
    project = _project(args)
    try:
        doc = manifest.load(project)
        keys = manifest.parse_epic_keys(args.epics)
        frozen = manifest.freeze(doc, keys, _now())
    except manifest.ManifestError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    except ValueError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.FINDINGS
    manifest.save(project, frozen)
    print(f"frozen; epics: {frozen['plan']['export']['epics']}")
    return exitcodes.OK


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="wow", description="WayOfWork CLI")
    parser.add_argument("--version", action="store_true", help="print the version and exit")
    sub = parser.add_subparsers(dest="command", parser_class=_Parser)

    def with_project(p):
        p.add_argument("--project", default=".", help="project root (default: current directory)")
        return p

    m = sub.add_parser("manifest", help="validate or lint the upstream manifest")
    msub = m.add_subparsers(dest="manifest_command", parser_class=_Parser)
    with_project(msub.add_parser("validate")).set_defaults(handler=_cmd_manifest_validate)
    with_project(msub.add_parser("lint")).set_defaults(handler=_cmd_manifest_lint)

    pl = sub.add_parser("plan", help="create or freeze the upstream plan")
    psub = pl.add_subparsers(dest="plan_command", parser_class=_Parser)
    init = with_project(psub.add_parser("init"))
    init.add_argument("plan_id")
    init.add_argument("--title", required=True)
    init.set_defaults(handler=_cmd_plan_init)
    fr = with_project(psub.add_parser("freeze"))
    fr.add_argument("--epics", required=True, help="EPIC=KEY pairs, comma separated")
    fr.set_defaults(handler=_cmd_plan_freeze)
    return parser
```

- [ ] **Step 6: Correr y verificar que pasa**

Run: `python3 -m unittest discover -s tests -v` → todos OK.

- [ ] **Step 7: Checkpoint (sin commit)**

Run: `/usr/bin/python3 -m unittest discover -s tests -v` → todos OK.

---

### Task 5: Fuente `repo` (context pack y paquetes de PB)

**Files:**
- Create: `wow/sources/__init__.py`, `wow/sources/repo.py`, `tests/test_repo.py`

**Interfaces:**
- Produces:
  - `sources.SourceUnavailable(Exception)` (lo usan Tasks 8 y 9).
  - `repo.context_pack_status(project: Path) -> dict` → `{"facts": bool, "pending_file": bool, "pending_open": int}`. `pending_open` cuenta líneas `- [ ]` en `wow/context-pack/pending-owner.md`.
  - `repo.packet_status(project: Path, mhash: str, epic_ids: list[str]) -> dict` → `{"prd": s, "rfc": s, "epics": {"E1": s, ...}}` con `s ∈ {"ok", "stale", "missing"}`. Un paquete es `ok` si contiene `manifest-hash=<mhash>`.
  - `repo.HASH_RE` = `re.compile(r"manifest-hash=([0-9a-f]{16})")`.

- [ ] **Step 1: Escribir el test que falla**

`tests/test_repo.py`:

```python
from __future__ import annotations

import unittest

from helpers import make_project, write
from sources import repo

H = "0123456789abcdef"


class ContextPackTest(unittest.TestCase):
    def test_empty_project(self):
        self.assertEqual(repo.context_pack_status(make_project()),
                         {"facts": False, "pending_file": False, "pending_open": 0})

    def test_counts_unchecked_items_only(self):
        project = make_project()
        write(project, "wow/context-pack/facts.md", "# Facts\n")
        write(project, "wow/context-pack/pending-owner.md",
              "- [ ] North Star\n- [x] SLA: [SIN DEFINIR] (accepted)\n  - [ ] rollout\n")
        self.assertEqual(repo.context_pack_status(project),
                         {"facts": True, "pending_file": True, "pending_open": 2})


class PacketTest(unittest.TestCase):
    def test_ok_stale_missing(self):
        project = make_project()
        write(project, "wow/pb/prd.md", f"<!-- wow: manifest-hash={H} -->\n# PRD\n")
        write(project, "wow/pb/rfc.md", "<!-- wow: manifest-hash=ffffffffffffffff -->\n")
        write(project, "wow/pb/epic-E1.md", f"<!-- wow: manifest-hash={H} -->\n")
        self.assertEqual(repo.packet_status(project, H, ["E1", "E2"]),
                         {"prd": "ok", "rfc": "stale", "epics": {"E1": "ok", "E2": "missing"}})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `python3 -m unittest discover -s tests -v` → ERROR `No module named 'sources'`.

- [ ] **Step 3: Implementar**

`wow/sources/__init__.py`:

```python
"""Read-only data sources. None of them writes outside the wow work directory."""


class SourceUnavailable(Exception):
    """A source could not be read; the message says why and never contains secrets."""
```

`wow/sources/repo.py`:

```python
"""Repo source: context pack and Product Brain packets under wow/."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

HASH_RE = re.compile(r"manifest-hash=([0-9a-f]{16})")
_UNCHECKED_RE = re.compile(r"^\s*-\s*\[ \]")


def context_pack_status(project: Path) -> dict:
    base = project / "wow" / "context-pack"
    pending = base / "pending-owner.md"
    open_items = 0
    if pending.is_file():
        open_items = sum(1 for line in pending.read_text(encoding="utf-8").splitlines() if _UNCHECKED_RE.match(line))
    return {"facts": (base / "facts.md").is_file(), "pending_file": pending.is_file(), "pending_open": open_items}


def _packet(path: Path, mhash: str) -> str:
    if not path.is_file():
        return "missing"
    match = HASH_RE.search(path.read_text(encoding="utf-8"))
    return "ok" if match and match.group(1) == mhash else "stale"


def packet_status(project: Path, mhash: str, epic_ids: List[str]) -> dict:
    base = project / "wow" / "pb"
    epics: Dict[str, str] = {eid: _packet(base / f"epic-{eid}.md", mhash) for eid in epic_ids}
    return {"prd": _packet(base / "prd.md", mhash), "rfc": _packet(base / "rfc.md", mhash), "epics": epics}
```

- [ ] **Step 4: Correr y verificar que pasa** — `python3 -m unittest discover -s tests -v` → todos OK.

- [ ] **Step 5: Checkpoint (sin commit)** — `/usr/bin/python3 -m unittest discover -s tests -v` → todos OK.

---

### Task 6: Fuente `pbchat` (copias de chats de Product Brain)

**Files:**
- Create: `wow/sources/pbchat.py`, `tests/test_pbchat.py`

**Interfaces:**
- Produces:
  - `pbchat.parse_chat(text: str) -> dict` → `{"closed": bool, "anchors": list[str]}` (anclas `AC<n>` y `E<n>.C<n>`, únicas y ordenadas).
  - `pbchat.chat_status(project: Path, doc: str) -> dict` → `{"present": bool, "closed": bool, "audit": str | None}`. Lee `wow/pb/chats/<doc>.md` y el campo `verdict` de `wow/pb/chats/<doc>.audit.json` (si el JSON no parsea, `audit` = `"unknown"`).
- Marca de cierre (spec 6.2): `100%`, "dalo/damos/doy por cerrado", "por cerrado/a". Como "100%" puede aparecer en otro contexto, la fase 3 exige además auditoría `approved` (Task 9).

- [ ] **Step 1: Escribir el test que falla**

`tests/test_pbchat.py`:

```python
from __future__ import annotations

import unittest

from helpers import make_project, write
from sources import pbchat


class ParseTest(unittest.TestCase):
    def test_closed_by_hundred_percent(self):
        self.assertTrue(pbchat.parse_chat("Con esto, el PRD llega al 100%.")["closed"])

    def test_closed_by_phrase(self):
        self.assertTrue(pbchat.parse_chat("Jose: dalo por cerrado")["closed"])
        self.assertTrue(pbchat.parse_chat("¡Perfecto! Damos por cerrado el PRD")["closed"])

    def test_open_chat(self):
        self.assertFalse(pbchat.parse_chat("Completamos 60% del documento")["closed"])

    def test_anchors_unique_sorted(self):
        text = "AC2: x\nAC1: y\nE1.C1: done\nAC1 again"
        self.assertEqual(pbchat.parse_chat(text)["anchors"], ["AC1", "AC2", "E1.C1"])


class StatusTest(unittest.TestCase):
    def test_missing_chat(self):
        self.assertEqual(pbchat.chat_status(make_project(), "prd"),
                         {"present": False, "closed": False, "audit": None})

    def test_chat_with_audit(self):
        project = make_project()
        write(project, "wow/pb/chats/prd.md", "... llega al 100%")
        write(project, "wow/pb/chats/prd.audit.json", '{"verdict": "approved"}')
        self.assertEqual(pbchat.chat_status(project, "prd"), {"present": True, "closed": True, "audit": "approved"})

    def test_unparseable_audit_is_unknown(self):
        project = make_project()
        write(project, "wow/pb/chats/rfc.md", "open")
        write(project, "wow/pb/chats/rfc.audit.json", "{nope")
        self.assertEqual(pbchat.chat_status(project, "rfc")["audit"], "unknown")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Correr y verificar que falla** — ERROR `cannot import name 'pbchat'`.

- [ ] **Step 3: Implementar `wow/sources/pbchat.py`**

```python
"""Local copies of Product Brain chats (spec D4)."""
from __future__ import annotations

import json
import re
from pathlib import Path

CLOSED_RE = re.compile(r"100\s*%|\b(?:dalo|damos|doy|lo doy)\s+por\s+cerrad[oa]|\bpor\s+cerrad[oa]", re.IGNORECASE)
ANCHOR_RE = re.compile(r"\b(AC[0-9]+|E[0-9]+\.C[0-9]+)\b")


def parse_chat(text: str) -> dict:
    return {"closed": bool(CLOSED_RE.search(text)), "anchors": sorted(set(ANCHOR_RE.findall(text)))}


def chat_status(project: Path, doc: str) -> dict:
    base = project / "wow" / "pb" / "chats"
    chat = base / f"{doc}.md"
    if not chat.is_file():
        return {"present": False, "closed": False, "audit": None}
    parsed = parse_chat(chat.read_text(encoding="utf-8"))
    audit_path = base / f"{doc}.audit.json"
    audit = None
    if audit_path.is_file():
        try:
            audit = json.loads(audit_path.read_text(encoding="utf-8")).get("verdict")
        except (json.JSONDecodeError, AttributeError):
            audit = "unknown"
    return {"present": True, "closed": parsed["closed"], "audit": audit}
```

- [ ] **Step 4: Correr y verificar que pasa** — todos OK.

- [ ] **Step 5: Checkpoint (sin commit)** — también con `/usr/bin/python3`.

---

### Task 7: Fuente `speckit` (specs, tasks y work units)

**Files:**
- Create: `wow/sources/speckit.py`, `tests/test_speckit.py`

**Interfaces:**
- Produces:
  - `speckit.parse_tasks(text: str) -> dict` → `{"total": int, "done": int, "stories": {KEY: {"total": int, "done": int}}, "lines": list[tuple[bool, str]]}`. Las líneas `- jira: KEY` se asocian a la tarea inmediatamente anterior (mismo regex que `push_status.py` de Spec-Kit).
  - `speckit.work_unit_ids(path: Path) -> list[str]` (acepta `{"work_units": [{"id": ...}]}` o una lista de objetos con `id`; archivo ausente o inválido → `[]`).
  - `speckit.features(project: Path) -> list[dict]`, cada uno: `{"dir": "specs/001-x", "epic_key": str | None, "has_plan": bool, "has_tasks": bool, "has_work_units": bool, "tasks_total": int, "tasks_done": int, "stories": {...}, "pending_work_units": list[str]}`. `work-units.json` se busca en la carpeta de la feature y, si no está, en `.spec-kit/work-units.json`. Una WU está hecha si alguna línea marcada `[x]` contiene su id.

- [ ] **Step 1: Escribir el test que falla**

`tests/test_speckit.py`:

```python
from __future__ import annotations

import unittest

from helpers import make_project, write
from sources import speckit

TASKS = (
    "## Phase 1: Setup\n"
    "- [x] T001 scaffold\n"
    "## Phase 3: Story 1\n"
    "- [x] T010 WU-001 model\n"
    "  - jira: IRIS-41\n"
    "- [ ] T011 WU-002 api\n"
    "\t- jira: IRIS-41\n"
    "- [x] T012 WU-003 ui\n"
    "  - jira: IRIS-42\n"
)


class ParseTasksTest(unittest.TestCase):
    def test_counts_and_story_mapping(self):
        parsed = speckit.parse_tasks(TASKS)
        self.assertEqual((parsed["total"], parsed["done"]), (4, 3))
        self.assertEqual(parsed["stories"], {"IRIS-41": {"total": 2, "done": 1}, "IRIS-42": {"total": 1, "done": 1}})

    def test_crlf_and_tabs(self):
        parsed = speckit.parse_tasks(TASKS.replace("\n", "\r\n"))
        self.assertEqual((parsed["total"], parsed["done"]), (4, 3))
        self.assertEqual(parsed["stories"]["IRIS-41"], {"total": 2, "done": 1})


class FeaturesTest(unittest.TestCase):
    def test_feature_with_epic_and_pending_wu(self):
        project = make_project()
        write(project, "specs/001-curation/spec.md", "# Spec\n**Jira Epic:** [IRIS-40](https://x/browse/IRIS-40)\n")
        write(project, "specs/001-curation/plan.md", "# Plan\n")
        write(project, "specs/001-curation/tasks.md", TASKS)
        write(project, "specs/001-curation/work-units.json",
              '{"work_units": [{"id": "WU-001"}, {"id": "WU-002"}, {"id": "WU-003"}]}')
        [feature] = speckit.features(project)
        self.assertEqual(feature["dir"], "specs/001-curation")
        self.assertEqual(feature["epic_key"], "IRIS-40")
        self.assertTrue(feature["has_plan"] and feature["has_tasks"] and feature["has_work_units"])
        self.assertEqual(feature["pending_work_units"], ["WU-002"])

    def test_work_units_fallback_and_no_epic(self):
        project = make_project()
        write(project, "specs/002-x/spec.md", "# Spec without epic\n")
        write(project, ".spec-kit/work-units.json", '[{"id": "WU-009"}]')
        [feature] = speckit.features(project)
        self.assertIsNone(feature["epic_key"])
        self.assertTrue(feature["has_work_units"])
        self.assertEqual(feature["pending_work_units"], ["WU-009"])

    def test_no_specs_dir(self):
        self.assertEqual(speckit.features(make_project()), [])

    def test_invalid_work_units_json(self):
        project = make_project()
        path = write(project, "w.json", "{bad")
        self.assertEqual(speckit.work_unit_ids(path), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Correr y verificar que falla** — ERROR `cannot import name 'speckit'`.

- [ ] **Step 3: Implementar `wow/sources/speckit.py`**

```python
"""Spec-Kit artifacts: specs/<feature>/, tasks.md and work-units.json (read only)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

EPIC_RE = re.compile(r"\*\*Jira Epic:\*\*\s*\[?([A-Z][A-Z0-9]*-[0-9]+)")
TASK_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s*(.*)$")
JIRA_RE = re.compile(r"^\s*-\s*jira:\s*([A-Z][A-Z0-9]*-\d+)\s*$", re.IGNORECASE)


def parse_tasks(text: str) -> dict:
    lines: List[Tuple[bool, str]] = []
    stories: Dict[str, Dict[str, int]] = {}
    last_checked: Optional[bool] = None
    for raw in text.splitlines():
        task = TASK_RE.match(raw)
        if task:
            last_checked = task.group(1).lower() == "x"
            lines.append((last_checked, task.group(2)))
            continue
        jira = JIRA_RE.match(raw)
        if jira and last_checked is not None:
            entry = stories.setdefault(jira.group(1).upper(), {"total": 0, "done": 0})
            entry["total"] += 1
            entry["done"] += 1 if last_checked else 0
            last_checked = None
    return {"total": len(lines), "done": sum(1 for checked, _ in lines if checked), "stories": stories, "lines": lines}


def work_unit_ids(path: Path) -> List[str]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    items = data.get("work_units", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    return [item["id"] for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)]


def features(project: Path) -> List[dict]:
    result: List[dict] = []
    specs = project / "specs"
    if not specs.is_dir():
        return result
    for spec in sorted(specs.glob("*/spec.md")):
        folder = spec.parent
        match = EPIC_RE.search(spec.read_text(encoding="utf-8"))
        tasks_path = folder / "tasks.md"
        parsed = parse_tasks(tasks_path.read_text(encoding="utf-8")) if tasks_path.is_file() else parse_tasks("")
        wu_path = folder / "work-units.json"
        if not wu_path.is_file():
            wu_path = project / ".spec-kit" / "work-units.json"
        wu_ids = work_unit_ids(wu_path)
        checked_text = [text for checked, text in parsed["lines"] if checked]
        pending = [wu for wu in wu_ids if not any(wu in text for text in checked_text)]
        result.append({
            "dir": folder.relative_to(project).as_posix(),
            "epic_key": match.group(1) if match else None,
            "has_plan": (folder / "plan.md").is_file(),
            "has_tasks": tasks_path.is_file(),
            "has_work_units": bool(wu_ids),
            "tasks_total": parsed["total"],
            "tasks_done": parsed["done"],
            "stories": parsed["stories"],
            "pending_work_units": pending,
        })
    return result
```

- [ ] **Step 4: Correr y verificar que pasa** — todos OK.

- [ ] **Step 5: Checkpoint (sin commit)** — también con `/usr/bin/python3`.

---

### Task 8: Fuente `jira` (cliente REST de solo lectura)

**Files:**
- Create: `wow/sources/jira.py`, `tests/test_jira.py`

**Interfaces:**
- Consumes: `config.JiraCreds` (Task 3), `sources.SourceUnavailable` (Task 5).
- Produces:
  - `jira.JiraClient(creds: JiraCreds, opener=None, timeout: float = 15.0)`; `opener(request, timeout=...)` devuelve un context manager con `.read() -> bytes` (por defecto `urllib.request.urlopen`).
  - `JiraClient.epic_summary(key: str) -> dict` → `{"key", "exists": bool, "stories": int, "done": int, "story_keys": list[str], "url": str}`. Usa `POST /rest/api/3/search/jql`, pagina con `nextPageToken`, excluye sub-tasks. Hijos por `parent = KEY`, o por `"Epic Link" = KEY` si `child_mode == "epic_link"`. HTTP 400 → `exists: False`. Otros errores HTTP, de red o JSON inválido → `SourceUnavailable` con motivo **sin token ni email**.

- [ ] **Step 1: Escribir el test que falla**

`tests/test_jira.py`:

```python
from __future__ import annotations

import io
import json
import unittest
import urllib.error

import helpers  # noqa: F401
from config import JiraCreds
from sources import SourceUnavailable
from sources.jira import JiraClient

TOKEN = "tok-SECRET-999"
CREDS = JiraCreds("https://acme.atlassian.net/", "dev@acme.io", TOKEN, "IRIS", "parent")


class FakeResponse:
    def __init__(self, payload: dict):
        self._data = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def issue(key: str, category: str) -> dict:
    return {"key": key, "fields": {"status": {"statusCategory": {"key": category}}}}


class EpicSummaryTest(unittest.TestCase):
    def test_paginates_counts_done_and_builds_url(self):
        pages = [{"issues": [issue("IRIS-41", "done")], "nextPageToken": "p2"},
                 {"issues": [issue("IRIS-42", "indeterminate")]}]
        seen = []

        def opener(request, timeout):
            body = json.loads(request.data.decode())
            seen.append(body)
            self.assertTrue(request.get_header("Authorization").startswith("Basic "))
            return FakeResponse(pages[len(seen) - 1])

        summary = JiraClient(CREDS, opener=opener).epic_summary("IRIS-40")
        self.assertEqual(summary, {"key": "IRIS-40", "exists": True, "stories": 2, "done": 1,
                                   "story_keys": ["IRIS-41", "IRIS-42"],
                                   "url": "https://acme.atlassian.net/browse/IRIS-40"})
        self.assertEqual(seen[0]["jql"], "parent = IRIS-40 AND issuetype not in subTaskIssueTypes()")
        self.assertEqual(seen[1]["nextPageToken"], "p2")

    def test_epic_link_mode(self):
        creds = JiraCreds("https://acme.atlassian.net", "dev@acme.io", TOKEN, "IRIS", "epic_link")
        captured = {}

        def opener(request, timeout):
            captured.update(json.loads(request.data.decode()))
            return FakeResponse({"issues": []})

        JiraClient(creds, opener=opener).epic_summary("IRIS-40")
        self.assertTrue(captured["jql"].startswith('"Epic Link" = IRIS-40'))

    def test_http_400_means_epic_does_not_exist(self):
        def opener(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 400, "Bad Request", {}, io.BytesIO(b"{}"))

        self.assertFalse(JiraClient(CREDS, opener=opener).epic_summary("IRIS-404")["exists"])

    def test_auth_error_is_unavailable_without_secrets(self):
        def opener(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 401, f"Unauthorized for {TOKEN}", {}, io.BytesIO(b""))

        with self.assertRaises(SourceUnavailable) as ctx:
            JiraClient(CREDS, opener=opener).epic_summary("IRIS-40")
        message = str(ctx.exception)
        self.assertIn("HTTP 401", message)
        self.assertNotIn(TOKEN, message)
        self.assertNotIn("dev@acme.io", message)

    def test_network_error_and_bad_json_are_unavailable(self):
        def offline(request, timeout):
            raise urllib.error.URLError("timed out")

        with self.assertRaises(SourceUnavailable):
            JiraClient(CREDS, opener=offline).epic_summary("IRIS-40")

        class Bad(FakeResponse):
            def read(self):
                return b"<html>"

        with self.assertRaises(SourceUnavailable):
            JiraClient(CREDS, opener=lambda r, timeout: Bad({})).epic_summary("IRIS-40")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Correr y verificar que falla** — ERROR `No module named 'sources.jira'`.

- [ ] **Step 3: Implementar `wow/sources/jira.py`**

```python
"""Read-only Jira Cloud client (urllib). Error messages never include credentials."""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Callable, Optional

from config import JiraCreds
from sources import SourceUnavailable


class JiraClient:
    def __init__(self, creds: JiraCreds, opener: Optional[Callable] = None, timeout: float = 15.0) -> None:
        self._creds = creds
        self._open = opener or urllib.request.urlopen
        self._timeout = timeout

    def _post(self, path: str, body: dict) -> dict:
        auth = base64.b64encode(f"{self._creds.email}:{self._creds.token}".encode()).decode()
        request = urllib.request.Request(
            self._creds.base_url + path, data=json.dumps(body).encode(), method="POST",
            headers={"Authorization": f"Basic {auth}", "Accept": "application/json",
                     "Content-Type": "application/json"})
        try:
            with self._open(request, timeout=self._timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 400:
                raise _NotFound()
            raise SourceUnavailable(f"jira: HTTP {exc.code} on {path}")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SourceUnavailable(f"jira: cannot reach {self._creds.base_url} ({type(exc).__name__})")
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise SourceUnavailable(f"jira: response from {path} is not JSON")

    def epic_summary(self, key: str) -> dict:
        if self._creds.child_mode == "epic_link":
            jql = f'"Epic Link" = {key}'
        else:
            jql = f"parent = {key}"
        jql += " AND issuetype not in subTaskIssueTypes()"
        url = f"{self._creds.base_url}/browse/{key}"
        issues, token = [], None
        try:
            while True:
                body = {"jql": jql, "fields": ["status"], "maxResults": 100}
                if token:
                    body["nextPageToken"] = token
                page = self._post("/rest/api/3/search/jql", body)
                issues.extend(page.get("issues", []))
                token = page.get("nextPageToken")
                if not token:
                    break
        except _NotFound:
            return {"key": key, "exists": False, "stories": 0, "done": 0, "story_keys": [], "url": url}
        done = sum(1 for i in issues
                   if (((i.get("fields") or {}).get("status") or {}).get("statusCategory") or {}).get("key") == "done")
        return {"key": key, "exists": True, "stories": len(issues), "done": done,
                "story_keys": sorted(i["key"] for i in issues), "url": url}


class _NotFound(Exception):
    """Internal: Jira answered 400 (unknown issue in JQL)."""
```

- [ ] **Step 4: Correr y verificar que pasa** — todos OK.

- [ ] **Step 5: Checkpoint (sin commit)** — también con `/usr/bin/python3`.

---

### Task 9: `state.py` y comando `wow state`

**Files:**
- Create: `wow/state.py`, `tests/test_state.py`
- Modify: `wow/cli.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `config.load_config`, `config.resolve_jira_credentials`, `config.ConfigError` (Task 3); `manifest.load/validate/manifest_hash/ManifestError` (Task 4); `repo.context_pack_status/packet_status` (Task 5); `pbchat.chat_status` (Task 6); `speckit.features` (Task 7); `JiraClient.epic_summary`, `SourceUnavailable` (Tasks 5, 8).
- Produces: `state.compute_state(project: Path, cfg: dict, jira=None) -> dict` con la forma:

```json
{"schema_version": 1,
 "plan": {"id": "…|null", "phase": 0, "stale_packets": [], "missing": ["…"]},
 "epics": [{"id": "E1", "title": "…", "jira": "IRIS-40|null", "jira_url": "…|null",
            "phase": 3, "reason": "…|null", "progress": "7/12|null", "missing": ["…"]}],
 "blockers": ["…"], "next_steps": [step, step, step], "steps_total": 9,
 "sources": {"jira": "ok|not_configured|<unavailable reason>"}}
```

  `phase` es un entero 0–6, `"done"` o `"unknown"`. Cada paso: `{"epic": "E1|null", "phase": int, "action": str, "where": "human|harness|product-brain|terminal|cursor", "model": str|null, "command": str, "why": str}`. `"terminal"` es un comando sin LLM (por ejemplo `spec-kit sync-status`). Orden de prioridad: `harness`, `product-brain` y `terminal` antes que `cursor`, y dentro de cada grupo por fase ascendente; se devuelven 3. Los pendientes del owner van en `blockers`, no en pasos.
  - `state.review_final(project: Path, ref: str) -> str | None` (campo `final` de `wow/reviews/<ref>.json`).
- CLI: `wow state [--project DIR]` imprime el JSON (indent 2) y sale con `0`; config inválida → `2`.

Reglas de fase (spec 6.2). Fases 0–2 del plan; si el plan no llegó a 3, cada épica hereda la fase del plan. Los pendientes del owner mantienen el plan en fase 0, pero los pasos de plan, paquetes y épicas se siguen calculando, porque el workflow corre las decisiones del owner en paralelo.

- [ ] **Step 1: Escribir el test que falla**

`tests/test_state.py`:

```python
from __future__ import annotations

import json
import unittest

from helpers import make_project, write
import config
import manifest
import state
from sources import SourceUnavailable
from test_manifest import valid_doc

CFG = config.DEFAULTS


class FakeJira:
    def __init__(self, summaries=None, error=None):
        self.summaries, self.error = summaries or {}, error

    def epic_summary(self, key):
        if self.error:
            raise SourceUnavailable(self.error)
        return self.summaries[key]


def summary(key, stories, done):
    return {"key": key, "exists": True, "stories": stories, "done": done,
            "story_keys": [], "url": f"https://acme.atlassian.net/browse/{key}"}


def project_at_phase_3():
    """Context pack done, readiness approved, packets fresh, manifest frozen with E1=IRIS-40."""
    p = make_project()
    write(p, "wow/context-pack/facts.md", "# Facts\n")
    write(p, "wow/context-pack/pending-owner.md", "- [x] North Star\n")
    doc = valid_doc()
    doc["plan"]["readiness"] = {"verdict": "approved", "rounds": 1}
    doc = manifest.freeze(doc, {"E1": "IRIS-40"}, "2026-10-02T10:00:00Z")
    manifest.save(p, doc)
    h = manifest.manifest_hash(p)
    for name in ("prd", "rfc", "epic-E1"):
        write(p, f"wow/pb/{name}.md", f"<!-- wow: manifest-hash={h} -->\n")
    return p


def close_chats(p, names=("prd", "rfc", "epic-E1")):
    for name in names:
        write(p, f"wow/pb/chats/{name}.md", "llega al 100%")
        write(p, f"wow/pb/chats/{name}.audit.json", '{"verdict": "approved"}')


TASKS_DONE = "- [x] T010 WU-001 model\n  - jira: IRIS-41\n- [x] T011 WU-002 api\n  - jira: IRIS-41\n"


def add_feature(p, tasks=TASKS_DONE):
    write(p, "specs/001-curation/spec.md", "**Jira Epic:** IRIS-40\n")
    write(p, "specs/001-curation/plan.md", "# Plan\n")
    write(p, "specs/001-curation/tasks.md", tasks)
    write(p, "specs/001-curation/work-units.json", '{"work_units": [{"id": "WU-001"}, {"id": "WU-002"}]}')


class PlanPhasesTest(unittest.TestCase):
    def test_fresh_project_is_phase_0_with_context_step(self):
        result = state.compute_state(make_project(), CFG)
        self.assertEqual(result["plan"]["phase"], 0)
        self.assertEqual(result["next_steps"][0]["action"], "build the context pack")
        self.assertEqual(result["next_steps"][0]["where"], "harness")
        self.assertEqual(result["sources"]["jira"], "not_configured")

    def test_open_owner_items_are_blockers_and_planning_continues(self):
        p = make_project()
        write(p, "wow/context-pack/facts.md", "x")
        write(p, "wow/context-pack/pending-owner.md", "- [ ] North Star\n- [ ] SLA\n")
        result = state.compute_state(p, CFG)
        self.assertEqual(result["plan"]["phase"], 0)
        self.assertEqual(result["blockers"], ["owner: 2 decision(s) open in wow/context-pack/pending-owner.md"])
        self.assertEqual(result["next_steps"][0]["command"], "wow-plan")

    def test_readiness_pending_is_phase_1(self):
        p = make_project()
        write(p, "wow/context-pack/facts.md", "x")
        write(p, "wow/context-pack/pending-owner.md", "- [x] ok\n")
        manifest.save(p, valid_doc())
        result = state.compute_state(p, CFG)
        self.assertEqual(result["plan"]["phase"], 1)
        self.assertEqual(result["next_steps"][0]["command"], "wow review --set readiness --ref plan")

    def test_stale_packet_is_phase_2(self):
        p = project_at_phase_3()
        write(p, "wow/pb/epic-E1.md", "<!-- wow: manifest-hash=ffffffffffffffff -->\n")
        result = state.compute_state(p, CFG)
        self.assertEqual(result["plan"]["phase"], 2)
        self.assertEqual(result["plan"]["stale_packets"], ["epic-E1"])
        self.assertEqual(result["epics"][0]["phase"], 2)
        self.assertEqual(result["next_steps"][0]["command"], "wow pack epic --id E1")

    def test_invalid_manifest_json_gives_fix_step(self):
        p = make_project()
        write(p, "wow/context-pack/facts.md", "x")
        write(p, "wow/context-pack/pending-owner.md", "")
        write(p, "wow/plan/manifest.json", "{bad")
        result = state.compute_state(p, CFG)
        self.assertEqual(result["plan"]["phase"], 1)
        self.assertEqual(result["next_steps"][0]["command"], "wow manifest validate")


class EpicPhasesTest(unittest.TestCase):
    def test_phase_3_waits_for_prd_chat_first(self):
        result = state.compute_state(project_at_phase_3(), CFG, FakeJira({}))
        epic = result["epics"][0]
        self.assertEqual(epic["phase"], 3)
        self.assertEqual(result["next_steps"][0]["where"], "product-brain")
        self.assertIn("wow/pb/prd.md", result["next_steps"][0]["command"])

    def test_phase_3_unaudited_chat(self):
        p = project_at_phase_3()
        close_chats(p)
        write(p, "wow/pb/chats/rfc.audit.json", '{"verdict": "changes_required"}')
        result = state.compute_state(p, CFG, FakeJira({}))
        self.assertEqual(result["next_steps"][0]["action"], "audit the RFC chat")

    def test_jira_unavailable_makes_epic_unknown(self):
        p = project_at_phase_3()
        close_chats(p)
        result = state.compute_state(p, CFG, FakeJira(error="jira: HTTP 401 on /rest/api/3/search/jql"))
        self.assertEqual(result["epics"][0]["phase"], "unknown")
        self.assertEqual(result["epics"][0]["reason"], "jira: HTTP 401 on /rest/api/3/search/jql")
        self.assertEqual(result["sources"]["jira"], "jira: HTTP 401 on /rest/api/3/search/jql")

    def test_jira_not_configured_makes_epic_unknown(self):
        p = project_at_phase_3()
        close_chats(p)
        self.assertEqual(state.compute_state(p, CFG, None)["epics"][0]["phase"], "unknown")

    def test_phase_4_sync_step_uses_cursor(self):
        p = project_at_phase_3()
        close_chats(p)
        result = state.compute_state(p, CFG, FakeJira({"IRIS-40": summary("IRIS-40", 2, 0)}))
        epic = result["epics"][0]
        self.assertEqual(epic["phase"], 4)
        self.assertEqual(epic["jira_url"], "https://acme.atlassian.net/browse/IRIS-40")
        step = result["next_steps"][0]
        self.assertEqual((step["where"], step["model"], step["command"]),
                         ("cursor", "composer-2.5", "wow sk cmd sync --epic IRIS-40"))

    def test_phase_5_pending_work_unit_and_progress(self):
        p = project_at_phase_3()
        close_chats(p)
        add_feature(p, "- [x] T010 WU-001 model\n  - jira: IRIS-41\n- [ ] T011 WU-002 api\n  - jira: IRIS-41\n")
        result = state.compute_state(p, CFG, FakeJira({"IRIS-40": summary("IRIS-40", 2, 0)}))
        epic = result["epics"][0]
        self.assertEqual((epic["phase"], epic["progress"]), (5, "1/2"))
        self.assertEqual(result["next_steps"][0]["command"], "wow run-wu WU-002")

    def test_phase_5_story_review_before_cursor(self):
        p = project_at_phase_3()
        close_chats(p)
        add_feature(p)
        result = state.compute_state(p, CFG, FakeJira({"IRIS-40": summary("IRIS-40", 2, 0)}))
        self.assertEqual(result["epics"][0]["phase"], 5)
        self.assertEqual(result["next_steps"][0]["command"], "wow review --set story --ref IRIS-41")

    def test_phase_6_and_done(self):
        p = project_at_phase_3()
        close_chats(p)
        add_feature(p)
        write(p, "wow/reviews/IRIS-41.json", json.dumps({"final": "approved"}))
        jira = FakeJira({"IRIS-40": summary("IRIS-40", 2, 1)})
        result = state.compute_state(p, CFG, jira)
        self.assertEqual(result["epics"][0]["phase"], 6)
        commands = [s["command"] for s in result["next_steps"]]
        self.assertIn("spec-kit sync-status specs/001-curation --dry-run", commands)
        self.assertIn("wow review --set epic --ref E1", commands)
        write(p, "wow/reviews/E1.json", json.dumps({"final": "approved"}))
        done = state.compute_state(p, CFG, FakeJira({"IRIS-40": summary("IRIS-40", 2, 2)}))
        self.assertEqual(done["epics"][0]["phase"], "done")

    def test_at_most_three_steps_and_cursor_last(self):
        p = make_project()
        result = state.compute_state(p, CFG)
        self.assertLessEqual(len(result["next_steps"]), 3)
        wheres = [s["where"] for s in result["next_steps"]]
        self.assertEqual(wheres, sorted(wheres, key=lambda w: w == "cursor"))


if __name__ == "__main__":
    unittest.main()
```

Agregar a `tests/test_cli.py`:

```python
class StateCommandTest(unittest.TestCase):
    def test_state_on_fresh_project_prints_json_and_exits_ok(self):
        code, out, _ = run_cli(["state", "--project", str(make_project())])
        self.assertEqual(code, 0)
        self.assertEqual(_json.loads(out)["plan"]["phase"], 0)

    def test_state_with_invalid_config_exits_2(self):
        project = make_project()
        write(project, ".wow/config.json", "{bad")
        self.assertEqual(run_cli(["state", "--project", str(project)])[0], 2)

    def test_state_output_never_contains_token(self):
        project = make_project()
        write(project, ".env.local", "IC_JIRA_BASE_URL=http://127.0.0.1:9\nIC_JIRA_USER_EMAIL=a@b.c\n"
                                     "IC_JIRA_API_TOKEN=tok-SECRET-777\n")
        code, out, err = run_cli(["state", "--project", str(project)])
        self.assertEqual(code, 0)
        self.assertNotIn("tok-SECRET-777", out + err)
```

- [ ] **Step 2: Correr y verificar que falla** — ERROR `No module named 'state'`.

- [ ] **Step 3: Implementar `wow/state.py`**

```python
"""Derive plan and epic phases plus ranked next steps from the read-only sources (spec 6)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import manifest
from sources import SourceUnavailable, pbchat, repo, speckit

_WHERE_RANK = {"human": 0, "harness": 1, "product-brain": 1, "terminal": 1, "cursor": 2}
_CHAT_LABEL = {"prd": "PRD", "rfc": "RFC"}


def review_final(project: Path, ref: str) -> Optional[str]:
    path = project / "wow" / "reviews" / f"{ref}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("final")
    except (json.JSONDecodeError, AttributeError):
        return None


def _step(epic, phase, action, where, model, command, why) -> dict:
    return {"epic": epic, "phase": phase, "action": action, "where": where,
            "model": model, "command": command, "why": why}


def compute_state(project: Path, cfg: dict, jira=None) -> dict:
    models = cfg["models"]
    steps: List[dict] = []
    blockers: List[str] = []
    sources = {"jira": "ok" if jira is not None else "not_configured"}
    plan = {"id": None, "phase": 3, "stale_packets": [], "missing": []}
    epics_out: List[dict] = []

    # Phase 0: context pack. Open owner items block phase 0 but planning continues in parallel.
    cp = repo.context_pack_status(project)
    if not cp["facts"] or not cp["pending_file"]:
        plan["phase"] = 0
        steps.append(_step(None, 0, "build the context pack", "harness", models["author"], "wow-context",
                           "wow/context-pack/facts.md and pending-owner.md are required before planning"))
    if cp["pending_open"]:
        plan["phase"] = 0
        blockers.append(f"owner: {cp['pending_open']} decision(s) open in wow/context-pack/pending-owner.md")

    # Phase 1: manifest and readiness.
    doc = None
    try:
        doc = manifest.load(project)
    except manifest.ManifestError as exc:
        plan["phase"] = min(plan["phase"], 1)
        if "not found" in str(exc):
            steps.append(_step(None, 1, "plan the initiative", "harness", models["author"], "wow-plan",
                               "there is no wow/plan/manifest.json yet"))
        else:
            steps.append(_step(None, 1, "fix the manifest", "harness", models["author"], "wow manifest validate",
                               str(exc)))
    if doc is not None:
        errors = manifest.validate(doc)
        if errors:
            plan["phase"] = min(plan["phase"], 1)
            steps.append(_step(None, 1, "fix the manifest", "harness", models["author"], "wow manifest validate",
                               errors[0]))
            doc = None
    if doc is not None:
        plan["id"] = doc["plan"]["id"]
        if doc["plan"]["readiness"]["verdict"] != "approved":
            plan["phase"] = min(plan["phase"], 1)
            steps.append(_step(None, 1, "run the readiness review", "harness", models["reviewer"],
                               "wow review --set readiness --ref plan",
                               f"readiness verdict is {doc['plan']['readiness']['verdict']}"))
        # Phase 2: packets carry the current manifest hash.
        epic_ids = [e["id"] for e in doc["epics"]]
        packets = repo.packet_status(project, manifest.manifest_hash(project), epic_ids)
        named = [("prd", "prd", None), ("rfc", "rfc", None)] + \
                [(f"epic-{eid}", "epic", eid) for eid in epic_ids]
        for name, kind, eid in named:
            status = packets["epics"][eid] if eid else packets[name]
            if status == "ok":
                continue
            if status == "stale":
                plan["stale_packets"].append(name)
            plan["phase"] = min(plan["phase"], 2)
            command = f"wow pack {kind}" + (f" --id {eid}" if eid else "")
            verb = "regenerate" if status == "stale" else "generate"
            steps.append(_step(None, 2, f"{verb} the {name} packet", "harness", models["author"], command,
                               f"wow/pb/{name}.md is {status}"))

    plan["missing"] = [s["action"] for s in steps if s["epic"] is None]

    if doc is not None:
        features = speckit.features(project)
        for epic in doc["epics"]:
            out = _epic_state(project, cfg, doc, epic, features, jira, plan["phase"], sources)
            epics_out.append(out["epic"])
            steps.extend(out["steps"])

    ranked = sorted(steps, key=lambda s: (_WHERE_RANK[s["where"]], s["phase"]))
    return {"schema_version": 1, "plan": plan, "epics": epics_out, "blockers": blockers,
            "next_steps": ranked[:3], "steps_total": len(steps), "sources": sources}


def _epic_state(project, cfg, doc, epic, features, jira, plan_phase, sources) -> dict:
    models = cfg["models"]
    eid = epic["id"]
    key = doc["plan"]["export"]["epics"].get(eid)
    out = {"id": eid, "title": epic["title"], "jira": key, "jira_url": None,
           "phase": plan_phase, "reason": None, "progress": None, "missing": []}
    steps: List[dict] = []

    def finish(phase):
        out["phase"] = phase
        out["missing"] = [s["action"] for s in steps]
        return {"epic": out, "steps": steps}

    if plan_phase < 3:
        return finish(plan_phase)

    # Phase 3: PRD, RFC and epic chats closed and audited, epic exported with all stories.
    for doc_name in ("prd", "rfc", f"epic-{eid}"):
        label = _CHAT_LABEL.get(doc_name, f"epic {eid}")
        chat = pbchat.chat_status(project, doc_name)
        if not chat["present"] or not chat["closed"]:
            steps.append(_step(eid, 3, f"finish the {label} chat in Product Brain", "product-brain",
                               models["product_brain"], f"paste the preamble and wow/pb/{doc_name}.md",
                               f"wow/pb/chats/{doc_name}.md is missing or not closed"))
            return finish(3)
        if chat["audit"] != "approved":
            steps.append(_step(eid, 3, f"audit the {label} chat", "harness", models["reviewer"], "wow-pb-audit",
                               f"audit verdict is {chat['audit']}"))
            return finish(3)
    if not key:
        steps.append(_step(eid, 3, f"export epic {eid} to Jira and record its key", "product-brain", None,
                           f"wow plan freeze --epics {eid}=<KEY>", "the manifest has no Jira key for this epic"))
        return finish(3)
    if jira is None:
        out["reason"] = "jira not configured"
        return finish("unknown")
    try:
        summary = jira.epic_summary(key)
    except SourceUnavailable as exc:
        sources["jira"] = str(exc)
        out["reason"] = str(exc)
        return finish("unknown")
    out["jira_url"] = summary["url"]
    expected = len(epic["tasks"])
    if not summary["exists"] or summary["stories"] < expected:
        steps.append(_step(eid, 3, f"complete the stories of {key} in Jira", "product-brain", None,
                           "re-export the epic from Product Brain",
                           f"Jira has {summary['stories']} of {expected} stories"))
        return finish(3)

    # Phase 4: Spec-Kit feature synced and planned.
    feature = next((f for f in features if f["epic_key"] == key), None)
    if feature is None:
        steps.append(_step(eid, 4, "sync the epic into Spec-Kit", "cursor", models["cursor_generate"],
                           f"wow sk cmd sync --epic {key}", f"no specs/*/spec.md declares **Jira Epic:** {key}"))
        return finish(4)
    if not feature["has_plan"]:
        steps.append(_step(eid, 4, "ratify the plan", "cursor", models["cursor_reason"],
                           f"wow sk cmd plan --feature {feature['dir']}", "plan.md is missing"))
        return finish(4)
    if not feature["has_tasks"] or not feature["has_work_units"]:
        steps.append(_step(eid, 4, "ratify tasks and work units", "cursor", models["cursor_reason"],
                           f"wow sk cmd tasks --feature {feature['dir']}", "tasks.md or work-units.json is missing"))
        return finish(4)

    # Phase 5: implementation and per-story independent review.
    out["progress"] = f"{feature['tasks_done']}/{feature['tasks_total']}"
    for wu in feature["pending_work_units"]:
        steps.append(_step(eid, 5, f"implement {wu}", "cursor", models["cursor_generate"], f"wow run-wu {wu}",
                           f"{wu} is not checked in tasks.md"))
    for story, counts in sorted(feature["stories"].items()):
        if counts["done"] == counts["total"] and review_final(project, story) != "approved":
            steps.append(_step(eid, 5, f"review story {story}", "harness", models["reviewer"],
                               f"wow review --set story --ref {story}", "all its tasks are done and it has no approved review"))
    if steps or feature["tasks_done"] < feature["tasks_total"]:
        return finish(5)

    # Phase 6: Jira closed and epic closure review.
    if summary["done"] < summary["stories"]:
        steps.append(_step(eid, 6, f"close the stories of {key} in Jira", "terminal", None,
                           f"spec-kit sync-status {feature['dir']} --dry-run",
                           f"{summary['done']} of {summary['stories']} stories are done in Jira"))
    if review_final(project, eid) != "approved":
        steps.append(_step(eid, 6, f"review epic {eid}", "harness", models["reviewer"],
                           f"wow review --set epic --ref {eid}", "the epic has no approved closure review"))
    return finish(6 if steps else "done")
```

- [ ] **Step 4: Agregar el subcomando `state` a `wow/cli.py`**

```python
import json

import config
import state as state_mod
from sources.jira import JiraClient


def _jira_for(project: Path):
    creds = config.resolve_jira_credentials(project)
    return JiraClient(creds, timeout=5.0) if creds else None


def _cmd_state(args) -> int:
    project = _project(args)
    try:
        cfg = config.load_config(project)
    except config.ConfigError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    result = state_mod.compute_state(project, cfg, _jira_for(project))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return exitcodes.OK
```

Dentro de `build_parser`, antes de `return parser`:

```python
    with_project(sub.add_parser("state", help="print the derived state as JSON")).set_defaults(handler=_cmd_state)
```

- [ ] **Step 5: Correr y verificar que pasa** — `python3 -m unittest discover -s tests -v` → todos OK. (El test del token usa `127.0.0.1:9`, que rechaza la conexión: la épica no llega a consultar Jira porque el proyecto está en fase 0, y aun si lo hiciera, el error no lleva el token.)

- [ ] **Step 6: Checkpoint (sin commit)** — también con `/usr/bin/python3`.

---

### Task 10: `snapshot.py`, schema de progreso y comando `wow snapshot`

**Files:**
- Create: `schemas/progress.schema.json`, `wow/snapshot.py`, `tests/test_snapshot.py`
- Modify: `wow/cli.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `state.compute_state` (Task 9), `schema.validate/load_schema` (Task 2).
- Produces:
  - `snapshot.PROGRESS_REL = Path("wow/progress.json")`
  - `snapshot.history_point(state: dict, now: str) -> dict` → `{"ts", "plan_phase", "phases": {E1: phase}, "tasks_done": int, "tasks_total": int}` (`tasks_*` suman los `progress` conocidos).
  - `snapshot.build(state: dict, previous: dict | None, now: str) -> dict` → `{"schema_version": 1, "generated_at": now, "current": state, "history": [...previous, point], "usage": previous.usage or []}`.
  - `snapshot.load_previous(project: Path) -> dict | None` (archivo ausente o inválido → `None`).
  - `snapshot.write(project: Path, snap: dict) -> Path`.
  - CLI: `wow snapshot [--project DIR]` escribe el archivo, imprime `wrote wow/progress.json` y los próximos pasos (`- [where] action → command`), sale con `0`; config inválida → `2`.
  - `usage` queda como lista vacía hasta el Plan 2 (`wow usage`).

- [ ] **Step 1: Escribir `schemas/progress.schema.json`**

```json
{
  "type": "object",
  "required": ["schema_version", "generated_at", "current", "history", "usage"],
  "additionalProperties": false,
  "properties": {
    "schema_version": {"type": "integer", "enum": [1]},
    "generated_at": {"type": "string"},
    "current": {
      "type": "object",
      "required": ["schema_version", "plan", "epics", "blockers", "next_steps", "steps_total", "sources"],
      "properties": {
        "plan": {"type": "object", "required": ["id", "phase", "stale_packets", "missing"]},
        "epics": {"type": "array", "items": {"type": "object", "required": ["id", "phase", "jira", "missing"]}},
        "blockers": {"type": "array", "items": {"type": "string"}},
        "next_steps": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["epic", "phase", "action", "where", "model", "command", "why"],
            "properties": {"where": {"type": "string", "enum": ["human", "harness", "product-brain", "terminal", "cursor"]}}
          }
        },
        "steps_total": {"type": "integer", "minimum": 0},
        "sources": {"type": "object"}
      }
    },
    "history": {"type": "array", "items": {"type": "object", "required": ["ts", "plan_phase", "phases", "tasks_done", "tasks_total"]}},
    "usage": {"type": "array", "items": {"type": "object"}}
  }
}
```

- [ ] **Step 2: Escribir el test que falla**

`tests/test_snapshot.py`:

```python
from __future__ import annotations

import json
import unittest

from helpers import make_project, write
import config
import schema
import snapshot
import state


def fake_state(progress="3/4"):
    return {"schema_version": 1,
            "plan": {"id": "0001-x", "phase": 3, "stale_packets": [], "missing": []},
            "epics": [{"id": "E1", "title": "t", "jira": "IRIS-40", "jira_url": None, "phase": 5,
                       "reason": None, "progress": progress, "missing": ["implement WU-004"]},
                      {"id": "E2", "title": "u", "jira": None, "jira_url": None, "phase": "unknown",
                       "reason": "jira not configured", "progress": None, "missing": []}],
            "blockers": [], "next_steps": [], "steps_total": 1, "sources": {"jira": "ok"}}


class SnapshotTest(unittest.TestCase):
    def test_history_point_sums_known_progress(self):
        point = snapshot.history_point(fake_state(), "2026-10-02T10:00:00Z")
        self.assertEqual(point, {"ts": "2026-10-02T10:00:00Z", "plan_phase": 3,
                                 "phases": {"E1": 5, "E2": "unknown"}, "tasks_done": 3, "tasks_total": 4})

    def test_build_appends_history_and_keeps_usage(self):
        previous = {"history": [{"ts": "a", "plan_phase": 2, "phases": {}, "tasks_done": 0, "tasks_total": 0}],
                    "usage": [{"model": "x"}]}
        snap = snapshot.build(fake_state(), previous, "2026-10-02T10:00:00Z")
        self.assertEqual(len(snap["history"]), 2)
        self.assertEqual(snap["usage"], [{"model": "x"}])
        self.assertEqual(schema.validate(snap, schema.load_schema("progress")), [])

    def test_real_state_snapshot_validates_and_round_trips(self):
        project = make_project()
        snap = snapshot.build(state.compute_state(project, config.DEFAULTS), None, "2026-10-02T10:00:00Z")
        self.assertEqual(schema.validate(snap, schema.load_schema("progress")), [])
        path = snapshot.write(project, snap)
        self.assertEqual(snapshot.load_previous(project)["generated_at"], "2026-10-02T10:00:00Z")
        self.assertTrue(path.read_text(encoding="utf-8").endswith("\n"))

    def test_load_previous_ignores_invalid_file(self):
        project = make_project()
        write(project, "wow/progress.json", "{bad")
        self.assertIsNone(snapshot.load_previous(project))


if __name__ == "__main__":
    unittest.main()
```

Agregar a `tests/test_cli.py`:

```python
class SnapshotCommandTest(unittest.TestCase):
    def test_snapshot_writes_file_and_grows_history(self):
        project = make_project()
        code, out, _ = run_cli(["snapshot", "--project", str(project)])
        self.assertEqual(code, 0)
        self.assertIn("wrote wow/progress.json", out)
        self.assertIn("build the context pack", out)
        run_cli(["snapshot", "--project", str(project)])
        saved = _json.loads((project / "wow/progress.json").read_text(encoding="utf-8"))
        self.assertEqual(len(saved["history"]), 2)
```

- [ ] **Step 3: Correr y verificar que falla** — ERROR `No module named 'snapshot'`.

- [ ] **Step 4: Implementar `wow/snapshot.py`**

```python
"""Persist the derived state as wow/progress.json with a compact history (spec 7.1)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

PROGRESS_REL = Path("wow/progress.json")


def history_point(state: dict, now: str) -> dict:
    done = total = 0
    for epic in state["epics"]:
        progress = epic.get("progress")
        if progress:
            d, t = progress.split("/")
            done, total = done + int(d), total + int(t)
    return {"ts": now, "plan_phase": state["plan"]["phase"],
            "phases": {e["id"]: e["phase"] for e in state["epics"]},
            "tasks_done": done, "tasks_total": total}


def build(state: dict, previous: Optional[dict], now: str) -> dict:
    previous = previous or {}
    return {"schema_version": 1, "generated_at": now, "current": state,
            "history": list(previous.get("history", [])) + [history_point(state, now)],
            "usage": list(previous.get("usage", []))}


def load_previous(project: Path) -> Optional[dict]:
    path = project / PROGRESS_REL
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def write(project: Path, snap: dict) -> Path:
    path = project / PROGRESS_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
```

- [ ] **Step 5: Agregar el subcomando `snapshot` a `wow/cli.py`**

```python
import snapshot as snapshot_mod


def _cmd_snapshot(args) -> int:
    project = _project(args)
    try:
        cfg = config.load_config(project)
    except config.ConfigError as exc:
        sys.stderr.write(f"wow: {exc}\n")
        return exitcodes.CANNOT_EVALUATE
    result = state_mod.compute_state(project, cfg, _jira_for(project))
    snap = snapshot_mod.build(result, snapshot_mod.load_previous(project), _now())
    snapshot_mod.write(project, snap)
    print(f"wrote {snapshot_mod.PROGRESS_REL}")
    for blocker in result["blockers"]:
        print(f"! {blocker}")
    for step in result["next_steps"]:
        print(f"- [{step['where']}] {step['action']} -> {step['command']}")
    return exitcodes.OK
```

Dentro de `build_parser`, antes de `return parser`:

```python
    with_project(sub.add_parser("snapshot", help="write wow/progress.json")).set_defaults(handler=_cmd_snapshot)
```

- [ ] **Step 6: Correr y verificar que pasa** — todos OK.

- [ ] **Step 7: Checkpoint (sin commit)** — también con `/usr/bin/python3`.

---

### Task 11: Skill `wow-guide`, `install.sh` y README

**Files:**
- Create: `skills/wow-guide/SKILL.md`, `install.sh`, `README.md`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `wow snapshot` y `wow state` (Tasks 9–10).
- Produces: la skill instalable con `npx skills add <repo> --skill wow-guide` y el comando `wow` en el PATH.

- [ ] **Step 1: Escribir el test que falla (pinnea comportamiento, no prosa)**

Agregar a `tests/test_cli.py`:

```python
import re as _re


class SkillContractTest(unittest.TestCase):
    def test_guide_skill_frontmatter_and_commands_exist(self):
        text = (ROOT / "skills/wow-guide/SKILL.md").read_text(encoding="utf-8")
        front = _re.match(r"^---\nname: (.+)\ndescription: (.+)\n---\n", text)
        self.assertIsNotNone(front)
        self.assertEqual(front.group(1), "wow-guide")
        self.assertLessEqual(len(text.splitlines()), 80)
        for command in _re.findall(r"`wow ([a-z]+)", text):
            self.assertIn(command, {"snapshot", "state"})

    def test_install_script_is_executable(self):
        import os
        self.assertTrue(os.access(ROOT / "install.sh", os.X_OK))
```

- [ ] **Step 2: Correr y verificar que falla** — FAIL/ERROR: no existe `skills/wow-guide/SKILL.md`.

- [ ] **Step 3: Escribir `skills/wow-guide/SKILL.md`**

```markdown
---
name: wow-guide
description: Tell the operator what to do next in the WayOfWork flow (Product Brain + Spec-Kit + strong models): current phase per plan and epic, blockers, and up to three next steps with where to run them, which model and the exact command. Use when the user asks "what's next", "where am I", "qué sigue", or opens a work session.
---

# wow-guide

Read-only navigator. It never executes the steps it recommends.

## When to use

- The user asks what to do next, where the work stands, or starts a session.
- After any step finishes, to confirm the phase advanced.

## Steps

1. From the project root (the Spec-Kit parent repo), run `wow snapshot`.
   It writes `wow/progress.json` and prints blockers and next steps.
2. If you need the full state without writing anything, run `wow state` (JSON on stdout).
3. Explain the result to the user:
   - Blockers first (owner decisions). They are human tasks, never resolve them by inference.
   - Then up to three next steps, each with: action, **where** (`harness`, `product-brain`,
     `terminal`, `cursor`), model, exact command, and the `why` field.
   - Point out any epic whose phase is `unknown` and quote its `reason` verbatim.
   - Mention `sources` that are not `ok`.
4. Stop. Do not run the recommended commands unless the user asks for that specific step.

## Rules

- Do not infer phases from prose: the JSON is the source of truth.
- Never invent a step that is not in `next_steps`; if the list is empty and every epic is `done`,
  say the plan is complete.
- `cursor` steps spend the scarce Cursor pool: say so and suggest batching them.
- Exit code 2 means wow could not evaluate (for example an invalid `.wow/config.json`);
  report the message, do not guess.
```

- [ ] **Step 4: Escribir `install.sh` (y `chmod +x install.sh`)**

```bash
#!/usr/bin/env bash
# Install the `wow` CLI by symlinking it into a directory on PATH.
set -euo pipefail
TARGET_DIR="${1:-$HOME/.local/bin}"
SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/wow/wow"
mkdir -p "$TARGET_DIR"
chmod +x "$SOURCE"
ln -sf "$SOURCE" "$TARGET_DIR/wow"
echo "installed: $TARGET_DIR/wow -> $SOURCE"
case ":$PATH:" in
  *":$TARGET_DIR:"*) ;;
  *) echo "note: $TARGET_DIR is not on PATH" ;;
esac
```

- [ ] **Step 5: Escribir `README.md` (castellano)**

```markdown
# WayOfWork

Skills atómicas y un CLI (`wow`) para trabajar con Product Brain, Spec-Kit y modelos fuertes
(Claude, Codex) sin perder la telemetría de Spec-Kit ni gastar de más el pool de Cursor.

Diseño: `docs/superpowers/specs/2026-10-01-wayofwork-design.md`.

## Instalación

```bash
./install.sh                      # enlaza wow/wow en ~/.local/bin/wow
npx skills add <repo> --skill wow-guide
```

Requiere Python 3.9 o superior. No instala dependencias.

## Uso

Desde la raíz del repo padre de Spec-Kit:

```bash
wow snapshot      # escribe wow/progress.json y muestra bloqueos y próximos pasos
wow state         # el estado completo en JSON, sin escribir nada
wow manifest validate | lint
wow plan init 0001-mi-iniciativa --title "Mi iniciativa"
wow plan freeze --epics E1=IRIS-40
```

Credenciales de Jira: variables `IC_JIRA_BASE_URL`, `IC_JIRA_USER_EMAIL`, `IC_JIRA_API_TOKEN`
(opcionales: `IC_JIRA_PROJECT_KEY`, `IC_JIRA_EPIC_CHILD_MODE`). Se leen del shell, de `.env.local`
o, como último recurso, de `JIRA_*` en `.spec-kit/.env`. `wow` nunca las imprime.

Códigos de salida: `0` OK · `1` hallazgos · `2` no pude evaluar.

## Tests

```bash
python3 -m unittest discover -s tests -v
/usr/bin/python3 -m unittest discover -s tests -v   # verifica compatibilidad con 3.9
```
```

- [ ] **Step 6: Correr y verificar que pasa**

Run: `chmod +x install.sh && python3 -m unittest discover -s tests -v` → todos OK.

- [ ] **Step 7: Prueba de humo end-to-end**

Run:

```bash
TMP=$(mktemp -d) && ./install.sh "$TMP/bin" && "$TMP/bin/wow" --version \
  && "$TMP/bin/wow" snapshot --project "$TMP" && test -f "$TMP/wow/progress.json" && echo SMOKE-OK
```

Expected: `wow 0.1.0`, `wrote wow/progress.json`, la línea `- [harness] build the context pack -> wow-context` y `SMOKE-OK`.

- [ ] **Step 8: Checkpoint final (sin commit)**

Run: `python3 -m unittest discover -s tests -v && /usr/bin/python3 -m unittest discover -s tests -v`
Expected: todo OK en ambas versiones. Avisar al operador que el Plan 1 está listo para commitear cuando lo pida.

---

## Fuera de este plan (Planes 2 y 3)

- **Plan 2:** `wow usage` (Claude, Codex, `harness/runs`), `wow review` + skill `wow-review`, `wow pack` + `wow-pack`, `wow pbchat parse/audit` + `wow-pb-audit`, `wow context scan/check` + `wow-context`, `wow sk status/cmd`, `wow run-wu` + `wow-sk-prep`, fuente GitHub (`gh pr list --json`) y links en el snapshot.
- **Plan 3:** `dashboard/wow-dashboard.html`, en inglés y sin red, con los tres `progress.json` de ejemplo y render headless.
