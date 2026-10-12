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
    "github": {"enabled": True},
    "pricing": {"as_of": None, "per_mtok": {}},
}

# Generic names are the documented ones; IC_* are one person's own aliases, still read (and checked first in a layer).
KEYS = {
    "base_url": ("IC_JIRA_BASE_URL", "JIRA_BASE_URL"),
    "email": ("IC_JIRA_USER_EMAIL", "JIRA_EMAIL"),
    "token": ("IC_JIRA_API_TOKEN", "JIRA_API_TOKEN"),
    "project_key": ("IC_JIRA_PROJECT_KEY", "JIRA_PROJECT_KEY"),
    "child_mode": ("IC_JIRA_EPIC_CHILD_MODE", "JIRA_EPIC_CHILD_MODE"),
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
    layers = [dict(os.environ if environ is None else environ), _read_dotenv(project / ".env.local"),
              _read_dotenv(project / ".spec-kit" / ".env")]

    def pick(key: str) -> Optional[str]:
        for layer in layers:
            for name in KEYS[key]:
                if layer.get(name):
                    return layer[name]
        return None

    base_url, email, token = pick("base_url"), pick("email"), pick("token")
    if not (base_url and email and token):
        return None
    return JiraCreds(base_url, email, token, pick("project_key"), pick("child_mode") or "parent")
