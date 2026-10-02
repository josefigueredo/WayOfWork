from __future__ import annotations

import unittest

from helpers import ROOT
import pbtemplate


class TemplateTest(unittest.TestCase):
    def test_prd_fields_groups_units(self):
        scalars, groups = pbtemplate.units("prd")
        self.assertEqual(len(pbtemplate.fields(pbtemplate.load("prd"))), 123)
        self.assertEqual(sorted(groups), ["assumption", "dependency", "health_kpi", "in_scope", "kpi", "nfr",
                                          "out_scope", "risk", "secondary_kpi"])
        self.assertEqual(len(scalars) + len(groups), 49)
        self.assertIn("open_questions", scalars)

    def test_rfc_fields_groups_units(self):
        scalars, groups = pbtemplate.units("rfc")
        self.assertEqual(sorted(groups), ["api", "component", "dependency", "goal", "milestone", "non_goal",
                                          "repo", "risk"])
        self.assertEqual(groups["api"]["index_type"], "alpha")
        self.assertEqual(len(scalars) + len(groups), 35)

    def test_single_brace_and_unknown_kind(self):
        self.assertEqual(pbtemplate.fields("{a} {{b}} {{ a }}"), ["a", "b"])
        with self.assertRaises(ValueError):
            pbtemplate.load("epic")

    def test_vendored_templates_match_reference_when_present(self):
        source = ROOT / "reference/product-brain/upstream/base-templates.ts"
        if not source.is_file():
            self.skipTest("reference/product-brain/upstream is not present (run refresh.sh)")
        text = source.read_text(encoding="utf-8")
        self.assertEqual(pbtemplate.extract_upstream(text, "PRD_TEMPLATE_CONTENT"), pbtemplate.load("prd"))
        self.assertEqual(pbtemplate.extract_upstream(text, "RFC_TEMPLATE_CONTENT"), pbtemplate.load("rfc"))


if __name__ == "__main__":
    unittest.main()
