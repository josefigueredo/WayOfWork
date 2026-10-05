"""wow jira fix-fields and the Jira component lint: what Product Brain's export leaves wrong on the stories.

Measured on PLATE-504 (IRIS pilot): the stories arrived with the epic's labels, no component, no story points and the
epic's priority. PB copies the epic labels and priority to every story (jira.exporter.ts:551-616), drops everything
but the labels when Jira rejects a component that does not exist (jira.client.ts:1236-1276), and looks for story
points in the first float field of the instance ("Valor del Riesgo" there; jira.client.ts:1342-1348).
"""
from __future__ import annotations

import os
import unittest
from unittest import mock

from helpers import make_project, run_cli
import jirafields
import manifest
from test_manifest import valid_doc


def _doc(key="IRIS-40"):
    doc = valid_doc()
    doc["epics"][0]["tasks"][0].update(component="BE", estimate=3, priority="high", labels=["backend"])
    doc["epics"][0]["tasks"][1].update(component="DEVOPS", estimate=2, priority="low", labels=["ci"])
    if key:
        doc["plan"]["export"]["epics"] = {"E1": key}
    return doc


# As Product Brain left them: epic labels, no component, no points, the epic's priority.
STORIES = [
    {"key": "IRIS-41", "summary": "[BE] Model", "components": [], "labels": ["backend", "ci"], "priority": "Medium"},
    {"key": "IRIS-42", "summary": "[DEVOPS] API", "components": [], "labels": ["backend", "ci"], "priority": "Medium"},
]
# customfield_1 comes first and is a float, like "Valor del Riesgo": PB's discovery picks it; the edit screen does not
# carry it, so it is not a story points field for these issues.
EDITMETA = {"summary": "Summary", "customfield_10016": "Story point estimate", "customfield_10050": "Story Points"}


class FakeJira:
    def __init__(self, components=("be", "mfe"), stories=STORIES):
        self.components = list(components)
        self.stories = [dict(s) for s in stories]
        self.updates = []

    def project_components(self, project_key):
        return self.components

    def stories_of(self, epic_key):
        return self.stories

    def edit_fields(self, key):
        return EDITMETA

    def priority_names(self):
        return ["Highest", "High", "Medium", "Low", "Lowest"]

    def update(self, key, fields):
        self.updates.append((key, fields))


class PointsFieldTest(unittest.TestCase):
    def test_picks_a_story_points_field_on_the_edit_screen_by_name_never_any_float(self):
        self.assertEqual(jirafields.points_field({"customfield_1": "Valor del Riesgo", **EDITMETA}),
                         "customfield_10016")
        self.assertEqual(jirafields.points_field({"customfield_10050": "Story Points"}), "customfield_10050")
        self.assertIsNone(jirafields.points_field({"customfield_1": "Valor del Riesgo"}))


class ComponentLintTest(unittest.TestCase):
    def test_components_missing_in_the_jira_project_are_findings(self):
        findings = jirafields.component_findings(_doc(), ["be", "mfe"], "IRIS")
        self.assertEqual(len(findings), 1)
        self.assertIn("1.2: component DEVOPS is not in Jira project IRIS (be, mfe)", findings[0])
        self.assertIn("Omitir en los issues", findings[0])

    def test_project_key_comes_from_the_export_or_the_credentials(self):
        self.assertEqual(jirafields.project_key(_doc("PLATE-504"), None), "PLATE")
        self.assertEqual(jirafields.project_key(_doc(None), "IRIS"), "IRIS")
        self.assertIsNone(jirafields.project_key(_doc(None), None))


class PlanTest(unittest.TestCase):
    def test_plan_restores_component_points_priority_and_labels_from_the_manifest(self):
        project = make_project()
        manifest.save(project, _doc())
        result = jirafields.plan(project, "E1", FakeJira())
        self.assertEqual(result["key"], "IRIS-40")
        self.assertEqual(result["blockers"], [])
        first, second = result["changes"]
        self.assertEqual(first["key"], "IRIS-41")
        self.assertEqual(first["fields"], {"components": [{"name": "be"}], "customfield_10016": 3,
                                           "priority": {"name": "High"}, "labels": ["backend"]})
        # DEVOPS does not exist in the project: WoW never invents a component, it says so and fixes the rest.
        self.assertNotIn("components", second["fields"])
        self.assertEqual(second["fields"]["priority"], {"name": "Low"})
        self.assertIn("component DEVOPS is not in IRIS", second["skipped"][0])

    def test_unmatched_stories_and_missing_export_are_reported(self):
        project = make_project()
        manifest.save(project, _doc(None))
        self.assertIn("E1 is not exported to Jira", jirafields.plan(project, "E1", FakeJira())["blockers"][0])
        manifest.save(project, _doc())
        stories = [dict(STORIES[0], summary="[BE] Something else")]
        result = jirafields.plan(project, "E1", FakeJira(stories=stories))
        self.assertEqual(result["changes"], [])
        self.assertIn("IRIS-41", result["unmatched"][0])

    def test_already_right_fields_are_not_rewritten(self):
        project = make_project()
        manifest.save(project, _doc())
        right = [dict(STORIES[0], components=["be"], labels=["backend"], priority="High", points=3)]
        result = jirafields.plan(project, "E1", FakeJira(stories=right))
        self.assertEqual(result["changes"], [])

    def test_apply_writes_each_change(self):
        project = make_project()
        manifest.save(project, _doc())
        jira = FakeJira()
        result = jirafields.plan(project, "E1", jira)
        self.assertEqual(jirafields.apply(result, jira), [])
        self.assertEqual([key for key, _ in jira.updates], ["IRIS-41", "IRIS-42"])


class CliTest(unittest.TestCase):
    def test_fix_fields_without_credentials_cannot_evaluate(self):
        project = make_project()
        manifest.save(project, _doc())
        with mock.patch.dict(os.environ, {}, clear=True):
            code, _, err = run_cli(["jira", "fix-fields", "--epic", "E1", "--project", str(project)])
        self.assertEqual(code, 2)
        self.assertIn("Jira credentials not found", err)


if __name__ == "__main__":
    unittest.main()
