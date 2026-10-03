from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest

from helpers import ROOT

HTML = ROOT / "dashboard" / "wow-dashboard.html"
EXAMPLES = ROOT / "dashboard" / "examples"
NODE = shutil.which("node")
_FORBIDDEN = ["fetch(", "XMLHttpRequest", "WebSocket", "EventSource", "sendBeacon", "<link", "@import",
              'src="http', "src='http", "url(http", "url('http", 'url("http']


def html_text() -> str:
    return HTML.read_text(encoding="utf-8")


def script(sid: str) -> str:
    match = re.search(rf'<script id="{sid}">(.*?)</script>', html_text(), re.S)
    if match is None:
        raise AssertionError(f"script #{sid} not found")
    return match.group(1)


def run_node(js: str) -> subprocess.CompletedProcess:
    return subprocess.run([NODE, "--input-type=commonjs", "-"], input=js, capture_output=True, text=True,
                          timeout=60)


class StaticTest(unittest.TestCase):
    def test_csp_blocks_network(self):
        text = html_text()
        csp = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)"', text)
        self.assertIsNotNone(csp)
        for directive in ("default-src 'none'", "connect-src 'none'", "form-action 'none'", "base-uri 'none'"):
            self.assertIn(directive, csp.group(1))

    def test_no_network_apis_or_remote_resources(self):
        text = html_text()
        for needle in _FORBIDDEN:
            self.assertNotIn(needle, text, needle)

    def test_english_only(self):
        self.assertIsNone(re.search(r"[áéíóúñÁÉÍÓÚÑ¿¡]", html_text()))


@unittest.skipIf(NODE is None, "node is not installed")
class CoreTest(unittest.TestCase):
    def test_core_functions(self):
        js = script("wow-core") + r"""
const assert = require("assert");
const C = WowCore;
const R = (o) => Object.assign({ts: "t", vendor: "anthropic", tool: "claude-code", model: "m1", tokens_in: null,
  tokens_out: null, cache_read: null, cache_write: null, reasoning_out: null, duration_ms: null,
  scope: "message", ref: null, source: "x"}, o);

assert.deepStrictEqual(C.validate([]).ok, false);
const v2 = C.validate({schema_version: 2, current: {}, history: [], usage: []});
assert.strictEqual(v2.ok, true);
assert.ok(v2.warnings[0].includes("schema_version"));
assert.deepStrictEqual(C.validate({schema_version: 1, current: {}}).warnings, ['missing "history"', 'missing "usage"']);

assert.deepStrictEqual([C.phaseState(5, 3), C.phaseState(5, 5), C.phaseState(5, 6), C.phaseState("unknown", 3)],
  ["done", "current", "todo", "unknown"]);

assert.strictEqual(C.sumOrNull([null, undefined]), null);
assert.strictEqual(C.sumOrNull([null, 2, 3]), 5);
assert.strictEqual(C.median([100, 300]), 200);
assert.strictEqual(C.median([100, 201]), 150);
assert.strictEqual(C.quantile([100, 200, 300], 0.95), 300);
assert.strictEqual(C.median([]), null);

const rows = C.usageByModel([R({tokens_in: 10, duration_ms: 100}), R({tokens_in: 5, duration_ms: 300}),
  R({duration_ms: 200}), R({vendor: "cursor", tool: "cursor-agent", model: "composer", tokens_out: 7})]);
assert.deepStrictEqual(rows.map(r => [r.vendor, r.model, r.count, r.pool]),
  [["anthropic", "m1", 3, "own"], ["cursor", "composer", 1, "cursor"]]);
assert.strictEqual(rows[0].tokens_in, 15);
assert.strictEqual(rows[0].cache_read, null);
assert.deepStrictEqual([rows[0].median_ms, rows[0].p95_ms], [200, 300]);
assert.strictEqual(rows[1].median_ms, null);

const pools = C.poolTotals([R({tokens_in: 4}), R({vendor: "cursor", tokens_out: 6})]);
assert.deepStrictEqual([pools.own.tokens_in, pools.own.tokens_out, pools.cursor.tokens_out], [4, null, 6]);

assert.deepStrictEqual([C.refEpic("E1/WU-8"), C.refEpic("plan"), C.refEpic(null)], ["E1", "plan", null]);
assert.deepStrictEqual(C.usageByEpic([R({ref: "E1/WU-8", tokens_in: 3}), R({vendor: "cursor", ref: "E1/WU-9",
  tokens_out: 2}), R({tokens_in: 1})]), [{epic: "E1", own: 3, cursor: 2}, {epic: "unattributed", own: 1, cursor: null}]);

assert.strictEqual(C.estimateCost([R({tokens_in: 1})], {as_of: null, per_mtok: {}}).available, false);
const cost = C.estimateCost([R({tokens_in: 1000000, tokens_out: 1000000}), R({model: "zzz", tokens_in: 5})],
  {as_of: "2026-09-01", per_mtok: {m1: {in: 3, out: 15}}});
assert.deepStrictEqual([cost.available, cost.as_of, cost.priced, cost.unpriced, cost.byPool.own], [true, "2026-09-01", 1, 1, 18]);

const blind = C.estimateCost([R({}), R({vendor: "cursor", model: "c1", tokens_in: 2000000})],
  {as_of: "x", per_mtok: {m1: {in: 3}, c1: {in: 1}}});
assert.deepStrictEqual([blind.priced, blind.unpriced, blind.byPool.own, blind.byPool.cursor], [1, 1, null, 2]);
assert.strictEqual(C.weekStart("2026-09-10T10:00:00Z"), "2026-09-07");
assert.strictEqual(C.weekStart("nope"), null);
assert.deepStrictEqual(C.weeklyThroughput([{ts: "2026-09-08T10:00:00Z", tasks_done: 0},
  {ts: "2026-09-10T10:00:00Z", tasks_done: 2}, {ts: "2026-09-16T10:00:00Z", tasks_done: 5},
  {ts: "2026-09-23T10:00:00Z", tasks_done: 4}]), [{week: "2026-09-14", done: 3}, {week: "2026-09-21", done: 0}]);

assert.deepStrictEqual(C.burnup([{ts: "a", epics: {E1: {done: 1, total: 4}}}, {ts: "b", epics: {}},
  {ts: "c", epics: {E1: {done: 3, total: 5}}}], "E1"), [{ts: "a", done: 1, total: 4}, {ts: "c", done: 3, total: 5}]);

const q = C.quality([{ref: "a", rounds: 1, final: "approved", first_pass: true},
  {ref: "b", rounds: 3, final: "hitl", first_pass: false}, {ref: "c", rounds: 1, final: null, first_pass: false}]);
assert.deepStrictEqual([q.total, q.decided, q.firstPassRate, q.hitl], [3, 2, 0.5, 1]);
assert.strictEqual(C.quality([]).firstPassRate, null);
const h = C.quality([{ref: "d", rounds: 3, final: "approved_by_human", first_pass: false},
  {ref: "e", rounds: 3, final: "rejected_by_human", first_pass: false}]);
assert.deepStrictEqual([h.decided, h.hitl, h.firstPassRate], [2, 2, 0]);
console.log("core ok");
"""
        proc = run_node(js)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("core ok", proc.stdout)


class ExamplesTest(unittest.TestCase):
    def test_examples_validate_against_progress_schema(self):
        import schema
        for name in ("empty.json", "partial.json", "full.json"):
            doc = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
            self.assertEqual(schema.validate(doc, schema.load_schema("progress")), [], name)


@unittest.skipIf(NODE is None, "node is not installed")
class RenderTest(unittest.TestCase):
    def test_render_examples_and_hostile_input(self):
        js = script("wow-core") + script("wow-render") + r"""
const assert = require("assert");
const fs = require("fs");
const R = WowRender;
const EX = %s;
const ex = (n) => JSON.parse(fs.readFileSync(EX + "/" + n, "utf8"));
const panels = (html) => (html.match(/<section class="panel/g) || []).length;

for (const n of ["empty.json", "partial.json", "full.json"]) {
  const out = R.renderDoc({name: n, doc: ex(n)});
  assert.strictEqual(panels(out.html), 7, n);
  assert.strictEqual(out.warnings, "", n);
  assert.strictEqual(R.renderAll(ex(n)).length, 7, n);
}
const empty = R.renderDoc({name: "e", doc: ex("empty.json")}).html;
assert.ok(empty.includes("No data"));
assert.ok(empty.includes("build the context pack"));
const partial = R.renderDoc({name: "p", doc: ex("partial.json")}).html;
assert.ok(partial.includes("jira: HTTP 401"));
assert.ok(partial.includes("run wow snapshot again"));
const full = R.renderDoc({name: "f", doc: ex("full.json")}).html;
for (const needle of ["E3", "estimated", "2026-09-01 (example values)", "Cursor", "EX-43", "checks failing",
                      'href="https://github.com/example/backend-example/pull/9"', "data-copy=", "HITL", "Packet (predicted)"]) {
  assert.ok(full.includes(needle), needle);
}

const evil = ex("full.json");
evil.current.epics[0].title = "<img src=x onerror=alert(1)>";
evil.current.epics[0].jira_url = "javascript:alert(1)";
evil.current.epics[0].links.jira = "javascript:alert(1)";
evil.current.epics[0].links.prs[0].url = "javascript:alert(2)";
const bad = R.renderDoc({name: "evil", doc: evil}).html;
assert.ok(!bad.includes("<img src=x"));
assert.ok(bad.includes("&lt;img src=x"));
assert.ok(!/href="javascript:/i.test(bad));

const v2 = R.renderDoc({name: "v2.json", doc: Object.assign(ex("empty.json"), {schema_version: 2})});
assert.ok(v2.warnings.includes("schema_version"));
assert.strictEqual(panels(v2.html), 7);
const broken = R.renderDoc({name: "bad.json", doc: null, error: "not valid JSON"});
assert.strictEqual(broken.html, "");
assert.ok(broken.warnings.includes("not valid JSON"));
assert.ok(R.renderDoc({name: "x.json", doc: {schema_version: 1}}).warnings.includes('missing &quot;current&quot;'));

const port = R.portfolio([{name: "a.json", doc: ex("full.json")}, {name: "b.json", doc: null, error: "not valid JSON"}], 0);
assert.ok(port.includes("Portfolio (2 files)"));
assert.ok(port.includes('data-select="1"'));
assert.ok(port.includes("not valid JSON"));
const ownUnpriced = ex("full.json");
ownUnpriced.current.pricing.per_mtok = {"composer-2.5": {in: 1.25, out: 10}};
const ou = R.renderDoc({name: "ou", doc: ownUnpriced}).html;
assert.ok(ou.includes("cost: no data"), "pool without priced records shows no data, not $0.00");
assert.ok(!ou.includes("$0.00 estimated"));
const svgs = full.match(/<svg [^>]*>/g) || [];
assert.ok(svgs.length >= 4);
assert.ok(svgs.every((s) => / width="\d+"/.test(s)), "every svg declares its nominal width");
console.log("render ok");
""" % json.dumps(str(EXAMPLES))
        proc = run_node(js)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("render ok", proc.stdout)


class AppStaticTest(unittest.TestCase):
    def test_app_wiring_and_theme_tokens(self):
        app = script("wow-app")
        for needle in ("dragover", "drop", "data-select", "data-copy", "textContent", "wow-theme", "window.print"):
            self.assertIn(needle, app, needle)
        self.assertNotIn("innerHTML = entry", app)
        text = html_text()
        for needle in ('@media (prefers-color-scheme: dark)', ':root[data-theme="dark"]', "@media print",
                       "repeating-linear-gradient(45deg", "#1baf7a", "#199e70", "forced-colors"):
            self.assertIn(needle, text, needle)

    def test_embedded_snapshots_load_without_a_drop(self):
        self.assertIn('<script type="application/json" id="wow-embedded">[]</script>', html_text())
        self.assertIn('getElementById("wow-embedded")', script("wow-app"))


class EmbedTest(unittest.TestCase):
    def test_embed_inlines_snapshots_and_cannot_close_the_script(self):
        import sys
        sys.path.insert(0, str(ROOT / "wow"))
        import standalone
        hostile = {"plan": {"id": "p1", "title": "</script><img src=x onerror=alert(1)>"}}
        out = standalone.embed(html_text(), [("site/progress.json", hostile)])
        block = re.search(r'<script type="application/json" id="wow-embedded">(.*?)</script>', out, re.S).group(1)
        self.assertNotIn("</script", block)
        self.assertEqual(json.loads(block), [{"name": "site/progress.json", "doc": hostile}])
        self.assertEqual(out.count('id="wow-embedded"'), 1)
        self.assertIn("Content-Security-Policy", out)  # the offline CSP travels with the file


if __name__ == "__main__":
    unittest.main()
