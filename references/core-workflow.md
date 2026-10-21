# Core workflow

Use the same workflow for every domain, but scale its formality to the task. The user's current request and later corrections take precedence over assumptions and source material.

## 1. Capture the current brief

Keep a `RunBrief` with the original user request stored verbatim, plus follow-up details, constraints, intended result, available inputs, and source links. Keep later additions and corrections alongside it rather than rewriting or replacing the original wording. Turn distinct needs into stable `Requirement` IDs with their source, status, rationale, and the artifact or section that addresses them. Add a new requirement when the user changes scope; do not silently remove one.

Before asking questions, scan for contradictions, missing inputs, dependencies, intended audience, desired format, acceptance expectations, access limits, and relevant risk. These are prompts for analysis, not a checklist to ask the user about. Ask only about gaps that could materially change the outcome. Do not ask the user to choose implementation details that do not affect their result.

## 2. Choose complexity and risk separately

Record a `RouteDecision` with work category, complexity, risk, actually available tools, selected route, and explicit limits. Complexity describes the amount of coordination and ambiguity; risk describes likely harm, sensitivity, cost, or irreversibility. A task can be simple and high-risk, or complex and low-risk.

| Level | Use when | Process |
| --- | --- | --- |
| Simple | One clear result, small scope, few dependencies | Do the work directly; ask only for a critical missing fact; make a short check before handing it over. |
| Medium | Several steps or choices within a bounded scope | Clarify only consequential choices; make a brief plan; execute and check against the requested result. |
| Complex | Multiple deliverables or participants, substantial ambiguity, long duration, or many dependencies | Preserve the brief and requirements; identify gaps; interview, write a specification or plan, execute by work items, independently assess acceptance, and preserve a resume point. |

Apply added safeguards at every complexity level when risk or irreversibility warrants them. Raise the process level when new dependencies or risks appear. Reduce it when the scope becomes clear and bounded. When information is unavailable, choose a safe reversible path or mark a visible placeholder instead of inventing an answer.

For a complex task, an interview round contains at most four independent questions. Group dependent details under one question, include a recommended answer when useful, and ask another round only for remaining material gaps. Let the user answer partially and continue with clearly stated assumptions where safe.

## 3. Select a route and make a usable plan

Use the route index to choose a profile based on the requested result, not merely on the tools used. Inspect actual tool and account access before promising execution. If no profile or tool fits, use the general route, identify the limit, and complete the available part without implying unavailable work was done.

Do not force a formal plan onto a small task. For complex work, make each `WorkItem` independently understandable and give it:

- `id` and linked `requirement_ids`;
- `route_owner`, inputs, and a concrete deliverable;
- dependencies on other work items;
- observable `acceptance_checks`, status, and artifact path when applicable.

Order work by dependencies, preserve source inputs, and update the plan when scope or evidence changes. A plan is not a completed result: execute the authorized work and report unfinished items explicitly.

## 4. Execute and maintain a resume point

Use available tools within their granted access. Keep progress and decisions in the current task context or the task's established local tracker. Do not create a lasting personal profile or carry preferences into another task without an explicit request.

For long or interrupted work, record the last confirmed checkpoint, completed deliverables, open items, changed requirements, and any external action already performed. On resumption, inspect that state and available artifacts before continuing. Do not repeat an external action whose result is already confirmed.

## 5. Check the result by artifact type

Every task gets a check proportionate to its result, even a simple one. Record an `ArtifactCheck` with artifact type, check performed, observed result, `passed`/`failed`/`not-run`, and a reason or next step. Choose the evidence that matches the deliverable:

| Result | Useful checks |
| --- | --- |
| Code or software | Existing project conventions, focused tests, relevant type/lint/build checks, and review of the actual change. Report commands not run. |
| Research or current information | Verify important claims against primary or authoritative sources when available; check source dates and links; distinguish evidence from inference. |
| Data analysis | Inspect source, grain, missing values, duplicates, joins, and limitations; keep the original data separate; reproduce transformations and reconcile key results where possible. |
| Document, presentation, or structured file | Keep an editable source when requested; open or render the artifact; inspect layout and content; recalculate or validate structure when the format supports it. |
| Service action or physical/organizational result | Confirm the real access path and target; prepare and confirm actions as required by safety rules; report only outcomes observed from the service or user. |
| Plan or other result | Check that it meets the request, names dependencies and owners where needed, and states assumptions, limits, and the next executable step. |

Do not treat a passed structural check as proof of visual quality or platform compatibility. If a check is unavailable, mark it `not-run` and say why; do not substitute a claim for evidence.

## 6. Hand off against the brief

Compare the final result with the original brief and every active requirement. Provide the requested artifact or location, relevant source links, checks and observed outcomes, and any remaining limitation or user action. Clearly label drafts and plans. Do not describe incomplete work as finished.
