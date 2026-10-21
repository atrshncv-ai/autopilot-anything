# Compatibility checks

These manual smoke checks distinguish package structure from actual host behavior. Each platform scenario can be run on its own from a clean scratch project; it covers installation, discovery, the host's native invocation, and representative results. Do not count a scenario as passed unless the runtime response and any requested local artifact were inspected.

## Scenarios

- [Codex CLI or IDE](codex.md)
- [Claude Code](claude-code.md)
- [Cursor](cursor.md)

Run every case in its platform scenario in a fresh conversation or turn. Record the host version, whether the runtime was authenticated, the cases actually run, and any `not run` reason below. A package validator pass does not count as a runtime pass.

## Environment results

Snapshot for this source workspace on 2026-10-21:

| Platform | Detected environment | Runtime result | Cases run / not run |
| --- | --- | --- | --- |
| Codex | Codex CLI 0.142.5; `codex login status` reported ChatGPT authentication | partial — isolated install and native skill discovery passed; inference was blocked by an unsupported-model HTTP 400 | Neutral `codex debug prompt-input` from the scratch project included the skill name. The adaptive-depth prompt was attempted with `gpt-6-luna`, then overrides `gpt-6.1-sol`, `gpt-5.5`, `gpt-5.4`, and `gpt-5.3-codex`; all were rejected, so no behavior case passed. `/skills` and remaining scenarios were not run. No credentials copied and no external actions performed; see [full Codex record](codex.md). |
| Claude Code | Claude Code 2.1.197; `claude auth status` reported `loggedIn: false` | not run — runtime is not authenticated | All cases not run; no credentials requested |
| Cursor | `cursor` command absent from `PATH`; no Cursor.app in `~/Applications` or `/Applications` | not run — Cursor was not detected in the standard install locations | All cases not run |

Update this table only from observed runtime results. Keep unavailable cases marked `not run`; do not infer compatibility from the files or from another platform's behavior.

## Package-only checks

From the `autopilot-anything/` directory, run:

```sh
python3 scripts/validate_package.py
python3 -m unittest discover -s tests -p 'test_*.py'
```

These commands verify package contents and validator behavior. They do not launch Codex, Claude Code, or Cursor.

## Deferred checks

The dashboard release does not change the prior Codex behavioral-smoke result: installation and discovery were observed, while behavior cases remain unverified because inference was blocked before a response. Two previously identified package-validator edge cases also remain deferred as separate follow-up tasks. Dashboard-specific coverage added here is not evidence that either deferred validator edge is fixed, and no compatibility result should be changed without a fresh observed run.
