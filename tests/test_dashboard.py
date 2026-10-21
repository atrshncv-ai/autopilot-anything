import contextlib
import io
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import dashboard


class DashboardTrackerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_cli(self, *args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = dashboard.main([*map(str, args)])
        return result, stdout.getvalue(), stderr.getvalue()

    def test_init_creates_isolated_runs_and_resume_reuses_id(self):
        result, _, _ = self.run_cli(
            "init", "--project-root", self.project_root, "--run-id", "run-a",
            "--title", "Research", "--mode", "semi", "--depth", "deep",
            "--complexity", "complex", "--risk", "high",
        )
        self.assertEqual(result, 0)
        first = dashboard.load_run(self.project_root, "run-a")
        self.assertEqual(first["mode"], "semi")
        self.assertEqual(first["depth"], "deep")
        self.assertEqual(first["complexity"], "complex")
        self.assertEqual(first["risk"], "high")
        self.assertEqual(first["revision"], 0)
        self.assertEqual(set(first["gates"]), {"G1", "G2", "G3", "G4"})

        self.run_cli("init", "--project-root", self.project_root, "--run-id", "run-b")
        second = dashboard.load_run(self.project_root, "run-b")
        self.assertNotEqual(first["run_id"], second["run_id"])

        result, _, _ = self.run_cli("resume", "--project-root", self.project_root, "--run-id", "run-a")
        self.assertEqual(result, 0)
        resumed = dashboard.load_run(self.project_root, "run-a")
        self.assertEqual(resumed["run_id"], "run-a")
        self.assertEqual(resumed["revision"], 1)

    def test_current_stage_start_survives_event_eviction_save_load_and_resume(self):
        state = dashboard.create_run_state("run-a", timestamp="2026-01-01T00:00:00Z")
        self.assertEqual(state["current_stage_started_at"], "2026-01-01T00:00:00Z")
        state = dashboard.apply_event(state, {
            "type": "stage", "id": "execution", "label": "Work", "status": "active",
            "timestamp": "2026-01-01T00:02:00Z",
        })
        self.assertEqual(state["current_stage_started_at"], "2026-01-01T00:02:00Z")
        state = dashboard.apply_event(state, {
            "type": "stage", "id": "execution", "label": "Work in progress", "status": "active",
            "timestamp": "2026-01-01T00:03:00Z",
        })
        self.assertEqual(state["current_stage_started_at"], "2026-01-01T00:02:00Z")

        for _ in range(205):
            state = dashboard.apply_event(state, {
                "type": "note", "text": "Routine update", "timestamp": "2026-01-01T00:04:00Z",
            })
        self.assertFalse(any(event["type"] == "stage" for event in state["events"]))
        dashboard.save_run(self.project_root, "run-a", state)
        loaded = dashboard.load_run(self.project_root, "run-a")
        self.assertEqual(loaded["current_stage_started_at"], "2026-01-01T00:02:00Z")

        resumed = dashboard.apply_event(loaded, {"type": "resume", "timestamp": "2026-01-01T00:05:00Z"})
        self.assertEqual(resumed["current_stage_started_at"], "2026-01-01T00:02:00Z")
        resumed = dashboard.apply_event(resumed, {
            "type": "stage", "id": "execution", "label": "Work", "status": "completed",
            "timestamp": "2026-01-01T00:06:00Z",
        })
        resumed = dashboard.apply_event(resumed, {
            "type": "stage", "id": "execution", "label": "Work restarted", "status": "active",
            "timestamp": "2026-01-01T00:07:00Z",
        })
        self.assertEqual(resumed["current_stage_started_at"], "2026-01-01T00:07:00Z")

    def test_events_update_requirements_items_checks_gates_and_finish(self):
        state = dashboard.create_run_state("run-a", title="Writing")
        state = dashboard.apply_event(state, {
            "type": "requirement", "id": "R01", "status": "satisfied",
            "text": "Use primary sources", "source": "Brief",
        })
        state = dashboard.apply_event(state, {
            "type": "item", "id": "W01", "status": "active", "title": "Research",
            "requirement_ids": ["R01"], "dependencies": [],
        })
        state = dashboard.apply_event(state, {
            "type": "check", "id": "C01", "status": "passed", "check_type": "source review",
            "result": "Three sources reviewed",
        })
        state = dashboard.apply_event(state, {"type": "gate", "id": "G1", "status": "passed"})
        state = dashboard.apply_event(state, {"type": "finish", "summary": "Ready"})

        self.assertEqual(state["requirements"][0]["status"], "satisfied")
        self.assertEqual(state["work_items"][0]["status"], "active")
        self.assertEqual(state["checks"][0]["status"], "passed")
        self.assertEqual(state["gates"]["G1"]["status"], "passed")
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["completion_summary"], "Ready")
        self.assertEqual(state["revision"], 5)
        self.assertEqual(len(state["events"]), 5)

    def test_invalid_ids_and_statuses_do_not_change_state(self):
        state = dashboard.create_run_state("run-a")
        before = json.dumps(state, sort_keys=True)
        for event in (
            {"type": "requirement", "id": "../escape", "status": "satisfied", "text": "x"},
            {"type": "item", "id": "W01", "status": "invented", "title": "x"},
            {"type": "gate", "id": "G9", "status": "passed"},
        ):
            with self.subTest(event=event), self.assertRaises(ValueError):
                dashboard.apply_event(state, event)
            self.assertEqual(json.dumps(state, sort_keys=True), before)

    def test_wait_interval_is_timestamped_and_excluded_from_elapsed_time(self):
        state = dashboard.create_run_state("run-a", timestamp="2026-01-01T00:00:00Z")
        state = dashboard.apply_event(state, {
            "type": "wait", "reason": "User approval", "timestamp": "2026-01-01T00:01:00Z",
        })
        self.assertEqual(state["status"], "waiting")
        self.assertEqual(state["elapsed_seconds"], 60)
        state = dashboard.apply_event(state, {
            "type": "answered", "note": "Approved", "timestamp": "2026-01-01T00:11:00Z",
        })
        self.assertEqual(state["status"], "active")
        self.assertEqual(state["elapsed_seconds"], 60)
        self.assertEqual(state["waiting_intervals"][0]["duration_seconds"], 600)
        self.assertEqual(state["waiting_intervals"][0]["ended_at"], "2026-01-01T00:11:00Z")

    def test_atomic_save_keeps_previous_state_when_replacement_fails(self):
        state = dashboard.create_run_state("run-a")
        dashboard.save_run(self.project_root, "run-a", state)
        state = dashboard.apply_event(state, {"type": "note", "text": "New note"})
        original = (self.project_root / ".autopilot/anything/run-a/state.json").read_text()
        with mock.patch.object(dashboard.os, "replace", side_effect=OSError("simulated failure")):
            with self.assertRaises(OSError):
                dashboard.save_run(self.project_root, "run-a", state)
        self.assertEqual((self.project_root / ".autopilot/anything/run-a/state.json").read_text(), original)
        self.assertEqual(dashboard.load_run(self.project_root, "run-a")["revision"], 0)

    def test_snapshot_embeds_escaped_state_without_executing_user_text(self):
        state = dashboard.create_run_state("run-a", title="</script><img src=x onerror=alert(1)>")
        state = dashboard.apply_event(state, {"type": "note", "text": "</script><script>alert(1)</script>"})
        rendered = dashboard.render_snapshot(dashboard.DEFAULT_TEMPLATE, state)
        self.assertIn("application/json", rendered)
        self.assertIn("\\u003c/script\\u003e", rendered)
        self.assertNotIn("</script><img", rendered)
        self.assertNotIn("</script><script>alert", rendered)
        self.assertNotIn("https://", rendered)

    def test_server_allows_only_loopback_read_endpoints_for_selected_run(self):
        dashboard.save_run(self.project_root, "run-a", dashboard.create_run_state("run-a", title="A"))
        dashboard.save_run(self.project_root, "run-b", dashboard.create_run_state("run-b", title="B"))
        server = dashboard.DashboardServer(self.project_root, "run-a", port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address[:2]
            self.assertIn(host, {"127.0.0.1", "::1"})

            def get(path):
                with urllib.request.urlopen(f"http://{host}:{port}{path}", timeout=2) as response:
                    return response.status, response.read().decode("utf-8")

            self.assertEqual(get("/healthz")[0], 200)
            page_status, page = get("/")
            self.assertEqual(page_status, 200)
            self.assertIn("Autopilot Anything", page)
            state_status, payload = get("/state.json")
            self.assertEqual(state_status, 200)
            self.assertEqual(json.loads(payload)["run_id"], "run-a")

            with self.assertRaises(urllib.error.HTTPError) as missing:
                get("/../run-b/state.json")
            self.assertIn(missing.exception.code, {400, 404})
            request = urllib.request.Request(
                f"http://{host}:{port}/state.json", data=b"{}", method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as forbidden:
                urllib.request.urlopen(request, timeout=2)
            self.assertEqual(forbidden.exception.code, 405)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_server_rejects_foreign_host_before_returning_page_or_state(self):
        dashboard.save_run(self.project_root, "run-a", dashboard.create_run_state("run-a", title="Private run"))
        server = dashboard.DashboardServer(self.project_root, "run-a", port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address[:2]
            for path in ("/", "/state.json"):
                request = urllib.request.Request(
                    f"http://{host}:{port}{path}", headers={"Host": f"evil.example:{port}"}, method="GET",
                )
                with self.subTest(path=path):
                    with self.assertRaises(urllib.error.HTTPError) as rejected:
                        urllib.request.urlopen(request, timeout=2)
                    self.assertEqual(rejected.exception.code, 403)
                    body = rejected.exception.read().decode("utf-8")
                    self.assertNotIn("Private run", body)
                    self.assertNotIn("run-a", body)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_cli_invalid_event_leaves_saved_state_unchanged(self):
        self.run_cli("init", "--project-root", self.project_root, "--run-id", "run-a")
        before = (self.project_root / ".autopilot/anything/run-a/state.json").read_text()
        result, _, _ = self.run_cli(
            "stage", "--project-root", self.project_root, "--run-id", "run-a",
            "--id", "brief", "--status", "made-up",
        )
        self.assertNotEqual(result, 0)
        self.assertEqual((self.project_root / ".autopilot/anything/run-a/state.json").read_text(), before)


if __name__ == "__main__":
    unittest.main()
