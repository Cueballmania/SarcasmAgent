# Langfuse observability changes

Plan: [langfuse-observability-plan.md](../../plans/2026-11-10/langfuse-observability-plan.md).
Declared scope: full plan P01-P03. Execution: complete.
Plan Ready, standard critique Complete/Pass. Subagents: none.

## Completed work

### P01-T01: Operational traces without audience text

[app/classifier.py](../../../app/classifier.py) records outcome, input length,
model/revision/usage, validation timing and contract/latency/abstention scores.
Unknown remains valid; cancellation re-raises with a safe code.
[app/tracing.py](../../../app/tracing.py) uses explicit approved fields, native
metadata projection, retained experiment linkage and service/version/environment
resources. Arbitrary prefixed metadata remains excluded.

### P02-T01: Persisted experiment and case evidence

[evals/run.py](../../../evals/run.py) adds deterministic item checks,
explicit aggregate/per-class summary trace scores, case trace/failure/usage
evidence, full slice metrics and failure counts. Config revision is also applied
to the classifier settings so nested trace revisions cannot disagree.
Missing SDK-isolated cases remain failures and costs stay nullable.

### P03-T01: Regressions and a prepared five-minute walkthrough

[tests/test_classifier.py](../../../tests/test_classifier.py),
[tests/test_eval_metrics.py](../../../tests/test_eval_metrics.py) and the dependent
[tests/test_audit_api.py](../../../tests/test_audit_api.py) verify actual SDK span
topology, ingestion, privacy, failure/abstention semantics and report linkage.
[docs/observability-demo.md](../../../docs/observability-demo.md) supplies the
prepared talk flow and explains operational versus semantic evidence.
README, operations and rubric link to the guide and describe actual score
semantics, local-data SDK limitations, and retained release gates.

## Validation

Passed: focused actual-SDK offline tests, 19 cases; Ruff check and format-check
for the repository; `git diff --check`.
Covered success, Unknown, refusal/incomplete/invalid label/provider/timeout,
cancellation, arbitrary metadata stripping, local experiment aggregate ingestion,
provider failures and SDK-isolated missing cases. Actual span and score payloads
captured offline. First isolated-case injection was normalized by OpenAI into
provider_error; moved injection after the SDK boundary to exercise true
experiment isolation. Corrected formatting with the existing formatter.
First full isolated regression run: 44 passed, 1 failed because the shared
provider fixture gained score capture and its audit-test consumer still unpacked
three fields. Updated that directly dependent consumer and extended its
privacy/linkage assertion to the score channel.
Final full isolated run: 45 passed, including disposable PostgreSQL audit
linkage and Chromium behavior checks. Ruff check and all 39 Python files'
format check passed; `git diff --check` passed.
Documentation links/claims reviewed against source. Live project delivery,
actual model quality and deployment remain intentionally unexecuted.

## Decisions and deviations

No material deviations. P03 test ownership includes the directly dependent
audit-test fixture consumer; full isolated PostgreSQL/browser checks use already
installed dependencies. Business Alignment: none; no BRD/PRD/ADR authority applies.
No live model/telemetry requests or external mutations authorized.

## Remaining work and handoff

P01-P03 complete. No active-plan work, implementation blockers or follow-ups.
Review complete, outcome Conformant; no Business Alignment decisions pending.

## Git delivery

User requested commit, run and push on 2026-11-10. Re-ran `uv lock --check`,
Ruff lint/format, all 45 isolated PostgreSQL/browser regressions and diff hygiene:
all passed. Delivery branch: `feat/langfuse-observability`, avoiding a possible
connected-service deployment from `main`. No paid evaluation or deployment run.
Only this work's source, tests, documentation and dated evidence are included;
the pre-existing 2026-11-09 presentation research remains untouched.
