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
