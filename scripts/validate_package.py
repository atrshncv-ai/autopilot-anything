#!/usr/bin/env python3
"""Validate package contents without third-party dependencies."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import unquote, urlsplit


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "autopilot-anything"
REQUIRED_ROUTES = (
    "references/routes/code.md",
    "references/routes/scientific-research.md",
    "references/routes/information-gathering.md",
    "references/routes/data-analysis.md",
    "references/routes/presentations.md",
    "references/routes/documents-and-files.md",
    "references/routes/general.md",
)
REQUIRED_PLATFORM_GUIDES = (
    "platforms/codex.md",
    "platforms/claude-code.md",
    "platforms/cursor.md",
)
REQUIRED_FILES = (
    "SKILL.md",
    "references/core-workflow.md",
    "references/safety-and-evidence.md",
    "references/route-index.md",
    *REQUIRED_ROUTES,
    *REQUIRED_PLATFORM_GUIDES,
    "README.md",
    "README.ru.md",
    "LICENSE",
    "ATTRIBUTION.md",
    "compatibility/README.md",
    "compatibility/codex.md",
    "compatibility/claude-code.md",
    "compatibility/cursor.md",
    "scripts/validate_package.py",
)
REQUIRED_SKILL_LINKS = (
    "references/core-workflow.md",
    "references/safety-and-evidence.md",
    "references/route-index.md",
)
MARKDOWN_LINK = re.compile(r"!?[\[][^\]]*\]\(\s*(?:<([^>]+)>|([^\s)]+))")
SECRET_PATTERNS = (
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "AWS access key"),
    (
        re.compile(r"\bAWS_SECRET_ACCESS_KEY\s*[:=]\s*\S+", re.IGNORECASE),
        "AWS secret access key assignment",
    ),
    (re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b"), "GitHub token"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"), "Slack token"),
    (re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"), "private key"),
    (
        re.compile(
            r"\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*['\"]?[A-Za-z0-9/+=_-]{20,}",
            re.IGNORECASE,
        ),
        "secret assignment",
    ),
)
PRIVATE_NAMES = {
    ".env",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
}
PRIVATE_SUFFIXES = {".key", ".pem", ".p12", ".pfx", ".keystore"}
MIT_LICENSE_TEXT = """MIT License

Copyright (c) 2026 Nick Vels

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""
POSITIVE_DERIVATIVE_PATTERNS = (
    re.compile(
        r"\bautopilot anything\b[^.!?]{0,120}\bis\s+(?:a|an)\s+(?:separate\s+)?"
        r"(?:adaptation|derivative work)\b[^.!?]{0,120}\bautopilot skill\b[^.!?]{0,100}\bnick vels\b"
    ),
    re.compile(
        r"\bautopilot anything\b[^.!?]{0,100}\b(?:adapts|is adapted from|is derived from|"
        r"derives from|is based on)\b[^.!?]{0,120}\b(?:nick vels[^.!?]{0,60}autopilot skill|"
        r"autopilot skill[^.!?]{0,60}nick vels)\b"
    ),
)
NEGATED_DERIVATIVE_PATTERNS = (
    re.compile(r"\b(?:no|not|never)\s+(?:(?:a|an|the)\s+)?(?:derivative(?: work)?|adaptation)\b"),
    re.compile(r"\b(?:no|not|never)\s+(?:adapted|derived)\s+from\b"),
    re.compile(r"\b(?:isn't|aren't|wasn't|weren't)\s+(?:(?:a|an|the)\s+)?(?:derivative(?: work)?|adaptation)\b"),
)


def relative_name(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def read_utf8(path: Path, root: Path, errors: List[str]) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        errors.append(f"Cannot read {relative_name(path, root)}: {error}")
        return None


def parse_frontmatter(text: str, errors: List[str]) -> Dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        errors.append("SKILL.md must start with YAML frontmatter delimited by '---'.")
        return {}

    try:
        end = lines.index("---", 1)
    except ValueError:
        errors.append("SKILL.md frontmatter has no closing '---'.")
        return {}

    metadata: Dict[str, str] = {}
    for line_number, line in enumerate(lines[1:end], start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z][A-Za-z0-9_-]*):\s*(.*?)\s*", line)
        if not match:
            errors.append(f"Unsupported frontmatter line at SKILL.md:{line_number}.")
            continue
        key, value = match.groups()
        if key in metadata:
            errors.append(f"Duplicate frontmatter key '{key}'.")
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        metadata[key] = value

    if metadata.get("name") != SKILL_NAME:
        errors.append(f"SKILL.md metadata must set name to '{SKILL_NAME}'.")
    if not metadata.get("description", "").strip():
        errors.append("SKILL.md metadata must include a non-empty description.")
    return metadata


def markdown_targets(text: str) -> List[str]:
    return [match.group(1) or match.group(2) for match in MARKDOWN_LINK.finditer(text)]


def local_link_path(
    source: Path, target: str, root: Path, errors: List[str]
) -> Optional[Path]:
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    if parsed.path.startswith("/"):
        errors.append(
            f"Markdown link in {relative_name(source, root)} must be relative: {target}"
        )
        return None

    resolved = (source.parent / unquote(parsed.path)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        errors.append(
            f"Markdown link in {relative_name(source, root)} escapes the package: {target}"
        )
        return None
    return resolved


def validate_markdown_links(root: Path, errors: List[str]) -> None:
    for source in sorted(root.rglob("*.md")):
        if not source.is_file():
            continue
        text = read_utf8(source, root, errors)
        if text is None:
            continue
        for target in markdown_targets(text):
            resolved = local_link_path(source, target, root, errors)
            if resolved is not None and not resolved.is_file():
                errors.append(
                    f"Broken relative link in {relative_name(source, root)}: {target}"
                )


def validate_required_links(root: Path, errors: List[str]) -> None:
    skill_path = root / "SKILL.md"
    if skill_path.is_file():
        text = read_utf8(skill_path, root, errors)
        if text is not None:
            linked_paths = {
                local_link_path(skill_path, target, root, errors)
                for target in markdown_targets(text)
            }
            for target in REQUIRED_SKILL_LINKS:
                if (root / target).resolve() not in linked_paths:
                    errors.append(f"SKILL.md must link to {target}.")

    route_index = root / "references" / "route-index.md"
    if route_index.is_file():
        text = read_utf8(route_index, root, errors)
        if text is not None:
            linked_paths = {
                local_link_path(route_index, target, root, errors)
                for target in markdown_targets(text)
            }
            for target in REQUIRED_ROUTES:
                if (root / target).resolve() not in linked_paths:
                    errors.append(f"{target} is not linked from references/route-index.md.")

    for readme_name in ("README.md", "README.ru.md"):
        readme = root / readme_name
        if not readme.is_file():
            continue
        text = read_utf8(readme, root, errors)
        if text is None:
            continue
        if SKILL_NAME not in text:
            errors.append(f"{readme_name} must use the package name '{SKILL_NAME}'.")
        linked_paths = {
            local_link_path(readme, target, root, errors)
            for target in markdown_targets(text)
        }
        for guide in REQUIRED_PLATFORM_GUIDES:
            if (root / guide).resolve() not in linked_paths:
                errors.append(f"{readme_name} must link to {guide}.")


def is_private_path(path: Path) -> bool:
    if ".autopilot" in path.parts or ".aws" in path.parts:
        return True
    name = path.name.lower()
    if name in PRIVATE_NAMES or name.startswith(".env."):
        return True
    return path.suffix.lower() in PRIVATE_SUFFIXES


def validate_private_material(root: Path, errors: List[str]) -> None:
    for path in sorted(root.rglob("*")):
        if is_private_path(path):
            errors.append(f"Private file or directory must not be packaged: {relative_name(path, root)}")
            continue
        if not path.is_file() or path.stat().st_size > 5_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern, label in SECRET_PATTERNS:
                if pattern.search(line):
                    errors.append(
                        f"Secret-like {label} in {relative_name(path, root)}:{line_number}."
                    )
                    break


def validate_license_and_attribution(root: Path, errors: List[str]) -> None:
    license_path = root / "LICENSE"
    if license_path.is_file():
        text = read_utf8(license_path, root, errors)
        if text is not None:
            actual = " ".join(text.split())
            expected = " ".join(MIT_LICENSE_TEXT.split())
            if actual != expected and not actual.startswith(expected + " "):
                errors.append(
                    "LICENSE must contain the complete MIT license text and upstream copyright notice."
                )

    attribution_path = root / "ATTRIBUTION.md"
    if attribution_path.is_file():
        text = read_utf8(attribution_path, root, errors)
        if text is not None:
            normalized = " ".join(text.casefold().split())
            negates_derivative_status = any(
                pattern.search(normalized) for pattern in NEGATED_DERIVATIVE_PATTERNS
            )
            states_derivative_status = any(
                pattern.search(normalized) for pattern in POSITIVE_DERIVATIVE_PATTERNS
            )
            if negates_derivative_status or not states_derivative_status:
                errors.append(
                    "ATTRIBUTION.md must positively state and must not negate that Autopilot Anything adapts or derives from Nick Vels's upstream Autopilot skill."
                )
            required_attribution = (
                "nick vels",
                "github.com/nick-vels/skills",
                "mit license",
                "copyright (c) 2026 nick vels",
                "license",
            )
            if any(marker not in normalized for marker in required_attribution):
                errors.append(
                    "ATTRIBUTION.md must identify Nick Vels and the upstream repository, MIT license, and preserved notice."
                )


def validate(package_root: Path = PACKAGE_ROOT) -> List[str]:
    """Return package problems; an empty list means the public checks passed."""
    root = package_root.resolve()
    errors: List[str] = []
    if not root.is_dir():
        return [f"Package root is not a directory: {root}"]

    for relative_path in REQUIRED_FILES:
        if not (root / relative_path).is_file():
            errors.append(f"Missing required file: {relative_path}")

    skill_path = root / "SKILL.md"
    if skill_path.is_file():
        text = read_utf8(skill_path, root, errors)
        if text is not None:
            parse_frontmatter(text, errors)

    validate_markdown_links(root, errors)
    validate_required_links(root, errors)
    validate_license_and_attribution(root, errors)
    validate_private_material(root, errors)
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Package structure, links, routes, provenance, and privacy checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
