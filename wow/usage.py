"""LLM usage collectors (spec 7.3). Records hold numbers and metadata only, never content."""
from __future__ import annotations

import json
import re
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

RECORD_KEYS = ["ts", "vendor", "tool", "model", "tokens_in", "tokens_out", "cache_read", "cache_write",
               "reasoning_out", "duration_ms", "scope", "ref", "source"]
_FRACTION_RE = re.compile(r"\.(\d+)")


def claude_slug(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def parse_ts(text: str) -> datetime:
    value = text.replace("Z", "+00:00")
    value = _FRACTION_RE.sub(lambda m: "." + (m.group(1) + "000000")[:6], value, count=1)
    return datetime.fromisoformat(value)


def _ms(start: Optional[str], end: str) -> Optional[int]:
    if not start:
        return None
    return int(round((parse_ts(end) - parse_ts(start)).total_seconds() * 1000))


def _record(**values) -> dict:
    record = {key: None for key in RECORD_KEYS}
    record.update(values)
    return record


def _lines(path: Path):
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            yield json.loads(raw)
        except json.JSONDecodeError:
            continue


def claude_records(root: Path, project: Path) -> List[dict]:
    folder = root / claude_slug(project)  # Claude Code names the folder after the path as typed, not resolved
    by_id: Dict[str, dict] = {}
    for path in sorted(folder.glob("*.jsonl")) if folder.is_dir() else []:
        last_user: Optional[str] = None
        for row in _lines(path):
            if row.get("type") == "user":
                last_user = row.get("timestamp") or last_user
                continue
            message = row.get("message") if isinstance(row.get("message"), dict) else {}
            if row.get("type") != "assistant" or not message.get("usage"):
                continue
            used = message["usage"]
            key = message.get("id") or f"{path.name}:{row.get('timestamp')}"
            by_id[key] = _record(
                ts=row.get("timestamp"), vendor="anthropic", tool="claude-code", model=message.get("model"),
                tokens_in=used.get("input_tokens"), tokens_out=used.get("output_tokens"),
                cache_read=used.get("cache_read_input_tokens"), cache_write=used.get("cache_creation_input_tokens"),
                duration_ms=_ms(last_user, row["timestamp"]) if row.get("timestamp") else None,
                scope="message", source="claude-transcript")
    return list(by_id.values())


def _inside(child: str, parent: Path) -> bool:
    try:
        Path(child).resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def codex_records(root: Path, project: Path) -> List[dict]:
    records: List[dict] = []
    for path in sorted(root.rglob("*.jsonl")) if root.is_dir() else []:
        rows = list(_lines(path))
        meta = next((r for r in rows if r.get("type") == "session_meta"), None)
        if not meta or not _inside((meta.get("payload") or {}).get("cwd", ""), project):
            continue
        model, total, start = None, {}, {}
        for row in rows:
            payload = row.get("payload") or {}
            kind = payload.get("type")
            if row.get("type") == "turn_context":
                model = payload.get("model") or model
            elif kind == "token_count" and payload.get("info"):
                total = payload["info"].get("total_token_usage") or total
            elif kind == "task_started":
                start = dict(total)
            elif kind == "task_complete":
                delta = {k: total.get(k, 0) - start.get(k, 0) for k in total}
                records.append(_record(
                    ts=row.get("timestamp"), vendor="openai", tool="codex", model=model,
                    tokens_in=delta.get("input_tokens"), tokens_out=delta.get("output_tokens"),
                    cache_read=delta.get("cached_input_tokens"), reasoning_out=delta.get("reasoning_output_tokens"),
                    duration_ms=payload.get("duration_ms"), scope="turn", source="codex-session"))
    return records


def cursor_records(project: Path) -> List[dict]:
    records: List[dict] = []
    for path in sorted((project / "harness" / "runs").glob("*.json")):
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        result = run.get("result") or {}
        used = result.get("usage") or {}
        records.append(_record(
            ts=run.get("ended_at"), vendor="cursor", tool="cursor-agent", model=run.get("model"),
            tokens_in=used.get("inputTokens"), tokens_out=used.get("outputTokens"),
            cache_read=used.get("cacheReadTokens"), cache_write=used.get("cacheWriteTokens"),
            duration_ms=result.get("duration_ms"), scope="task", ref=run.get("ref"), source="cursor-run"))
    return records


def cursor_turn_records(project: Path) -> List[dict]:
    """Cursor IDE agent turns the `wow hook cursor-stop` hook kept in the project (one JSON line per turn)."""
    records: List[dict] = []
    for path in sorted((project / "harness" / "cursor-turns").glob("*.jsonl")):
        for turn in _lines(path):
            if not isinstance(turn, dict):
                continue
            records.append(_record(
                ts=turn.get("ts"), vendor="cursor", tool="cursor-ide", model=turn.get("model_id") or turn.get("model"),
                tokens_in=turn.get("input_tokens"), tokens_out=turn.get("output_tokens"),
                cache_read=turn.get("cache_read_tokens"), cache_write=turn.get("cache_write_tokens"),
                scope="turn", ref=turn.get("conversation_id"), source="cursor-hook"))
    return records


_REVIEWER_VENDOR = {"codex": "openai", "copilot": "github"}


def review_records(project: Path) -> List[dict]:
    """Rounds `wow review` recorded in the project (codex runs --ephemeral, so its session log never exists)."""
    records: List[dict] = []
    for path in sorted((project / "harness" / "reviews").glob("*.json")):
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        used = run.get("usage") or {}
        reviewer = run.get("reviewer")
        records.append(_record(
            ts=run.get("ts"), vendor=_REVIEWER_VENDOR.get(reviewer, reviewer), tool=reviewer, model=run.get("model"),
            tokens_in=used.get("input_tokens"), tokens_out=used.get("output_tokens"),
            cache_read=used.get("cached_input_tokens"), reasoning_out=used.get("reasoning_output_tokens"),
            scope="review", ref=run.get("ref"), source="wow-review"))
    return records


def collect(project: Path, cfg: dict, claude_root: Optional[Path] = None, codex_root: Optional[Path] = None) -> List[dict]:
    roots = cfg.get("usage") or {}
    claude_root = claude_root or Path(roots.get("claude_root", Path.home() / ".claude" / "projects")).expanduser()
    codex_root = codex_root or Path(roots.get("codex_root", Path.home() / ".codex" / "sessions")).expanduser()
    records = (claude_records(claude_root, project) + codex_records(codex_root, project) + cursor_records(project)
               + cursor_turn_records(project) + review_records(project))
    return sorted(records, key=lambda r: r["ts"] or "")


def summarize(records: List[dict]) -> List[dict]:
    groups: Dict[tuple, List[dict]] = {}
    for record in records:
        groups.setdefault((record["vendor"], record["model"]), []).append(record)
    rows = []
    for (vendor, model), items in sorted(groups.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
        durations = [r["duration_ms"] for r in items if r["duration_ms"] is not None]
        rows.append({"vendor": vendor, "model": model, "count": len(items),
                     "tokens_in": sum(r["tokens_in"] or 0 for r in items),
                     "tokens_out": sum(r["tokens_out"] or 0 for r in items),
                     "median_ms": int(statistics.median(durations)) if durations else None})
    return rows
