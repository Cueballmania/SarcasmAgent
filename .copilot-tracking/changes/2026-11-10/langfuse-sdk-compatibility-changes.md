# RPI Changes: Langfuse SDK compatibility

## Metadata

Task ID: `langfuse-sdk-compatibility`. Date: 2026-11-10.
Plan: [.copilot-tracking/plans/2026-11-10/langfuse-sdk-compatibility-plan.md](../../plans/2026-11-10/langfuse-sdk-compatibility-plan.md).

## Execution Status

Complete, full-plan invocation. Completed P01 and P01-T01/T02/T03; no remaining active markers. Plan Ready and standard critique Complete/Pass; no blockers.

## Execution Summary

Langfuse 5.2.0 is locked; approved native metadata is JSON-encoded; actual-SDK tests verify the new score endpoint, native run scores and task-observation linkage. Privacy, classifier behavior and summary/report contracts are preserved.

## Completed Work

### Supported SDK and JSON metadata

P01-T01: [pyproject.toml](../../../pyproject.toml), [uv.lock](../../../uv.lock) now select Langfuse 5.2.0 through `>=5.2,<6`; uv changed only the Langfuse package/version requirement. [app/tracing.py](../../../app/tracing.py) JSON-encodes approved native metadata while preserving original application attributes and the strict allowlists. `uv lock`, locked sync and installed-version check passed. Protocol coverage follows in P01-T02.

### Actual v5 score and experiment contracts

P01-T02: [tests/test_classifier.py](../../../tests/test_classifier.py) and [tests/test_eval_metrics.py](../../../tests/test_eval_metrics.py) assert POST `/api/public/scores` array payloads with accepted responses, JSON-decoded metadata semantics, native local-run scores keyed by experiment ID, and item evaluator scores linked to the SDK's `experiment-item-task` observation. Project lookup is mocked; all span exports and provider calls are intercepted.

The first tests exposed native experiment-level scores with no trace ID, then the SDK's new task child (where approved case metadata is applied). These are supported v5 contracts, not absent telemetry. Test selection now separates experiment scores from trace scores and checks parent/task/observation IDs explicitly. Existing success/error/Unknown/cancellation/privacy and report gate assertions still pass. No tests removed or added; existing cases extended. Targeted/configuration tests: 23 passed. HTTP audit regressions: 11 passed, 1 PostgreSQL test deselected.

### Accurate v5 operator guidance

P01-T03: [docs/observability-demo.md](../../../docs/observability-demo.md) identifies SDK/server requirements, task score targets, native local run persistence, deployment-before-cutoff and new-ingestion verification. [evals/run.py](../../../evals/run.py) explains the retained summary trace as a stable report/navigation contract instead of a v3 workaround. Documentation reviewed against the observed SDK and migration evidence.

## Implementation-Time Plan Updates

P01-T02 local judgment: inspect installed v5 `_process_experiment_item` and score models when tests expose protocol differences. No requirement, authority or design changes. The plan already permits adapting actual v5 span/score contracts; no new critique warranted.

## Business Alignment

* None.

## Validation Record

| Check | Status | Evidence |
|---|---|---|
| `uv lock` and `uv sync --locked --group eval` | Passed | Only Langfuse upgraded, 3.15.0 to 5.2.0 |
| `uv lock --check` | Passed | 72 packages resolved |
| `uv run --locked ruff check .` | Passed | All checks passed |
| `uv run --locked ruff format --check .` | Passed | 45 files formatted |
| `uv run --locked --group eval pytest tests/test_classifier.py tests/test_eval_metrics.py tests/test_config.py -q --tb=short` | Passed | 23 tests |
| `uv run --locked --group eval pytest tests/test_audit_api.py -m 'not postgres' -q --tb=short` | Passed | 11 tests; 1 PostgreSQL-only test deselected |
| `git diff --check` | Passed | No whitespace errors |
| PostgreSQL/browser suites | Skipped | No database/browser behavior changed; focused SDK and HTTP coverage sufficient |
| Live ingestion/evaluations | Skipped | Outside authorized scope; no secrets or paid calls |

## Pre-Review Reconciliation

Plan task markers, context, completed-work entries, requirements and validation reconciled. No BRD/PRD/ADR differences, pending decisions, blockers or active follow-ups. Ready for the session's one Review.

## Blockers

None.

## Remaining Work

None.

## Follow-Up Items

None.

## Return-to-Caller State

Full-plan implementation Complete, Review ready. Automatic parent proceeds to Review; source changes validated offline, not deployed. No business-alignment entries or plan-design changes. Unrelated pre-existing presentation research left unchanged.
