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
            self.assertTrue(request.get_header("Authorization").startswith("Basic "))
            if body["jql"] == "key = IRIS-40":
                return FakeResponse({"issues": [issue("IRIS-40", "indeterminate")]})
            seen.append(body)
            return FakeResponse(pages[len(seen) - 1])

        summary = JiraClient(CREDS, opener=opener).epic_summary("IRIS-40")
        self.assertEqual(summary, {"key": "IRIS-40", "exists": True, "stories": 2, "done": 1, "epic_done": False,
                                   "story_keys": ["IRIS-41", "IRIS-42"],
                                   "url": "https://acme.atlassian.net/browse/IRIS-40"})
        self.assertEqual(seen[0]["jql"], "parent = IRIS-40 AND issuetype not in subTaskIssueTypes()")
        self.assertEqual(seen[1]["nextPageToken"], "p2")

    def test_epic_link_mode(self):
        creds = JiraCreds("https://acme.atlassian.net", "dev@acme.io", TOKEN, "IRIS", "epic_link")
        captured = {}

        def opener(request, timeout):
            body = json.loads(request.data.decode())
            if body["jql"] == "key = IRIS-40":
                return FakeResponse({"issues": [{"key": "IRIS-40", "fields": {}}]})
            captured.update(body)
            return FakeResponse({"issues": []})

        JiraClient(creds, opener=opener).epic_summary("IRIS-40")
        self.assertTrue(captured["jql"].startswith('"Epic Link" = IRIS-40'))

    def test_http_400_means_epic_does_not_exist(self):
        def opener(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 400, "Bad Request", {}, io.BytesIO(b"{}"))

        self.assertFalse(JiraClient(CREDS, opener=opener).epic_summary("IRIS-404")["exists"])

    def test_epic_invisible_to_the_account_is_unavailable_not_an_empty_epic(self):
        # Jira hides projects without Browse permission: every search comes back empty instead of 403.
        with self.assertRaises(SourceUnavailable) as ctx:
            JiraClient(CREDS, opener=lambda r, timeout: FakeResponse({"issues": []})).epic_summary("PLATE-491")
        self.assertIn("PLATE-491 is not visible", str(ctx.exception))
        self.assertNotIn(TOKEN, str(ctx.exception))

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
