# Package architecture

Autopilot Anything is a portable skill package, not a standalone application or tool server. The host agent supplies the model, tools, permissions, and external-service connections; this package supplies the workflow, domain guidance, progress tracker, and package checks.

## Request flow

1. [`SKILL.md`](../SKILL.md) is the entry point. It captures the brief, selects an appropriate depth, and loads the shared workflow and safety guidance.
2. [`references/core-workflow.md`](../references/core-workflow.md) defines the adaptive process, requirements, interviews, planning, progress, resume, and final acceptance.
3. [`references/route-index.md`](../references/route-index.md) selects one or more deliverable routes. The route files under `references/routes/` specify domain methods and checks for code, research, information gathering, data analysis, presentations, documents, and general work; see the [code route](../references/routes/code.md) as an example.
4. [`references/safety-and-evidence.md`](../references/safety-and-evidence.md) applies across routes, including evidence quality, uncertainty, high-risk recommendations, and confirmation before consequential external actions.
5. The agent uses tools available in the host to produce the result, records meaningful progress, then checks the deliverable with criteria suited to that result.

## Progress dashboard

[`scripts/dashboard.py`](../scripts/dashboard.py) owns each run's state and event log under the user's project at `.autopilot/anything/<run-id>/`. It renders [`dashboard.html`](../dashboard.html) as a live, loopback-only read-only view when supported, and as a standalone `snapshot.html` fallback. The page observes state; it cannot update a run, approve a gate, or perform an external action. See the [dashboard lifecycle](../references/dashboard.md).

## Platform adapters

The shared instructions do not assume that a host has a particular connector or that every platform uses the same invocation syntax. Platform guides such as [Codex](../platforms/codex.md) document installation and native invocation; the [compatibility records](../compatibility/README.md) store observed runtime results and repeatable manual scenarios. Runtime claims must be based on checks actually performed in that platform.

## Package checks and project records

- [`scripts/validate_package.py`](../scripts/validate_package.py) checks package structure, links, routes, provenance, and privacy constraints.
- [`tests/test_dashboard.py`](../tests/test_dashboard.py) and the related suite cover the validator and dashboard tracker/UI contracts.
- [`.github/workflows/validate.yml`](../.github/workflows/validate.yml) runs package validation and the Python tests on pushes and pull requests.
- [Architecture decisions](adr/0001-standalone-public-package.md) record choices that affect the package structure and workflow.
- [`CONTEXT.md`](../CONTEXT.md) defines project terminology; [`CHANGELOG.md`](../CHANGELOG.md) records public package changes.

Run checks from the package root:

```sh
python3 scripts/validate_package.py
python3 -m unittest discover -s tests -p 'test_*.py'
```
