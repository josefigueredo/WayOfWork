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
