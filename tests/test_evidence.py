from __future__ import annotations

import json
import unittest

from helpers import make_project, write
import config
import evidence


class PbStatusTest(unittest.TestCase):
    def test_reads_audit_details_and_missing_docs(self):
        project = make_project()
        write(project, "wow/pb/chats/prd.md", "llega al 100%\n")
        write(project, "wow/pb/chats/prd.audit.json", json.dumps({
            "verdict": "changes_required", "completion_pct": 100, "inventions": [{"term": "x"}],
            "missing_anchors": ["AC2"], "open_questions": ["q1", "q2"]}))
        write(project, "wow/pb/chats/rfc.md", "draft\n")
        write(project, "wow/pb/chats/rfc.audit.json", "{bad")
        out = evidence.pb_status(project, ["E1"])
        self.assertEqual(list(out), ["prd", "rfc", "epic-E1"])
        self.assertEqual(out["prd"], {"present": True, "closed": True, "audit": "changes_required",
                                      "completion_pct": 100, "inventions": 1, "missing_anchors": 1,
                                      "open_questions": 2, "packet_pct": None, "packet_errors": None})
        self.assertEqual(out["rfc"]["audit"], "unknown")
        self.assertIsNone(out["rfc"]["inventions"])
        self.assertEqual(out["epic-E1"], {"present": False, "closed": False, "audit": None, "completion_pct": None,
                                          "inventions": None, "missing_anchors": None, "open_questions": None,
                                          "packet_pct": None, "packet_errors": None})


class ReviewSummariesTest(unittest.TestCase):
    def test_summaries_sorted_and_corrupt_skipped(self):
        project = make_project()
        write(project, "wow/reviews/plan.json", json.dumps({
            "ref": "plan", "anchor_set": "readiness", "final": "approved",
            "rounds": [{"n": 1, "verdict": "CHANGES_REQUIRED", "blockers": [{"anchor": "R1"}]},
                       {"n": 2, "verdict": "APPROVED", "blockers": []}]}))
        write(project, "wow/reviews/IRIS-41.json", json.dumps({
            "ref": "IRIS-41", "anchor_set": "story", "final": "approved",
            "rounds": [{"n": 1, "verdict": "APPROVED", "blockers": []}]}))
        write(project, "wow/reviews/broken.json", "{bad")
        self.assertEqual(evidence.review_summaries(project), [
            {"ref": "IRIS-41", "anchor_set": "story", "rounds": 1, "final": "approved", "first_pass": True,
             "blockers": 0},
            {"ref": "plan", "anchor_set": "readiness", "rounds": 2, "final": "approved", "first_pass": False,
             "blockers": 1}])
        self.assertEqual(evidence.review_summaries(make_project()), [])


class PricingTest(unittest.TestCase):
    def test_defaults_and_configured_table(self):
        self.assertEqual(evidence.pricing(config.DEFAULTS), {"as_of": None, "per_mtok": {}})
        cfg = {"pricing": {"as_of": "2026-09-01", "per_mtok": {"m": {"in": 1}}}}
        self.assertEqual(evidence.pricing(cfg), {"as_of": "2026-09-01", "per_mtok": {"m": {"in": 1}}})


class PacketPctTest(unittest.TestCase):
    def test_packet_pct(self):
        import pbtemplate
        project = make_project()
        write(project, "wow/pb/prd.md", pbtemplate.load("prd"))
        out = evidence.pb_status(project, [])
        self.assertEqual((out["prd"]["packet_pct"], out["rfc"]["packet_pct"]), (0, None))


if __name__ == "__main__":
    unittest.main()
