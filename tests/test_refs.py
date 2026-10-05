"""wow ref check: every commit or GitHub URL a document hands out exists and is reachable on its remote."""
from __future__ import annotations

import subprocess
import unittest

from helpers import make_project, run_cli, write
import refs


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
                          check=True, capture_output=True, text=True).stdout.strip()


def _workspace():
    """A workspace with one child repo whose origin is github.com/acme/engine and one commit."""
    root = make_project()
    engine = root / "engine"
    engine.mkdir()
    _git(engine, "init", "-q")
    _git(engine, "remote", "add", "origin", "git@github.com:acme/engine.git")
    write(engine, "a.txt", "x\n")
    _git(engine, "add", "-A")
    _git(engine, "commit", "-q", "-m", "c")
    return root, _git(engine, "rev-parse", "HEAD")


class ExtractTest(unittest.TestCase):
    def test_commits_and_github_urls(self):
        text = ("motor @ 53fd100, BFF @ 5b5bbacdeadbeef and https://github.com/acme/engine/blob/abc1234/x.py#L3; "
                "a color #101218 and a word like decade are not commits")
        self.assertEqual(refs.extract(text), [("sha", None, "53fd100"), ("sha", None, "5b5bbacdeadbeef"),
                                              ("url", "acme/engine", "abc1234")])


class UncheckedTest(unittest.TestCase):
    def test_bare_hashes_outside_the_checked_forms_are_reported(self):
        # The IRIS journey cited 13 commits as <code>a915f8b</code>: ref check said "0 references checked".
        text = ("WoW <code>a915f8b</code> y <code>2e76516</code>, motor @ 53fd100, "
                "https://github.com/acme/engine/blob/abc1234/x.py, color #101218, decade, cafebabe9")
        self.assertEqual(refs.unchecked(text), ["a915f8b", "2e76516", "cafebabe9"])

    def test_words_and_numbers_that_look_like_hex_are_not_hashes(self):
        self.assertEqual(refs.unchecked("decade facade 2026100 deadbeef 1234567 abcdefa"), [])


class CheckTest(unittest.TestCase):
    def test_a_commit_only_in_a_local_clone_is_an_error(self):
        root, sha = _workspace()
        on_remote = lambda repo, ref: False  # squash-merged and deleted branch: GitHub never saw it
        findings = refs.check(f"BFF @ {sha[:7]}", root, on_remote)
        self.assertEqual(findings, [f"{sha[:7]}: commit in engine but not on the default branch of acme/engine "
                                    "(local only, or a squash-merged/deleted branch): cite a commit on origin's default branch"])

    def test_reachable_commits_pass_and_unknown_ones_fail(self):
        root, sha = _workspace()
        seen = []
        on_remote = lambda repo, ref: seen.append((repo, ref)) or True
        self.assertEqual(refs.check(f"motor @ {sha[:7]}", root, on_remote), [])
        self.assertEqual(seen, [("acme/engine", sha)])
        self.assertEqual(refs.check("motor @ fd025ca", root, on_remote),
                         ["fd025ca: commit not found in any repo of the workspace"])

    def test_github_urls_are_checked_on_their_own_repo(self):
        root, _ = _workspace()
        seen = []
        on_remote = lambda repo, ref: seen.append((repo, ref)) or ref != "gone123"
        findings = refs.check("https://github.com/acme/other/blob/gone123/x.py and "
                              "https://github.com/acme/other/tree/main/docs", root, on_remote)
        self.assertEqual(seen, [("acme/other", "gone123"), ("acme/other", "main")])
        self.assertEqual(findings, ["https://github.com/acme/other @ gone123: not on the default branch, or not accessible"])


class CliTest(unittest.TestCase):
    def test_cli_codes(self):
        root, _ = _workspace()
        doc = write(root, "doc.md", "no refs here\n")
        self.assertEqual(run_cli(["ref", "check", str(doc), "--project", str(root)])[0], 0)
        write(root, "doc.md", "motor @ fd025ca\n")
        code, out, _ = run_cli(["ref", "check", str(doc), "--project", str(root)])
        self.assertEqual(code, 1)
        self.assertIn("fd025ca: commit not found", out)

    def test_cli_warns_about_bare_hashes_it_did_not_check(self):
        root, _ = _workspace()
        doc = write(root, "doc.md", "WoW <code>a915f8b</code> lo agregó\n")
        code, out, _ = run_cli(["ref", "check", str(doc), "--project", str(root)])
        self.assertEqual(code, 0)
        self.assertIn("not checked: a915f8b", out)
        self.assertIn("0 references checked, 0 findings, 1 bare hash not checked", out)


class PackCheckTest(unittest.TestCase):
    def test_a_packet_naming_a_missing_commit_does_not_go_to_product_brain(self):
        import pbtemplate
        from pbfill import fill
        root, _ = _workspace()
        write(root, "wow/pb/prd.md", fill(pbtemplate.load("prd")).replace("dato", "motor @ fd025ca", 1))
        code, out, _ = run_cli(["pack", "check", "prd", "--project", str(root)])
        self.assertEqual(code, 1)
        self.assertIn("error: fd025ca: commit not found in any repo of the workspace", out)


if __name__ == "__main__":
    unittest.main()
