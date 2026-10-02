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
