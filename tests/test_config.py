from __future__ import annotations

import unittest

from helpers import make_project, write
import config

SECRET = "tok-SECRET-123"


class LoadConfigTest(unittest.TestCase):
    def test_defaults_when_no_file(self):
        cfg = config.load_config(make_project())
        self.assertEqual(cfg["models"]["cursor_generate"], "composer-2.5")
        self.assertEqual(cfg["reviewers"], ["codex", "copilot"])

    def test_file_overrides_are_deep_merged(self):
        project = make_project()
        write(project, ".wow/config.json", '{"models": {"cursor_generate": "grok-4.7-medium"}}')
        cfg = config.load_config(project)
        self.assertEqual(cfg["models"]["cursor_generate"], "grok-4.7-medium")
        self.assertEqual(cfg["models"]["author"], "claude-opus")

    def test_invalid_json_raises_config_error(self):
        project = make_project()
        write(project, ".wow/config.json", "{nope")
        with self.assertRaises(config.ConfigError):
            config.load_config(project)


class DotenvTest(unittest.TestCase):
    def test_parses_export_quotes_and_comments(self):
        text = '# c\nexport A="1"\nB=\'two\'\nC=3=4\n\n'
        self.assertEqual(config.parse_dotenv(text), {"A": "1", "B": "two", "C": "3=4"})


class CredentialsTest(unittest.TestCase):
    def test_shell_environment_wins(self):
        project = make_project()
        write(project, ".env.local", "IC_JIRA_BASE_URL=https://file.example\n")
        env = {"IC_JIRA_BASE_URL": "https://shell.example", "IC_JIRA_USER_EMAIL": "a@b.c",
               "IC_JIRA_API_TOKEN": SECRET}
        creds = config.resolve_jira_credentials(project, env)
        self.assertEqual(creds.base_url, "https://shell.example")
        self.assertEqual(creds.child_mode, "parent")

    def test_env_local_then_spec_kit_fallback_per_key(self):
        project = make_project()
        write(project, ".env.local", "IC_JIRA_USER_EMAIL=local@b.c\nIC_JIRA_PROJECT_KEY=IRIS\n")
        write(project, ".spec-kit/.env", f"JIRA_BASE_URL=https://sk.example\nJIRA_EMAIL=sk@b.c\nJIRA_API_TOKEN={SECRET}\n")
        creds = config.resolve_jira_credentials(project, {})
        self.assertEqual((creds.base_url, creds.email, creds.project_key),
                         ("https://sk.example", "local@b.c", "IRIS"))
        self.assertEqual(creds.token, SECRET)

    def test_missing_required_returns_none(self):
        self.assertIsNone(config.resolve_jira_credentials(make_project(), {"IC_JIRA_BASE_URL": "x"}))

    def test_repr_never_contains_token(self):
        env = {"IC_JIRA_BASE_URL": "https://x", "IC_JIRA_USER_EMAIL": "a@b.c", "IC_JIRA_API_TOKEN": SECRET}
        creds = config.resolve_jira_credentials(make_project(), env)
        self.assertNotIn(SECRET, repr(creds))
        self.assertNotIn(SECRET, str(creds))


if __name__ == "__main__":
    unittest.main()
