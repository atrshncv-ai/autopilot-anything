# Cursor

Cursor discovers skill folders containing `SKILL.md`. Its native user-level locations include `~/.agents/skills/` and `~/.cursor/skills/`; project-level locations include `.agents/skills/` and `.cursor/skills/`. This guide uses `.agents/skills/` for the portable project path.

## Install

For your account, clone the standalone repository into a user-level skill directory:

```sh
git clone https://github.com/atrshncv-ai/autopilot-anything.git "$HOME/.agents/skills/autopilot-anything"
```

For one project, run this from the project root to add the skill as a submodule:

```sh
git submodule add https://github.com/atrshncv-ai/autopilot-anything.git .agents/skills/autopilot-anything
```

If the project does not use submodules, clone or copy the complete repository into `<repo>/.agents/skills/autopilot-anything/` (or `<repo>/.cursor/skills/autopilot-anything/`) and track its files with the project. Keep `SKILL.md`, `references/`, and `scripts/` together.

## Invoke and smoke-check

Open Agent chat, type `/`, search for `autopilot-anything`, and select it. For a harmless check, ask it to turn “organize my desk” into a three-step checklist and explicitly say not to change files or contact anyone. Confirm the skill is listed and that the response follows the checklist workflow. A slash-invoked skill applies to that message; use it again when needed in a later message.

Cursor discovers skills when it starts. Reopen Cursor or its Agent session if a newly installed or updated skill does not appear. User-level skills stay on the local machine unless you enable Cursor's documented cloud sync or team publishing; project skills in the repository are available where that repository is checked out.

## Update

For a user-level clone:

```sh
git -C "$HOME/.agents/skills/autopilot-anything" pull --ff-only
```

For a project submodule, run from the project root, then commit the updated submodule pointer if you want teammates to receive the update:

```sh
git submodule update --remote --merge -- .agents/skills/autopilot-anything
```

For copied files, replace the complete `.agents/skills/autopilot-anything/` directory with the new package contents, then reopen Cursor or the Agent session if the update is not discovered.

## Remove

Remove a user-level clone with:

```sh
rm -rf -- "$HOME/.agents/skills/autopilot-anything"
```

To remove a project submodule from the project root:

```sh
git submodule deinit -f -- .agents/skills/autopilot-anything
git rm -f -- .agents/skills/autopilot-anything
```

To remove copied project files, delete `<repo>/.agents/skills/autopilot-anything/` (or `.cursor/skills/autopilot-anything/`) and remove its tracked files.

## Source

- [Cursor: Agent Skills](https://cursor.com/docs/skills) — supported locations and scope, slash-menu invocation, and availability limits for unsynced user skills.
