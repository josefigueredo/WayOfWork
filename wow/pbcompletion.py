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


def _norm_heading(text: str) -> str:
    """Port of detector.ts normalizeHeading: no accents, lowercase, punctuation as spaces."""
    decomposed = unicodedata.normalize("NFD", text)
    value = "".join(c for c in decomposed if not unicodedata.combining(c)).lower()
    value = re.sub(r"[`*_]", "", value)
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _cells(line: str) -> List[str]:
    body = line.strip()
    body = body[1:] if body.startswith("|") else body
    body = body[:-1] if body.endswith("|") and not body.endswith("\\|") else body
    return [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", body)]


def _sections(text: str) -> List[Tuple[str, List[str]]]:
    sections: List[Tuple[str, List[str]]] = [("", [])]
    for line in text.splitlines():
        if _HEADING_RE.match(line):
            sections.append((line.strip(), []))
        else:
            sections[-1][1].append(line)
    return sections


def _heading_regex(template_heading: str) -> "re.Pattern[str]":
    """Regex over _norm_heading(packet heading); placeholders become named groups."""
    pieces = []  # (is_placeholder, regex)
    for part in re.split(r"(\{\{\s*[a-zA-Z0-9_.-]+\s*\}\})", template_heading):
        if part.startswith("{{"):
            pieces.append((True, f"(?P<{re.sub(r'[^a-z0-9_]', '_', part.strip('{} '))}>.*?)"))
        elif _norm_heading(part):
            pieces.append((False, re.escape(_norm_heading(part))))
    body = ""
    for index, (is_placeholder, regex) in enumerate(pieces):
        if index:
            # Two adjacent placeholders were separated by punctuation ("{{rfc_id}}: {{title}}"): keep a word boundary.
            body += r"\s+" if is_placeholder and pieces[index - 1][0] else r"\s*"
        body += regex
    return re.compile("^" + body + "$")


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
        if heading and regex.match(_norm_heading(heading)):
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
                match = _heading_regex(info["section"]).match(_norm_heading(heading))
                if re.search(r"\{\{\s*" + re.escape(name) + r"\s*\}\}", heading):
                    state = "empty"
                else:
                    state = value_state(match.group(re.sub(r"[^a-z0-9_]", "_", name)) if match else "")
            elif info["kind"] == "kv":
                rows = [_cells(l) for l in body if l.strip().startswith("|")]
                state = next((value_state(r[1]) for r in rows if len(r) > 1 and _norm(r[0]) == info["label"]), "empty")
            elif info["kind"] == "label":
                lines = [_LABEL_RE.match(l.strip()) for l in body]
                state = next((value_state(m.group(2)) for m in lines if m and _norm(m.group(1)) == info["label"]), "empty")
            elif info["kind"] == "open_questions":
                rows = [(r + ["", "", "", ""])[:4] for r in _table_rows(body)]
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
