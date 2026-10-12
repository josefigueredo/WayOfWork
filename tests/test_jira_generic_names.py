"""A new user is shown the generic JIRA_* names; IC_JIRA_* is one person's own alias, read but never advertised."""
from __future__ import annotations

import os
import unittest
from unittest import mock

from helpers import make_project, run_cli, write
import config

SECRET = "tok-SECRET-123"
GENERIC = {"JIRA_BASE_URL": "https://g.example", "JIRA_EMAIL": "g@x", "JIRA_API_TOKEN": "g-tok"}
ALIAS = {"IC_JIRA_BASE_URL": "https://ic.example", "IC_JIRA_USER_EMAIL": "ic@x", "IC_JIRA_API_TOKEN": "ic-tok"}


def _dotenv(**pairs: str) -> str:
    return "".join(f"{k}={v}\n" for k, v in pairs.items())


def _creds(project, environ):
    c = config.resolve_jira_credentials(project, environ)
    return None if c is None else (c.base_url, c.email, c.token)


class GenericNamesAreReadInEveryLayerTest(unittest.TestCase):
    def test_shell_environment(self):
        self.assertEqual(_creds(make_project(), GENERIC), ("https://g.example", "g@x", "g-tok"))

    def test_env_local(self):
        project = make_project()
        write(project, ".env.local", _dotenv(**GENERIC))
        self.assertEqual(_creds(project, {}), ("https://g.example", "g@x", "g-tok"))

    def test_spec_kit_env(self):
        project = make_project()
        write(project, ".spec-kit/.env", _dotenv(**GENERIC))
        self.assertEqual(_creds(project, {}), ("https://g.example", "g@x", "g-tok"))

    def test_the_optional_ones_have_a_generic_name_too(self):
        project = make_project()
        write(project, ".env.local", _dotenv(JIRA_PROJECT_KEY="IRIS", JIRA_EPIC_CHILD_MODE="epic-link"))
        creds = config.resolve_jira_credentials(project, GENERIC)
        self.assertEqual((creds.project_key, creds.child_mode), ("IRIS", "epic-link"))


class PersonalAliasStillWorksTest(unittest.TestCase):
    def test_each_layer_still_accepts_the_alias(self):
        self.assertEqual(_creds(make_project(), ALIAS), ("https://ic.example", "ic@x", "ic-tok"))
        project = make_project()
        write(project, ".env.local", _dotenv(**ALIAS))
        self.assertEqual(_creds(project, {}), ("https://ic.example", "ic@x", "ic-tok"))
        project = make_project()
        write(project, ".spec-kit/.env", _dotenv(**ALIAS))
        self.assertEqual(_creds(project, {}), ("https://ic.example", "ic@x", "ic-tok"))

    def test_the_alias_wins_over_the_generic_name_in_the_same_layer(self):
        # same order as jira-team-kit (jkan/config.py KEYS): layer first, then IC_ before JIRA_ inside a layer
        self.assertEqual(_creds(make_project(), {**GENERIC, **ALIAS}), ("https://ic.example", "ic@x", "ic-tok"))

    def test_a_closer_layer_beats_a_farther_one_whatever_the_name(self):
        project = make_project()
        write(project, ".env.local", _dotenv(IC_JIRA_BASE_URL="https://file.example"))
        env = {**GENERIC, "JIRA_BASE_URL": "https://shell.example"}
        self.assertEqual(_creds(project, env)[0], "https://shell.example")

    def test_the_two_families_mix_per_key(self):
        env = {"JIRA_BASE_URL": "https://g.example", "IC_JIRA_USER_EMAIL": "ic@x", "JIRA_API_TOKEN": SECRET}
        self.assertEqual(_creds(make_project(), env), ("https://g.example", "ic@x", SECRET))


class UserMessagesTest(unittest.TestCase):
    def test_the_missing_credentials_error_names_the_generic_variables(self):
        # clear=True: the shell running the suite may hold real credentials
        for argv in (["close", "--epic", "E1"], ["jira", "fix-fields", "--epic", "E1"]):
            with mock.patch.dict(os.environ, {}, clear=True):
                code, out, err = run_cli([*argv, "--project", str(make_project())])
            self.assertEqual(code, 2, argv)
            for name in GENERIC:
                self.assertIn(name, err, argv)
            self.assertNotIn("IC_JIRA", out + err, argv)


if __name__ == "__main__":
    unittest.main()
