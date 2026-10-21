# Claude Code

Claude Code skills are folders with a `SKILL.md`. The folder name becomes the slash command, and project skills are loaded from `.claude/skills/` in the project or its parent directories.

## Install

For your account, clone the standalone repository into Claude Code's personal skills directory:

```sh
git clone https://github.com/atrshncv-ai/autopilot-anything.git "$HOME/.claude/skills/autopilot-anything"
```

For one project, run this from the project root to add the skill as a submodule:

```sh
git submodule add https://github.com/atrshncv-ai/autopilot-anything.git .claude/skills/autopilot-anything
```

If the project does not use submodules, clone or copy the complete repository into `<repo>/.claude/skills/autopilot-anything/` and track its files with the project. Keep `SKILL.md`, `references/`, and `scripts/` together.

## Invoke and smoke-check

Start Claude Code in the project, type `/` and select `/autopilot-anything`, or enter that command directly. For a harmless check, ask it to turn “organize my desk” into a three-step checklist and explicitly say not to change files or contact anyone. Confirm Claude Code lists the skill and returns the requested checklist. Project skills may require accepting the workspace trust prompt.

Claude Code watches existing skill directories for changes. If you create the top-level `.claude/skills/` or `~/.claude/skills/` directory while a session is already open, run `/reload-skills`; otherwise restart the session if the new skill is not listed.

## Per-run dashboard

When Claude Code runs the skill, it should invoke `scripts/dashboard.py` from the same installed folder as the loaded `SKILL.md`, and keep run state under the current project. If the host can maintain a background process and open its loopback URL, the tracker serves a read-only live page. If either capability is unavailable, generate and present the static snapshot. This is a best-effort path by analogy; Claude Code has not been runtime-tested here. Follow the [shared dashboard lifecycle](../references/dashboard.md).

## Update

For a personal clone:

```sh
git -C "$HOME/.claude/skills/autopilot-anything" pull --ff-only
```

For a project submodule, run from the project root, then commit the updated submodule pointer if teammates should receive it:

```sh
git submodule update --remote --merge -- .claude/skills/autopilot-anything
```

For copied files, replace the complete `.claude/skills/autopilot-anything/` directory with the new package contents. Claude Code watches skill files in an existing skill directory; use `/reload-skills` if the directory itself was just created during the session.

## Remove

Remove a personal skill with:

```sh
rm -rf -- "$HOME/.claude/skills/autopilot-anything"
```

To remove a project submodule from the project root:

```sh
git submodule deinit -f -- .claude/skills/autopilot-anything
git rm -f -- .claude/skills/autopilot-anything
```

To remove a copied project skill, delete `<repo>/.claude/skills/autopilot-anything/` and remove its tracked files.

## Source

- [Anthropic: Claude Code skills](https://code.claude.com/docs/en/skills) — skill format and invocation, personal/project locations, change detection, and removal.
