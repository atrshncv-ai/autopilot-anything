# Run dashboard

The dashboard is the read-only progress view for each Autopilot Anything run. The Python tracker owns the state; the page never changes run status, records events, approves a gate, performs an external action, or stops the tracker. Refresh, language, theme, and requirement filters only affect what is shown.

## Start a run

Use the `scripts/dashboard.py` that belongs to the installed skill currently handling the request. Resolve `SKILL_DIR` from that skill's own `SKILL.md`; do not assume the user's project checkout contains the active package. Keep run state in the user's project under `.autopilot/anything/<run-id>/`.

Start a tracker for every task, including a small one. Choose a unique, safe run ID and record the process mode, depth, complexity, risk, and route separately:

```sh
python3 "$SKILL_DIR/scripts/dashboard.py" init \
  --project-root "$PWD" --run-id 20261021-research-01 \
  --title "Research brief" --mode semi --depth normal \
  --complexity complex --risk medium --route scientific-research
```

The default mode is `semi`; the default depth is `normal`. The four modes describe how much the user is involved: `full` runs without ordinary clarification or process approval, `semi` asks about consequential gaps, `interview` asks about all material product decisions and forks, and `manual` adds approval of the specification and work plan. The three depths are `strict` (stay within the request while still handling errors and empty states), `normal` (use proportionate judgment), and `deep` (examine each requirement and its edge cases). Run an adversarial search for missed requirements at `deep` in every mode and at every depth in `interview` or `manual`. Complexity (`simple|medium|complex`) and risk (`low|medium|high|critical|unknown`) are independent assessments; do not infer one from the other. Safety confirmations for consequential external actions apply in every mode.

## Keep the state current

Use tracker commands for state changes; never hand-edit `state.json` or the generated snapshot. Update it at meaningful transitions, not for every thought:

- `stage` when work enters, completes, skips, waits, fails, or resumes a workflow stage;
- `requirement` when a requirement's status or evidence changes;
- `item` when a universal work item starts, waits, completes, fails, or is blocked;
- `check` when an artifact, source, calculation, or outcome check is performed;
- `gate` for G1–G4 when applicable; use `not-applicable` when an adaptive route legitimately skips that gate;
- `wait` and `answered` around a user decision, so waiting time is separate from active work;
- `note` for a short significant update and `finish` once the result has been checked and handed off.

G1 checks that the brief and requirement ledger retain the user's requests. G2 checks that the specification covers the brief, including an independent search for omissions. G3 traces the work plan to active requirements. G4 is blind final acceptance against the original request. Keep the original request and later changes in the task's local brief; put only short summaries and requirement IDs in dashboard state. Never store secrets or a full conversation in the tracker.

For a simple task, keep the dashboard compact: record the brief/current stage, relevant work and check, then finish. Do not invent interview, specification, plan, or review stages that did not occur; mark skipped stages `skipped` and gates `not-applicable` when appropriate. For a complex task, keep requirements, dependencies, outputs, checks, gates, waits, and the last confirmed checkpoint in sync with the work.

## Show the live page or a snapshot

After initialization, make a static snapshot so there is a useful fallback even if a local server or browser is unavailable:

```sh
python3 "$SKILL_DIR/scripts/dashboard.py" snapshot \
  --project-root "$PWD" --run-id 20261021-research-01
```

When the host can keep a local process running and open a loopback URL, start the server in the background using the host's supported process tool:

```sh
python3 "$SKILL_DIR/scripts/dashboard.py" serve \
  --project-root "$PWD" --run-id 20261021-research-01 --port 0
```

The tracker prints a `127.0.0.1` URL with the selected port. Open that URL using the current host's browser interface when available. The server binds to IPv4 loopback and serves only `GET /`, `GET /state.json`, and `GET /healthz`; it rejects foreign Host headers, other paths, and mutation methods. It does not expose files from the project. Do not add a tunnel, bind to a public interface, or place the run state on a network service.

The live page first renders its embedded snapshot, then refreshes state from the same local server. If the server cannot start, the host cannot open localhost, or the page is opened from disk, provide the generated `snapshot.html` and say that live refresh is unavailable. Regenerate the snapshot after significant transitions, before a long wait, and at finish or failure. Stop a server only through the tracker command when the host confirms the process is no longer needed:

```sh
python3 "$SKILL_DIR/scripts/dashboard.py" stop \
  --project-root "$PWD" --run-id 20261021-research-01
```

## Resume

On continuation, use the same project root and run ID. Read the saved brief and inspect tracker state before doing work; the latest confirmed stage, requirements, completed items, checks, and event revision are the resume point. Then record the resume event and reopen or refresh the live page. Do not repeat an external action whose result was already confirmed. If the run is complete, start a new run for new work instead of reopening it.

The UI source of truth is the installed package's `dashboard.html`. The local server and `snapshot` command both render that file with the selected run state. The snapshot works without a server; changing the package page changes both views on the next tracker process start.
