"""Jira Cloud client (urllib): reads, plus the done transition `wow close` applies. Errors never include credentials."""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Callable, List, Optional

from config import JiraCreds
from sources import SourceUnavailable


_DONE_NAMES = ("done", "listo", "finalizado", "finalizada", "hecho", "cerrado", "closed", "resolved", "resuelto")


class _NotFound(Exception):
    """Internal: Jira answered 400 (unknown issue in JQL)."""


class JiraClient:
    def __init__(self, creds: JiraCreds, opener: Optional[Callable] = None, timeout: float = 15.0) -> None:
        self._creds = creds
        self._open = opener or urllib.request.urlopen
        self._timeout = timeout

    def _post(self, path: str, body: dict) -> dict:
        return self._send("POST", path, body)

    def _send(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        auth = base64.b64encode(f"{self._creds.email}:{self._creds.token}".encode()).decode()
        request = urllib.request.Request(
            self._creds.base_url + path, data=json.dumps(body).encode() if body is not None else None, method=method,
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
        if not raw:
            return {}  # 204 No Content, as the transitions POST answers
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
            # Jira hides a project the account cannot browse: searches come back empty, not 403. Without
            # this check an invisible epic would read as "exists with 0 stories" and ask for a re-export.
            epic = self._post("/rest/api/3/search/jql", {"jql": f"key = {key}", "fields": ["status"]}).get("issues")
            if not epic:
                raise SourceUnavailable(f"jira: {key} is not visible to this account "
                                        f"(no Browse permission on its project, or another site)")
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
        return {"key": key, "exists": True, "stories": len(issues), "done": done, "epic_done": self._done(epic[0]),
                "story_keys": sorted(i["key"] for i in issues), "url": url}

    def _search(self, jql: str, fields=("status",)) -> List[dict]:
        issues, token = [], None
        while True:
            body = {"jql": jql, "fields": list(fields), "maxResults": 100}
            if token:
                body["nextPageToken"] = token
            page = self._post("/rest/api/3/search/jql", body)
            issues.extend(page.get("issues", []))
            token = page.get("nextPageToken")
            if not token:
                return issues

    @staticmethod
    def _done(issue: dict) -> bool:
        return (((issue.get("fields") or {}).get("status") or {}).get("statusCategory") or {}).get("key") == "done"

    def open_issues(self, epic_key: str) -> List[dict]:
        """The epic, its children and their subtasks, with whether each one is already in the done category."""
        try:
            epic = self._search(f"key = {epic_key}")
            if not epic:
                raise SourceUnavailable(f"jira: {epic_key} is not visible to this account")
            # Same child rule as epic_summary: reading children the wrong way would close the epic over open work.
            link = f'"Epic Link" = {epic_key}' if self._creds.child_mode == "epic_link" else f"parent = {epic_key}"
            children = self._search(link)
            subtasks = self._search(f"parent in ({', '.join(i['key'] for i in children)})",
                                    fields=("status", "parent")) if children else []
        except _NotFound:
            raise SourceUnavailable(f"jira: Jira rejected the search for {epic_key} (unknown key or project?)")
        return ([{"key": i["key"], "level": "epic", "done": self._done(i)} for i in epic]
                + [{"key": i["key"], "level": "story", "done": self._done(i)} for i in children]
                + [{"key": i["key"], "level": "subtask", "done": self._done(i),
                    "parent": ((i.get("fields") or {}).get("parent") or {}).get("key")} for i in subtasks])

    def close(self, key: str) -> str:
        """Apply the transition that lands in the done status category; return that status name."""
        path = f"/rest/api/3/issue/{key}/transitions"
        try:
            transitions = self._send("GET", path).get("transitions", [])
            done = [tr for tr in transitions
                    if ((tr.get("to") or {}).get("statusCategory") or {}).get("key") == "done"]
            # "Won't Do" and "Cancelled" are also in the done category: finished work prefers a plain done status.
            target = next((tr for tr in done if (tr["to"].get("name") or "").lower() in _DONE_NAMES),
                          done[0] if done else None)
            if target is None:
                raise SourceUnavailable(f"jira: no done transition for {key}")
            self._send("POST", path, {"transition": {"id": target["id"]}})
        except _NotFound:
            raise SourceUnavailable(f"jira: {key} rejected the done transition (required fields?)")
        return target["to"].get("name", "done")
