"""Black-box checks for the public package validation command."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = PACKAGE_ROOT / "scripts" / "validate_package.py"


class ValidatePackageTests(unittest.TestCase):
    def run_validator(self, package_root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(package_root / "scripts" / "validate_package.py")],
            check=False,
            capture_output=True,
            text=True,
        )

    def copy_package(self, destination: Path) -> Path:
        copied_root = destination / "autopilot-anything"
        shutil.copytree(PACKAGE_ROOT, copied_root)
        return copied_root

    def test_complete_package_passes_public_cli(self) -> None:
        result = self.run_validator(PACKAGE_ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_route_fails_with_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            package_root = self.copy_package(Path(temporary_directory))
            (package_root / "references" / "routes" / "general.md").unlink()

            result = self.run_validator(package_root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("references/routes/general.md", result.stderr)

    def test_unconnected_route_fails_even_when_all_files_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            package_root = self.copy_package(Path(temporary_directory))
            route_index = package_root / "references" / "route-index.md"
            route_index.write_text(
                route_index.read_text(encoding="utf-8").replace(
                    "[General work](routes/general.md)", "General work"
                ),
                encoding="utf-8",
            )

            result = self.run_validator(package_root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("routes/general.md", result.stderr)

    def test_broken_relative_link_in_guide_fails_with_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            package_root = self.copy_package(Path(temporary_directory))
            guide = package_root / "platforms" / "codex.md"
            guide.write_text(
                guide.read_text(encoding="utf-8") + "\n[Missing](../missing.md)\n",
                encoding="utf-8",
            )

            result = self.run_validator(package_root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("platforms/codex.md", result.stderr)
        self.assertIn("../missing.md", result.stderr)

    def test_missing_public_release_files_fail_with_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            package_root = self.copy_package(Path(temporary_directory))
            for relative_path in ("README.md", "README.ru.md", "LICENSE", "ATTRIBUTION.md"):
                (package_root / relative_path).unlink()

            result = self.run_validator(package_root)

        self.assertNotEqual(result.returncode, 0)
        for relative_path in ("README.md", "README.ru.md", "LICENSE", "ATTRIBUTION.md"):
            self.assertIn(relative_path, result.stderr)

    def test_incomplete_mit_license_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            package_root = self.copy_package(Path(temporary_directory))
            (package_root / "LICENSE").write_text(
                "MIT License\n\nCopyright (c) 2026 Nick Vels\n",
                encoding="utf-8",
            )

            result = self.run_validator(package_root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("LICENSE", result.stderr)

    def test_complete_mit_license_allows_appended_notice(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            package_root = self.copy_package(Path(temporary_directory))
            license_file = package_root / "LICENSE"
            license_file.write_text(
                license_file.read_text(encoding="utf-8")
                + "\n\nAdditional distributor notice.\n",
                encoding="utf-8",
            )

            result = self.run_validator(package_root)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_modified_mit_terms_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            package_root = self.copy_package(Path(temporary_directory))
            license_file = package_root / "LICENSE"
            license_file.write_text(
                license_file.read_text(encoding="utf-8").replace(
                    "free of charge", "not free of charge", 1
                ),
                encoding="utf-8",
            )

            result = self.run_validator(package_root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("LICENSE", result.stderr)

    def test_attribution_must_describe_derivative_and_upstream(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            package_root = self.copy_package(Path(temporary_directory))
            (package_root / "ATTRIBUTION.md").write_text(
                "# Attribution\n\nNick Vels is named in the LICENSE.\n",
                encoding="utf-8",
            )

            result = self.run_validator(package_root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ATTRIBUTION.md", result.stderr)

    def test_attribution_that_negates_derivative_status_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            package_root = self.copy_package(Path(temporary_directory))
            attribution = package_root / "ATTRIBUTION.md"
            attribution.write_text(
                attribution.read_text(encoding="utf-8")
                + "\nThis package is not a derivative.\n",
                encoding="utf-8",
            )

            result = self.run_validator(package_root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ATTRIBUTION.md", result.stderr)

    def test_private_autopilot_material_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            package_root = self.copy_package(Path(temporary_directory))
            private_directory = package_root / ".autopilot"
            private_directory.mkdir()
            (private_directory / "session.md").write_text("private build notes\n", encoding="utf-8")

            result = self.run_validator(package_root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(".autopilot", result.stderr)

    def test_secret_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            package_root = self.copy_package(Path(temporary_directory))
            (package_root / ".env").write_text("API_KEY=placeholder\n", encoding="utf-8")

            result = self.run_validator(package_root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(".env", result.stderr)

    def test_secret_like_token_in_regular_file_fails_without_echoing_value(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            package_root = self.copy_package(Path(temporary_directory))
            fake_token = "ghp_" + ("A" * 36)
            private_text = package_root / "release-notes.md"
            private_text.write_text(f"Credential accidentally included: {fake_token}\n", encoding="utf-8")

            result = self.run_validator(package_root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("release-notes.md", result.stderr)
        self.assertNotIn(fake_token, result.stderr)

    def test_aws_secret_assignment_in_regular_file_fails_without_echoing_value(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            package_root = self.copy_package(Path(temporary_directory))
            fake_secret = "not-a-real-secret-marker"
            release_notes = package_root / "release-notes.txt"
            release_notes.write_text(
                f"{'AWS_SECRET_' + 'ACCESS_KEY'}={fake_secret}\n", encoding="utf-8"
            )

            result = self.run_validator(package_root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("release-notes.txt", result.stderr)
        self.assertIn("Secret-like", result.stderr)
        self.assertNotIn(fake_secret, result.stderr)

    def test_skill_name_must_match_package_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            package_root = self.copy_package(Path(temporary_directory))
            skill = package_root / "SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "name: autopilot-anything", "name: another-skill", 1
                ),
                encoding="utf-8",
            )

            result = self.run_validator(package_root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("autopilot-anything", result.stderr)

    def test_dashboard_lifecycle_files_are_required(self) -> None:
        required_dashboard_files = (
            "dashboard.html",
            "scripts/dashboard.py",
            "references/dashboard.md",
            "tests/test_dashboard.py",
            "tests/test_dashboard_ui.py",
            "platforms/codex.md",
            "platforms/claude-code.md",
            "platforms/cursor.md",
        )
        for relative_path in required_dashboard_files:
            with self.subTest(relative_path=relative_path), tempfile.TemporaryDirectory() as temporary_directory:
                package_root = self.copy_package(Path(temporary_directory))
                target = package_root / relative_path
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("placeholder\n", encoding="utf-8")
                target.unlink()

                result = self.run_validator(package_root)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(relative_path, result.stderr)

    def test_installed_package_template_drives_live_page_and_snapshot_after_event_eviction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temp_root = Path(temporary_directory)
            package_root = self.copy_package(temp_root)
            dashboard_path = package_root / "scripts" / "dashboard.py"
            module_spec = importlib.util.spec_from_file_location("dashboard_installed_copy", dashboard_path)
            self.assertIsNotNone(module_spec)
            self.assertIsNotNone(module_spec.loader)
            installed_dashboard = importlib.util.module_from_spec(module_spec)
            sys.modules[module_spec.name] = installed_dashboard
            try:
                module_spec.loader.exec_module(installed_dashboard)
                packaged_template = (package_root / "dashboard.html").read_text(encoding="utf-8")
                self.assertEqual(installed_dashboard.DEFAULT_TEMPLATE, packaged_template)
                self.assertEqual(installed_dashboard.DASHBOARD_TEMPLATE_PATH, (package_root / "dashboard.html").resolve())
                default_state = installed_dashboard.create_run_state("default-settings")
                self.assertEqual(default_state["mode"], "semi")
                self.assertEqual(default_state["depth"], "normal")
                init_defaults = installed_dashboard.build_parser().parse_args(["init", "--project-root", str(temp_root)])
                self.assertEqual(init_defaults.mode, "semi")
                self.assertEqual(init_defaults.depth, "normal")

                project_root = temp_root / "user-project"
                state = installed_dashboard.create_run_state("integration-run", timestamp="2026-01-01T00:00:00Z")
                state = installed_dashboard.apply_event(state, {
                    "type": "stage", "id": "execution", "label": "Create deliverable", "status": "active",
                    "timestamp": "2026-01-01T00:02:00Z",
                })
                for _ in range(205):
                    state = installed_dashboard.apply_event(state, {
                        "type": "note", "text": "Progress update", "timestamp": "2026-01-01T00:03:00Z",
                    })
                self.assertFalse(any(event["type"] == "stage" for event in state["events"]))
                installed_dashboard.save_run(project_root, "integration-run", state)

                server = installed_dashboard.DashboardServer(project_root, "integration-run", port=0)
                server_thread = threading.Thread(target=server.serve_forever, daemon=True)
                server_thread.start()
                try:
                    host, port = server.server_address[:2]
                    with urllib.request.urlopen(f"http://{host}:{port}/", timeout=2) as response:
                        live_page = response.read().decode("utf-8")
                    with urllib.request.urlopen(f"http://{host}:{port}/state.json", timeout=2) as response:
                        live_state = json.loads(response.read().decode("utf-8"))

                    snapshot_path = temp_root / "snapshot.html"
                    result = installed_dashboard.main([
                        "snapshot", "--project-root", str(project_root), "--run-id", "integration-run",
                        "--output", str(snapshot_path),
                    ])
                    self.assertEqual(result, 0)
                    snapshot_page = snapshot_path.read_text(encoding="utf-8")
                finally:
                    server.shutdown()
                    server.server_close()
                    server_thread.join(timeout=2)
            finally:
                sys.modules.pop(module_spec.name, None)

        embedded_match = re.search(
            r'<script\s+id="initial-state"\s+type="application/json">(.*?)</script>', live_page, re.DOTALL,
        )
        self.assertIsNotNone(embedded_match)
        embedded_state = json.loads(embedded_match.group(1))
        self.assertEqual(live_page, snapshot_page)
        self.assertEqual(live_state["revision"], embedded_state["revision"])
        self.assertEqual(live_state["current_stage_started_at"], "2026-01-01T00:02:00Z")
        self.assertEqual(embedded_state["current_stage_started_at"], live_state["current_stage_started_at"])
        self.assertIn("state.current_stage_started_at", live_page)


if __name__ == "__main__":
    unittest.main()
