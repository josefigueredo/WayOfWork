from __future__ import annotations

import json
import subprocess
import unittest

from helpers import make_project
from sources import SourceUnavailable, github

PRS = [{"number": 7, "title": "IRIS-41 curate endpoint", "state": "OPEN", "url": "https://gh/x/7",
        "headRefName": "feat/IRIS-41", "statusCheckRollup": [{"conclusion": "SUCCESS"}]},
       {"number": 8, "title": "chore: deps", "state": "MERGED", "url": "https://gh/x/8",
        "headRefName": "deps", "statusCheckRollup": [{"conclusion": "FAILURE"}]}]


def runner(stdout, code=0):
    return lambda argv, cwd=None, capture_output=None, text=None, timeout=None: \
        subprocess.CompletedProcess(argv, code, stdout, "token=secret")


class GithubTest(unittest.TestCase):
    def test_pull_requests_and_link(self):
        prs = github.pull_requests(make_project(), runner(json.dumps(PRS)), which=lambda n: "/bin/gh")
        self.assertEqual([(p["number"], p["checks"]) for p in prs], [(7, "passing"), (8, "failing")])
        self.assertEqual([p["number"] for p in github.link(prs, {"IRIS-41"})], [7])

    def test_unavailable_without_secrets(self):
        with self.assertRaises(SourceUnavailable):
            github.pull_requests(make_project(), runner("[]"), which=lambda n: None)
        with self.assertRaises(SourceUnavailable) as ctx:
            github.pull_requests(make_project(), runner("", code=1), which=lambda n: "/bin/gh")
        self.assertNotIn("secret", str(ctx.exception))

    def test_checks_state(self):
        self.assertEqual(github.checks_state(None), "none")
        self.assertEqual(github.checks_state([{"status": "IN_PROGRESS"}]), "pending")
        self.assertEqual(github.checks_state([{"state": "SUCCESS"}, {"conclusion": "SUCCESS"}]), "passing")


class GithubDirsTest(unittest.TestCase):
    def test_snapshot_reads_nested_repos_and_skips_non_git_root(self):
        from unittest import mock
        from helpers import write
        import cli
        project = make_project()
        write(project, "engine/prism-group/.git/HEAD", "x")
        write(project, "product/dora-group/bff/.git/HEAD", "x")
        seen = []
        with mock.patch.object(cli.github, "pull_requests", side_effect=lambda d: seen.append(d.name) or []):
            prs, status = cli._github_prs(project, {"github": {"enabled": True}})
        self.assertEqual((sorted(seen), status), (["bff", "prism-group"], "ok"))
        with mock.patch.object(cli.github, "pull_requests", side_effect=AssertionError("no call")):
            self.assertEqual(cli._github_prs(make_project(), {}), ([], "no git repositories found"))


if __name__ == "__main__":
    unittest.main()
