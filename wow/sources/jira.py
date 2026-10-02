"""Read-only Jira Cloud client (urllib). Error messages never include credentials."""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Callable, Optional

from config import JiraCreds
from sources import SourceUnavailable


class _NotFound(Exception):
    """Internal: Jira answered 400 (unknown issue in JQL)."""


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
            # Jira hides a project the account cannot browse: searches come back empty, not 403. Without
            # this check an invisible epic would read as "exists with 0 stories" and ask for a re-export.
            if not self._post("/rest/api/3/search/jql", {"jql": f"key = {key}", "fields": ["status"]}).get("issues"):
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
        return {"key": key, "exists": True, "stories": len(issues), "done": done,
                "story_keys": sorted(i["key"] for i in issues), "url": url}
