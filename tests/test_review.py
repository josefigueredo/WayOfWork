from __future__ import annotations

import unittest

from helpers import make_project, write
import review

OUTPUT = """Some preface the model added.
VERDICT: CHANGES_REQUIRED
BLOCKER AC1 src/api.py:42 — returns 500 instead of 404 for a missing id
BLOCKER AC9 src/api.py:50 - not an existing anchor
WARNING src/api.py:10 – long function
NIT — rename variable x
"""


class ParseTest(unittest.TestCase):
    def test_parses_all_kinds_and_separators(self):
        parsed = review.parse_verdict(OUTPUT)
        self.assertEqual(parsed["verdict"], "CHANGES_REQUIRED")
        self.assertEqual(parsed["blockers"], [
            {"anchor": "AC1", "path_line": "src/api.py:42", "text": "returns 500 instead of 404 for a missing id"},
            {"anchor": "AC9", "path_line": "src/api.py:50", "text": "not an existing anchor"},
        ])
        self.assertEqual(parsed["warnings"], [{"path_line": "src/api.py:10", "text": "long function"}])
        self.assertEqual(parsed["nits"], ["rename variable x"])

    def test_missing_verdict(self):
        self.assertIsNone(review.parse_verdict("looks fine to me")["verdict"])

    def test_markdown_around_the_keywords_is_ignored(self):
        # Measured on 2026-10-13: cursor-agent answered "**VERDICT: APPROVED**" and the round counted as unparseable.
        for line in ("**VERDICT: APPROVED**", "**VERDICT:** APPROVED", "## VERDICT: APPROVED", "> VERDICT: APPROVED",
                     "`VERDICT: APPROVED`", "__VERDICT: APPROVED__"):
            self.assertEqual(review.parse_verdict(line)["verdict"], "APPROVED", line)
        parsed = review.parse_verdict("**VERDICT: CHANGES_REQUIRED**\n"
                                      "- **BLOCKER** `AC1` `src/api.py:42` — returns **500**\n"
                                      "* **WARNING** src/api.py:10 – long function\n"
                                      "1. **NIT** — rename `x`\n")
        self.assertEqual(parsed["verdict"], "CHANGES_REQUIRED")
        self.assertEqual(parsed["blockers"], [{"anchor": "AC1", "path_line": "src/api.py:42", "text": "returns **500**"}])
        self.assertEqual(parsed["warnings"], [{"path_line": "src/api.py:10", "text": "long function"}])
        self.assertEqual(parsed["nits"], ["rename `x`"])

    def test_markup_inside_a_finding_is_kept_verbatim(self):
        # Only the wrapper around the keyword goes: dunders and globs in paths and text are real.
        parsed = review.parse_verdict("VERDICT: CHANGES_REQUIRED\n"
                                      "**BLOCKER** AC1 wow/sources/__init__.py:3 — `__init__` imports **/*.py eagerly\n"
                                      "WARNING src/__main__.py:1 — runs on import\n")
        self.assertEqual(parsed["blockers"], [{"anchor": "AC1", "path_line": "wow/sources/__init__.py:3",
                                               "text": "`__init__` imports **/*.py eagerly"}])
        self.assertEqual(parsed["warnings"], [{"path_line": "src/__main__.py:1", "text": "runs on import"}])

    def test_a_keyword_in_the_middle_of_prose_is_still_not_a_verdict(self):
        self.assertIsNone(review.parse_verdict("I would say **VERDICT: APPROVED** here")["verdict"])


class RoundsTest(unittest.TestCase):
    def test_unknown_anchor_is_downgraded_and_round_recorded(self):
        summary = review.record_round(review.new_summary("IRIS-41", "story"),
                                      review.parse_verdict(OUTPUT), {"AC1", "AC2"}, "h1")
        rnd = summary["rounds"][0]
        self.assertEqual((rnd["n"], rnd["verdict"], rnd["diff_hash"]), (1, "CHANGES_REQUIRED", "h1"))
        self.assertEqual([b["anchor"] for b in rnd["blockers"]], ["AC1"])
        self.assertTrue(rnd["warnings"][-1]["text"].startswith("[downgraded: unknown anchor AC9] "))
        self.assertIsNone(summary["final"])

    def test_zero_valid_blockers_approves_even_if_model_said_changes(self):
        text = "VERDICT: CHANGES_REQUIRED\nBLOCKER AC9 a.py:1 — prose only\n"
        summary = review.record_round(review.new_summary("IRIS-41", "story"), review.parse_verdict(text), {"AC1"}, "h")
        self.assertEqual(summary["rounds"][0]["verdict"], "APPROVED")
        self.assertEqual(summary["final"], "approved")

    def test_unparseable_output_raises(self):
        with self.assertRaises(review.ReviewOutputError):
            review.record_round(review.new_summary("x", "story"), review.parse_verdict("hello"), set(), "h")

    def test_third_round_with_blocker_escalates_to_hitl(self):
        summary = review.new_summary("IRIS-41", "story")
        blocked = review.parse_verdict("VERDICT: CHANGES_REQUIRED\nBLOCKER AC1 a.py:1 — still broken\n")
        for n in range(3):
            summary = review.record_round(summary, blocked, {"AC1"}, f"h{n}")
        self.assertEqual(summary["final"], "hitl")
        self.assertEqual(review.next_action(summary, "h9"), "hitl")

    def test_human_decision_only_after_hitl_records_who_and_why(self):
        summary = review.new_summary("IRIS-41", "story")
        blocked = review.parse_verdict("VERDICT: CHANGES_REQUIRED\nBLOCKER AC1 a.py:1 — still broken\n")
        with self.assertRaises(ValueError):  # no HITL yet: a human decision cannot skip the reviewer
            review.decide(summary, "approved", "looks fine", "ana", "2026-10-02T22:00:00Z")
        for n in range(3):
            summary = review.record_round(summary, blocked, {"AC1"}, f"h{n}")
        with self.assertRaises(ValueError):
            review.decide(summary, "approved", "  ", "ana", "2026-10-02T22:00:00Z")
        approved = review.decide(summary, "approved", "AC1 is conditional and did not fire", "ana", "2026-10-02T22:00:00Z")
        self.assertEqual(approved["final"], "approved_by_human")
        self.assertEqual(approved["decision"], {"by": "human", "author": "ana", "verdict": "approved",
                                                "reason": "AC1 is conditional and did not fire",
                                                "at": "2026-10-02T22:00:00Z"})
        self.assertEqual(len(approved["rounds"]), 3)  # the reviewer's rounds stay on record
        self.assertEqual(review.next_action(approved, "h2"), "done")  # the human decided on the last round's content
        rejected = review.decide(summary, "rejected", "needs a semantic audit", "ana", "2026-10-02T22:00:00Z")
        self.assertEqual((rejected["final"], review.next_action(rejected, "h2")), ("rejected_by_human", "rejected"))

    def test_an_approval_covers_only_the_content_it_saw(self):
        approved = review.record_round(review.new_summary("facts", "claims"), review.parse_verdict("VERDICT: APPROVED\n"),
                                       {"C1"}, "h1")
        self.assertEqual(review.next_action(approved, "h1"), "done")
        self.assertEqual(review.next_action(approved, "h2"), "run")  # the doc changed after approval
        reopened = review.reopen_if_stale(approved, "h2")
        self.assertIsNone(reopened["final"])
        self.assertEqual(reopened["closed_cycles"][0]["final"], "approved")
        self.assertIs(review.reopen_if_stale(approved, "h1"), approved)
        blocked = review.parse_verdict("VERDICT: CHANGES_REQUIRED\nBLOCKER C1 f.md:1 — wrong\n")
        summary = review.record_round(reopened, blocked, {"C1"}, "h2")
        summary = review.record_round(summary, blocked, {"C1"}, "h3")
        self.assertIsNone(summary["final"])  # round 3 overall, but only the 2nd of the new cycle
        summary = review.record_round(summary, blocked, {"C1"}, "h4")
        self.assertEqual(summary["final"], "hitl")
        self.assertEqual([r["n"] for r in summary["rounds"]], [1, 2, 3, 4])

    def test_a_human_decision_reopens_when_the_content_changes(self):
        summary = review.new_summary("IRIS-41", "story")
        blocked = review.parse_verdict("VERDICT: CHANGES_REQUIRED\nBLOCKER AC1 a.py:1 — x\n")
        for n in range(3):
            summary = review.record_round(summary, blocked, {"AC1"}, f"h{n}")
        rejected = review.decide(summary, "rejected", "fix the audit", "ana", "2026-10-04T16:00:00Z")
        self.assertEqual(review.next_action(rejected, "h9"), "run")
        self.assertEqual(review.reopen_if_stale(rejected, "h9")["closed_cycles"][0]["decision"]["verdict"], "rejected")

    def test_next_action_rules(self):
        empty = review.new_summary("IRIS-41", "story")
        self.assertEqual(review.next_action(empty, "h1"), "run")
        blocked = review.record_round(empty, review.parse_verdict("VERDICT: CHANGES_REQUIRED\nBLOCKER AC1 a:1 — x\n"),
                                      {"AC1"}, "h1")
        self.assertEqual(review.next_action(blocked, "h1"), "wait_for_changes")
        self.assertEqual(review.next_action(blocked, "h2"), "run")
        approved = review.record_round(empty, review.parse_verdict("VERDICT: APPROVED\n"), {"AC1"}, "h1")
        self.assertEqual(review.next_action(approved, "h1"), "done")

    def test_summary_round_trip_and_invalid_file(self):
        project = make_project()
        summary = review.record_round(review.new_summary("E1", "epic"), review.parse_verdict("VERDICT: APPROVED\n"),
                                      {"E1.C1"}, "h")
        review.save_summary(project, summary)
        self.assertEqual(review.load_summary(project, "E1", "epic")["final"], "approved")
        write(project, "wow/reviews/E2.json", "{bad")
        self.assertEqual(review.load_summary(project, "E2", "epic"), review.new_summary("E2", "epic"))


class RefSafetyTest(unittest.TestCase):
    def test_unsafe_refs_are_rejected(self):
        project = make_project()
        for bad in ("../escape", "a/b", "..", "", "x\\y"):
            with self.assertRaises(ValueError):
                review.save_summary(project, review.new_summary(bad, "story"))
        for good in ("IRIS-41", "E1", "plan", "facts.v2"):
            self.assertTrue(review.safe_ref(good))


if __name__ == "__main__":
    unittest.main()
