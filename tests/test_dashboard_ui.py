import copy
import datetime
import json
import os
import re
import shutil
import sys
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import dashboard


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = PACKAGE_ROOT / "dashboard.html"


class DashboardMarkup(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.buttons = []
        self.script_sources = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.add(attributes["id"])
        if tag == "button":
            self.buttons.append(attributes)
        if tag == "script" and attributes.get("src"):
            self.script_sources.append(attributes["src"])
        if tag == "link" and attributes.get("href"):
            self.links.append(attributes["href"])


def embedded_state(page):
    match = re.search(
        r'<script\s+id="initial-state"\s+type="application/json">(.*?)</script>',
        page,
        re.DOTALL,
    )
    if not match:
        raise AssertionError("rendered page must contain its initial snapshot")
    return json.loads(match.group(1))


NODE_DOM_HARNESS = r'''const vm = require('node:vm');
class Element {
  constructor(tag='div') {
    this.tagName = tag.toUpperCase(); this.children = []; this.attributes = {}; this.className = '';
    this._text = ''; this.hidden = false; this.style = {}; this.dataset = {}; this.options = [];
    this.listeners = {}; this.classList = {
      add: name => { const set = new Set(this.className.split(/\s+/).filter(Boolean)); set.add(name); this.className = [...set].join(' '); },
      remove: name => { this.className = this.className.split(/\s+/).filter(item => item && item !== name).join(' '); }
    };
  }
  set textContent(value) { this._text = value == null ? '' : String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
  get childNodes() { return this.children; }
  appendChild(child) { this.children.push(child); return child; }
  replaceChildren(...children) { this._text = ''; this.children = children; }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  getAttribute(key) { return this.attributes[key] || null; }
  removeAttribute(key) { delete this.attributes[key]; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  querySelector(selector) {
    if (selector.startsWith('.')) {
      const wanted = selector.slice(1);
      for (const child of this.children) {
        if (child.className.split(/\s+/).includes(wanted)) return child;
        const found = child.querySelector(selector); if (found) return found;
      }
    }
    return null;
  }
}
const state = JSON.parse(process.env.RUN_STATE);
const frozenNow = Date.parse(process.env.FIXED_NOW);
class FixedDate extends Date {
  constructor(...args) { if (args.length) super(...args); else super(frozenNow); }
  static now() { return frozenNow; }
}
const elements = new Map();
const get = id => { if (!elements.has(id)) { const element = new Element(); element.id = id; elements.set(id, element); } return elements.get(id); };
const actions = new Map(['refresh','language','theme'].map(action => { const button = new Element('button'); button.setAttribute('data-action', action); return [action, button]; }));
get('initial-state').textContent = JSON.stringify(state);
get('requirement-search').value = '';
get('requirement-filter').value = 'all';
get('requirement-filter').options = ['allRequirements','openRequirements','closedRequirements'].map(key => { const option = new Element('option'); option.setAttribute('data-i18n', key); return option; });
const document = {
  documentElement: new Element('html'), body: new Element('body'),
  getElementById: get,
  createElement: tag => new Element(tag),
  createTextNode: value => { const item = new Element('#text'); item.textContent = value; return item; },
  querySelector: selector => {
    const match = selector.match(/^\[data-action="(refresh|language|theme)"\]$/);
    if (match) return actions.get(match[1]);
    return null;
  },
  querySelectorAll: () => []
};
const context = {
  document, window: {setInterval: () => 0},
  Date: FixedDate,
  localStorage: {getItem: () => null, setItem: () => {}},
  fetch: async () => ({ok:true, json:async () => state}),
  console
};
vm.runInNewContext(process.env.DASHBOARD_SCRIPT, context);
setImmediate(() => {
  const ids = ['title','run-id','run-status','checkpoint','progress-label','stages','gates','requirements','work-items','checks','artifacts','activity','waiting-panel','waiting-reason','completion-panel','completion-status','completion-summary','connection'];
  const output = Object.fromEntries(ids.map(id => { const element = get(id); return [id, {text:element.textContent, hidden:element.hidden, className:element.className}]; }));
  console.log(JSON.stringify(output));
});
'''


class DashboardUITests(unittest.TestCase):
    def read_template(self):
        self.assertTrue(DASHBOARD_PATH.is_file(), "dashboard.html must ship in the package")
        return DASHBOARD_PATH.read_text(encoding="utf-8")

    def assert_tokens(self, template, *tokens):
        missing = [token for token in tokens if token not in template]
        self.assertFalse(missing, "dashboard is missing UI contract tokens: %r" % missing)

    def assert_absent(self, template, *tokens):
        present = [token for token in tokens if token in template]
        self.assertFalse(present, "dashboard contains forbidden UI tokens: %r" % present)

    def render_visible_ui(self, state):
        if not shutil.which("node"):
            self.skipTest("Node is optional; skip the executable DOM smoke when absent")
        template = self.read_template()
        rendered = dashboard.render_snapshot(template, state)
        scripts = re.findall(r"<script>(.*?)</script>", rendered, re.DOTALL)
        self.assertEqual(len(scripts), 1, "snapshot should have one executable UI script")
        result = subprocess.run(
            [shutil.which("node"), "-e", NODE_DOM_HARNESS],
            env={**os.environ, "RUN_STATE": json.dumps(state), "DASHBOARD_SCRIPT": scripts[0], "FIXED_NOW": state["updated_at"]},
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def active_state_without_start_event(self):
        now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        run_started = (now - datetime.timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        stage_started = (now - datetime.timedelta(minutes=9)).isoformat().replace("+00:00", "Z")
        state = dashboard.create_run_state("visible-run", title="Research brief", timestamp=run_started)
        state["updated_at"] = now.isoformat().replace("+00:00", "Z")
        state["current_stage_started_at"] = stage_started
        state["stages"][0].update({"label":"Evidence review", "status":"active"})
        state["checkpoint"] = {"stage":"brief", "label":"Evidence review", "status":"active"}
        state["events"] = []  # The bounded log no longer contains the stage-start event.
        state["requirements"] = [{"id":"R01", "text":"Use primary sources", "status":"satisfied"}]
        state["work_items"] = [{"id":"W01", "title":"Gather evidence", "status":"active", "artifact":"research/findings.md"}]
        state["checks"] = [{"id":"C01", "check_type":"Citation review", "status":"passed", "result":"Links verified"}]
        return state, now, datetime.datetime.fromisoformat(stage_started.replace("Z", "+00:00"))

    def test_template_renders_an_empty_run_from_an_embedded_snapshot(self):
        template = self.read_template()
        state = dashboard.create_run_state("empty-run", timestamp="2026-01-02T03:04:05Z")

        rendered = dashboard.render_snapshot(template, state)
        parsed = DashboardMarkup()
        parsed.feed(rendered)

        self.assertEqual(embedded_state(rendered), state)
        for element_id in (
            "title", "run-status", "run-settings", "progress", "stages", "gates",
            "requirements", "work-items", "checks", "artifacts", "activity", "connection",
        ):
            with self.subTest(element_id=element_id):
                self.assertIn(element_id, parsed.ids)
        self.assertNotIn("{{STATE_JSON}}", rendered)

    def test_active_waiting_and_completed_states_keep_the_tracker_shape(self):
        template = self.read_template()
        state = dashboard.create_run_state("state-run", timestamp="2026-01-02T03:04:05Z")
        state = dashboard.apply_event(state, {
            "type": "requirement", "id": "R01", "status": "in-progress",
            "text": "Check the primary source", "source": "Brief",
        })
        state = dashboard.apply_event(state, {
            "type": "item", "id": "W01", "status": "active", "title": "Gather evidence",
            "owner": "research", "artifact": "research/findings.md", "requirement_ids": ["R01"],
        })
        state = dashboard.apply_event(state, {
            "type": "check", "id": "C01", "status": "not-run", "check_type": "citation review",
            "reason": "Waiting for sources",
        })
        active_page = dashboard.render_snapshot(template, state)
        self.assertEqual(embedded_state(active_page), state)
        self.assertIn("work_items", embedded_state(active_page))
        self.assertIn("checks", embedded_state(active_page))

        state = dashboard.apply_event(state, {
            "type": "wait", "reason": "Choose the citation style", "timestamp": "2026-01-02T03:05:05Z",
        })
        waiting_page = dashboard.render_snapshot(template, state)
        waiting_snapshot = embedded_state(waiting_page)
        self.assertEqual(waiting_snapshot["status"], "waiting")
        self.assertIsNone(waiting_snapshot["waiting_intervals"][-1]["ended_at"])
        self.assertIn("waiting_intervals", waiting_snapshot)

        state = dashboard.apply_event(state, {
            "type": "answered", "note": "APA", "timestamp": "2026-01-02T03:10:05Z",
        })
        state = dashboard.apply_event(state, {
            "type": "check", "id": "C01", "status": "passed", "check_type": "citation review",
            "result": "Every claim links to a source",
        })
        state = dashboard.apply_event(state, {
            "type": "item", "id": "W01", "status": "completed", "title": "Gather evidence",
            "artifact": "research/findings.md",
        })
        state = dashboard.apply_event(state, {
            "type": "finish", "summary": "Research package is ready", "timestamp": "2026-01-02T03:11:05Z",
        })
        completed_page = dashboard.render_snapshot(template, state)
        self.assertEqual(embedded_state(completed_page)["status"], "completed")
        self.assertEqual(embedded_state(completed_page)["completion_summary"], "Research package is ready")
        self.assertEqual(embedded_state(completed_page)["checks"][0]["status"], "passed")

    def test_active_waiting_and_completed_states_render_as_visible_ui(self):
        state, now, stage_started = self.active_state_without_start_event()
        active_ui = self.render_visible_ui(state)
        self.assertEqual(active_ui["title"]["text"], "Research brief")
        self.assertEqual(active_ui["run-status"]["text"], "Active")
        self.assertIn("Evidence review", active_ui["stages"]["text"])
        self.assertIn("Active for 9m", active_ui["stages"]["text"])
        self.assertIn("Use primary sources", active_ui["requirements"]["text"])
        self.assertIn("Gather evidence", active_ui["work-items"]["text"])
        self.assertIn("Citation review", active_ui["checks"]["text"])
        self.assertIn("research/findings.md", active_ui["artifacts"]["text"])

        waiting = copy.deepcopy(state)
        wait_start = (stage_started + datetime.timedelta(minutes=4)).isoformat().replace("+00:00", "Z")
        waiting.update({
            "status":"waiting",
            "checkpoint":{"stage":"brief", "label":"Evidence review", "status":"waiting"},
            "waiting_intervals":[{"reason":"Choose the citation style", "started_at":wait_start, "ended_at":None, "duration_seconds":0}],
        })
        waiting_ui = self.render_visible_ui(waiting)
        self.assertEqual(waiting_ui["run-status"]["text"], "Waiting")
        self.assertFalse(waiting_ui["waiting-panel"]["hidden"])
        self.assertIn("Choose the citation style", waiting_ui["waiting-reason"]["text"])
        self.assertIn("Active for 4m", waiting_ui["stages"]["text"])

        completed = copy.deepcopy(state)
        completed.update({"status":"completed", "completed_at":now.isoformat().replace("+00:00", "Z"), "completion_summary":"Research package is ready"})
        completed["stages"][0]["status"] = "completed"
        completed_ui = self.render_visible_ui(completed)
        self.assertEqual(completed_ui["run-status"]["text"], "Completed")
        self.assertFalse(completed_ui["completion-panel"]["hidden"])
        self.assertEqual(completed_ui["completion-summary"]["text"], "Research package is ready")

    def test_active_stage_duration_is_unavailable_without_a_persisted_or_logged_start(self):
        state, _, _ = self.active_state_without_start_event()
        state.pop("current_stage_started_at")
        rendered = self.render_visible_ui(state)
        self.assertIn("Duration unavailable", rendered["stages"]["text"])
        self.assertNotIn("Active for", rendered["stages"]["text"])

    def test_untrusted_text_stays_in_json_and_never_enters_html_sinks(self):
        template = self.read_template()
        hostile = '</script><img src=x onerror="alert(1)"><script>alert(2)</script>'
        state = dashboard.create_run_state("safe-run", title=hostile)
        state = dashboard.apply_event(state, {
            "type": "requirement", "id": "R01", "status": "pending", "text": hostile,
        })
        state = dashboard.apply_event(state, {
            "type": "item", "id": "W01", "status": "pending", "title": hostile,
            "artifact": "outputs/safe.txt",
        })
        state = dashboard.apply_event(state, {
            "type": "check", "id": "C01", "status": "failed", "check_type": "HTML review",
            "result": hostile,
        })
        rendered = dashboard.render_snapshot(template, state)
        self.assert_tokens(rendered, "\\u003c/script\\u003e")
        self.assertNotIn(hostile, rendered)
        self.assert_absent(template, "innerHTML")
        self.assert_tokens(template, "textContent", "createElement")

    def test_refresh_and_preferences_are_observation_only(self):
        template = self.read_template()
        parsed = DashboardMarkup()
        parsed.feed(template)

        button_actions = [button.get("data-action") for button in parsed.buttons]
        self.assertEqual(set(button_actions), {"refresh", "language", "theme"})
        self.assertTrue(all(button.get("type") == "button" for button in parsed.buttons))
        self.assert_absent(template.lower(), "<form", "method: 'post'", "/stop")
        self.assert_tokens(template, "fetch('/state.json'", "cache: 'no-store'", "setInterval")

    def test_locales_theme_narrow_layout_and_reduced_motion_are_included(self):
        template = self.read_template()
        parser = DashboardMarkup()
        parser.feed(template)

        self.assertFalse(any(source.startswith(("http:", "https:")) for source in parser.script_sources))
        self.assertFalse(any(href.startswith(("http:", "https:")) for href in parser.links))
        for token in ("data-lang=\"en\"", "ru: {", "en: {", "setAttribute('data-lang', language)", "localStorage", "prefers-reduced-motion", "prefers-color-scheme", "max-width: 440px"):
            with self.subTest(token=token):
                self.assertIn(token, template)
        self.assert_tokens(template, "aria-live", "aria-label")

    def test_connection_failure_and_old_state_are_visible(self):
        template = self.read_template()
        self.assert_tokens(template, "disconnected", "stale", "lastState", "Snapshot", "Live")

    def test_stage_duration_and_universal_artifacts_are_rendered(self):
        template = self.read_template()
        self.assert_tokens(template, "stageDuration", "artifact", "acceptance_checks", "work_items", "requirements", "checks")
        self.assert_absent(template.lower(), "commit count", "test count")


if __name__ == "__main__":
    unittest.main()
