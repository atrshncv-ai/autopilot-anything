# Autopilot Anything

Autopilot Anything is one portable agent skill for carrying a request from a short brief to a checked result. It chooses a proportionate workflow for the task, loads a focused route when needed, and reports work it could not perform or verify.

The target public repository for this standalone package is [atrshncv-ai/autopilot-anything](https://github.com/atrshncv-ai/autopilot-anything). The repository root is the skill folder; it contains only the Autopilot Anything adaptation and its supporting files.

## What it can do

The skill supplies instructions, reference material, and a package validator. It does not include an MCP server, browser, file editor, connector, credentials, or other execution service. Whether an agent can search the web, edit files, inspect a document, or act in an external service depends on the tools and permissions available in that runtime. Actions such as sending, publishing, purchasing, or deleting still require the safeguards of the host environment. Other platforms are best-effort; only Codex, Claude Code, and Cursor have dedicated installation guides here.

## What it preserves and changes

Autopilot Anything preserves the source Autopilot's verbatim brief, requirement ledger, adaptive interview, progress and resume point, and acceptance against the original brief. It replaces coding-centered file tickets, implementation waves, and test-count gates with route-aware work items and checks chosen for the deliverable: evidence and source checks for research, reproducible calculations for data, rendered layout review for documents and slides, and project checks for code. The three workflow levels are based on complexity; risk and irreversibility are assessed separately and can add safeguards at any level.

## Runtime compatibility status

Codex is the only platform designated for full live validation. On 2026-10-21, an isolated install and native skill discovery were confirmed with Codex CLI 0.142.5, but execution checks were blocked before a model response by an unsupported-model error. The behavior smoke cases remain unverified, so this run does not establish full Codex compatibility. Claude Code and Cursor guides follow their documented skill mechanisms as best-effort adaptations and have not been runtime-tested. See the [Codex smoke record](compatibility/codex.md).

## Install

Clone the repository into the platform's user-level skill directory, or add it as a project submodule. The repository itself is the complete skill folder, so `SKILL.md`, `references/`, and `scripts/` stay together. The platform guides include exact commands for installation, updates, removal, and a harmless smoke check.

| Platform | User-level location | Project-level location | Invoke |
|---|---|---|---|
| Codex CLI / IDE extension | `$HOME/.agents/skills/autopilot-anything/` | `<repo>/.agents/skills/autopilot-anything/` | `$autopilot-anything` or choose it from `/skills` |
| Claude Code | `~/.claude/skills/autopilot-anything/` | `<repo>/.claude/skills/autopilot-anything/` | `/autopilot-anything` |
| Cursor | `$HOME/.agents/skills/autopilot-anything/` | `<repo>/.agents/skills/autopilot-anything/` or `<repo>/.cursor/skills/autopilot-anything/` | Type `/` in Agent chat and select `autopilot-anything` |

See [Codex installation](platforms/codex.md), [Claude Code installation](platforms/claude-code.md), and [Cursor installation](platforms/cursor.md) for install, update, remove, and smoke-check steps. The invocation syntax is host-specific: Codex uses `$autopilot-anything` (or its `/skills` selector), while Claude Code and Cursor expose the skill in their slash menus.

## Check the package

From this directory, run `python3 scripts/validate_package.py` to check required files and skill metadata. This checks the package structure only; follow the platform guide's manual smoke steps to confirm that a specific runtime discovers and invokes the skill.

## License and attribution

This adaptation is distributed under the MIT License; see [LICENSE](LICENSE) and [ATTRIBUTION.md](ATTRIBUTION.md). It is based on Nick Vels's Autopilot skill in the [nick-vels/skills](https://github.com/nick-vels/skills) collection. This repository contains only the Autopilot Anything adaptation; unrelated skills from that collection are not included.

## Platform documentation

- [OpenAI: Skills](https://developers.openai.com/plugins/concepts/skills) and [Codex: Build skills](https://learn.chatgpt.com/docs/build-skills)
- [Anthropic: Claude Code skills](https://code.claude.com/docs/en/skills)
- [Cursor: Agent Skills](https://cursor.com/docs/skills)
