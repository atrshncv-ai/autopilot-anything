# Codex

Codex skills are folders with a `SKILL.md` and optional supporting files. This package needs to remain a complete folder because `SKILL.md` links to `references/` content.

## Install

For your account, clone the standalone repository directly into Codex's user-level skills directory:

```sh
git clone https://github.com/atrshncv-ai/autopilot-anything.git "$HOME/.agents/skills/autopilot-anything"
```

For one project, run this from the project root to add the skill as a submodule:

```sh
git submodule add https://github.com/atrshncv-ai/autopilot-anything.git .agents/skills/autopilot-anything
```

If your project does not use submodules, clone or copy the repository's tracked files into `<repo>/.agents/skills/autopilot-anything/` and commit those files with the project. Do not copy only `SKILL.md`.

## Invoke and smoke-check

In Codex CLI or the IDE extension, use `/skills` to browse available skills or type `$autopilot-anything` in the prompt. For a harmless check, ask it to turn “organize my desk” into a three-step checklist and explicitly say not to change files or contact anyone. Confirm the skill appears in the selector or the response follows the checklist workflow. Codex's documented explicit skill mention is `$autopilot-anything`; the Claude Code and Cursor `/autopilot-anything` slash form is not the Codex invocation documented for local skills.

Codex detects skill changes automatically. If the skill does not appear, restart Codex and check that `SKILL.md` is at the exact path above.

See the [recorded Codex compatibility results](../compatibility/codex.md). The 2026-10-21 check confirmed isolated installation and skill discovery with Codex CLI 0.142.5; execution smoke cases remain unverified because the account rejected the available model IDs.

## Update

For a user-level clone:

```sh
git -C "$HOME/.agents/skills/autopilot-anything" pull --ff-only
```

For a project submodule, run from the project root, then commit the updated submodule pointer if you want teammates to receive the update:

```sh
git submodule update --remote --merge -- .agents/skills/autopilot-anything
```

For copied files, replace the complete `.agents/skills/autopilot-anything/` directory with the new package contents. Restart Codex if it does not pick up the update.

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

To remove a copied project-level skill, delete `<repo>/.agents/skills/autopilot-anything/` and remove its tracked files.

## Sources

- [OpenAI: Skills](https://developers.openai.com/plugins/concepts/skills) — folder and `SKILL.md` format, activation, and the boundary between skill instructions and tools.
- [OpenAI: Build skills](https://learn.chatgpt.com/docs/build-skills) — current Codex user/project locations, `$` invocation, detection, and refresh behavior.
