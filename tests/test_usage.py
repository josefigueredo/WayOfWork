from __future__ import annotations

import json
import unittest
from pathlib import Path

from helpers import make_project, write
import usage


def jl(*rows):
    return "\n".join(json.dumps(r) for r in rows) + "\n"


class ClaudeTest(unittest.TestCase):
    def test_dedupes_split_message_and_measures_response_time(self):
        project, root = make_project(), make_project()
        slug = usage.claude_slug(project)
        u = {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 7}
        write(root, f"{slug}/s1.jsonl", jl(
            {"type": "user", "timestamp": "2026-10-01T10:00:00.000Z", "message": {"role": "user"}},
            {"type": "assistant", "timestamp": "2026-10-01T10:00:02.500Z",
             "message": {"id": "m1", "model": "claude-opus-5-5", "usage": u}},
            {"type": "assistant", "timestamp": "2026-10-01T10:00:03.000Z",
             "message": {"id": "m1", "model": "claude-opus-5-5", "usage": u}},
        ))
        [rec] = usage.claude_records(root, project)
        self.assertEqual((rec["vendor"], rec["model"], rec["tokens_in"], rec["tokens_out"]),
                         ("anthropic", "claude-opus-5-5", 10, 5))
        self.assertEqual((rec["cache_read"], rec["cache_write"], rec["reasoning_out"]), (100, 7, None))
        self.assertEqual(rec["duration_ms"], 3000)
        self.assertEqual(sorted(rec), sorted(usage.RECORD_KEYS))

    def test_other_projects_are_ignored(self):
        root = make_project()
        write(root, "-Other-project/s.jsonl", jl({"type": "assistant", "timestamp": "2026-10-01T10:00:00Z",
                                                   "message": {"id": "x", "model": "m", "usage": {}}}))
        self.assertEqual(usage.claude_records(root, make_project()), [])

    def test_slug(self):
        self.assertEqual(usage.claude_slug(Path("/Users/josefigueredo/CurrentCode/SPECKIT")),
                         "-Users-josefigueredo-CurrentCode-SPECKIT")


class CodexTest(unittest.TestCase):
    def test_turn_delta_ignores_repeated_token_counts(self):
        project, root = make_project(), make_project()

        def tc(inp, out, reason):
            return {"type": "event_msg", "timestamp": "2026-10-01T10:00:01Z", "payload": {
                "type": "token_count", "info": {"total_token_usage": {
                    "input_tokens": inp, "cached_input_tokens": 0, "output_tokens": out,
                    "reasoning_output_tokens": reason, "total_tokens": inp + out}}}}

        write(root, "2026/10/01/rollout.jsonl", jl(
            {"type": "session_meta", "timestamp": "2026-10-01T10:00:00Z", "payload": {"cwd": str(project / "sub")}},
            {"type": "turn_context", "timestamp": "2026-10-01T10:00:00Z", "payload": {"model": "gpt-5.3-codex"}},
            tc(100, 10, 4),
            {"type": "event_msg", "timestamp": "2026-10-01T10:00:00Z", "payload": {"type": "task_started"}},
            tc(300, 30, 9),
            tc(300, 30, 9),
            {"type": "event_msg", "timestamp": "2026-10-01T10:00:05Z",
             "payload": {"type": "task_complete", "duration_ms": 4200}},
        ))
        [rec] = usage.codex_records(root, project)
        self.assertEqual((rec["vendor"], rec["tool"], rec["model"]), ("openai", "codex", "gpt-5.3-codex"))
        self.assertEqual((rec["tokens_in"], rec["tokens_out"], rec["reasoning_out"]), (200, 20, 5))
        self.assertEqual((rec["duration_ms"], rec["scope"]), (4200, "turn"))

    def test_sessions_outside_project_are_ignored(self):
        root = make_project()
        write(root, "s.jsonl", jl({"type": "session_meta", "timestamp": "2026-10-01T10:00:00Z",
                                   "payload": {"cwd": "/somewhere/else"}}))
        self.assertEqual(usage.codex_records(root, make_project()), [])


class CursorAndSummaryTest(unittest.TestCase):
    def test_cursor_runs_and_summary(self):
        project = make_project()
        write(project, "harness/runs/WU-001-1.json", json.dumps({
            "schema_version": 1, "work_unit": "WU-001", "ref": "E1/WU-001", "model": "composer-2.5",
            "started_at": "2026-10-01T10:00:00Z", "ended_at": "2026-10-01T10:01:00Z", "exit_code": 0,
            "result": {"duration_ms": 60000, "usage": {"inputTokens": 1000, "outputTokens": 50,
                                                       "cacheReadTokens": 800, "cacheWriteTokens": 0}}}))
        write(project, "harness/runs/WU-002-1.json", json.dumps({
            "schema_version": 1, "work_unit": "WU-002", "ref": "WU-002", "model": "composer-2.5",
            "started_at": "2026-10-01T11:00:00Z", "ended_at": "2026-10-01T11:00:10Z", "exit_code": 1, "result": None}))
        records = usage.cursor_records(project)
        self.assertEqual([r["ref"] for r in records], ["E1/WU-001", "WU-002"])
        self.assertEqual((records[0]["tokens_in"], records[0]["duration_ms"]), (1000, 60000))
        self.assertIsNone(records[1]["tokens_in"])
        [row] = usage.summarize(records)
        self.assertEqual(row, {"vendor": "cursor", "model": "composer-2.5", "count": 2,
                               "tokens_in": 1000, "tokens_out": 50, "median_ms": 60000})

    def test_review_runs_are_usage_records(self):
        project = make_project()
        write(project, "harness/reviews/20261002T220000Z-PLATE-492-r1.json", json.dumps({
            "schema_version": 1, "ts": "2026-10-02T22:00:00Z", "ref": "PLATE-492", "set": "story", "round": 1,
            "reviewer": "codex", "model": "gpt-6-luna",
            "usage": {"input_tokens": 16425, "cached_input_tokens": 7936, "output_tokens": 5, "reasoning_output_tokens": 2}}))
        [record] = usage.review_records(project)
        self.assertEqual((record["vendor"], record["tool"], record["model"], record["scope"], record["ref"]),
                         ("openai", "codex", "gpt-6-luna", "review", "PLATE-492"))
        self.assertEqual((record["tokens_in"], record["tokens_out"], record["cache_read"], record["reasoning_out"]),
                         (16425, 5, 7936, 2))
        self.assertIn(record, usage.collect(project, {"usage": {"claude_root": str(project / "c"),
                                                                "codex_root": str(project / "x")}}))

    def test_parse_ts_variants(self):
        self.assertEqual(usage.parse_ts("2026-10-01T10:00:00.1234567Z").microsecond, 123456)
        self.assertEqual(usage.parse_ts("2026-10-01T10:00:00Z").second, 0)


if __name__ == "__main__":
    unittest.main()
