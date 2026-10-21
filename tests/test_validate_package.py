"""Black-box checks for the public package validation command."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
