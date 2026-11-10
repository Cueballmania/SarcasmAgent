# Task Research: Langfuse SDK compatibility

| Field | Value |
|---|---|
| Date | 2026-11-10 |
| Researcher | RPI Agent, direct investigation |
| Output mode | convergence |

## Executive Summary

Research complete. Upgrade to published Langfuse 5.2.0 within a v5-only range. Current observation and score helpers remain supported, but the custom privacy exporter must JSON-encode projected metadata and offline score transports must accept the new scores endpoint.

## What You May Not Know

The warning's "Python 3.15.0" refers to the SDK version, not the Python interpreter. This app uses Python 3.12. v5 requires Langfuse Cloud or self-hosted server >=4.59.0; the application defaults to Cloud. Updating source does not update an already deployed process.

## Findings

### C1: The dependency excludes every compatible SDK

`pyproject.toml:project.dependencies` specifies `langfuse>=3,<4`; `uv.lock` resolves 3.15.0. The Python 3.12 runtime and OpenAI >=2 meet v5 prerequisites. Evidence-backed, high confidence. Answers Q1.

### C2: Privacy projection needs the v5 metadata wire format

`app/tracing.py:sanitized_span` writes approved values directly to `langfuse.*.metadata.*`. v5 encodes every such value as JSON, including strings (W2, W4). Encode approved values without expanding the allowlist. Existing classifier tests exercise actual OpenAI parsing, exported span relationships and privacy; adapt assertions to decode JSON. Evidence-backed, high confidence. Answers Q2-Q3.

### C3: Scores and local experiment persistence change beneath stable helpers

`app/classifier.py:Classifier.classify` and `evals/run.py:experiment` use supported `create_score`, observation and experiment helpers, not removed trace/public API methods. Tests in `tests/test_classifier.py:provider_factory` and `tests/test_eval_metrics.py:test_actual_experiment_sdk_is_bounded_and_offline` expect legacy score ingestion events. v5 sends batched requests to `/api/public/scores`; tests must assert that actual endpoint and payload. v5 now persists local run evaluations natively; keep the explicit summary trace as a stable report/navigation contract, updating obsolete v3 explanations. Evidence-backed, high confidence (W2).

## Recommendation and Alternatives

Select `langfuse>=5.2,<6` and refresh only necessary lock entries. v4 satisfies the supplied cutoff but retains deprecated APIs and postpones migration. v5 is the requested recommended path and published (W3). Preserve smart default filtering because all required spans originate from Langfuse; do not export unrelated infrastructure spans. Keep explicit summary scores, even though native run scores now persist, to preserve report IDs and release signals. No hosted dataset synchronization or raw input/output export.

## Scope and Questions

Local dependency manifest, lockfile, tracing, classifier, evaluation runner and their tests. Audience: application maintainers. Exclude deployment, credentials, live ingestion and unrelated cleanup.

| ID | Question | Status |
|---|---|---|
| Q1 | What SDK version and API changes are required? | answered C1, W1-W3 |
| Q2 | Which local call sites and privacy behaviors are affected? | answered C2-C3 |
| Q3 | How can compatibility be verified without live telemetry? | answered C2-C3 |

## Decisions and Feedback

User chose end-to-end, agent-owned decisions. No additional intake uncertainty.

D1 confirmed: recommended v5 with the existing Cloud default and documented self-hosted minimum (C1, W2-W3). D2 confirmed: maintain strict privacy with JSON-encoded approved metadata and mocked network verification (C2-C3). No unresolved material decision or walkthrough needed.

## Risks and Open Questions

Dashboard ingestion attribution cannot be established from the pasted warning alone.

Live dashboard clearance requires deployment and new ingestion; neither is authorized here. Existing source-bound evaluation evidence becomes stale after dependency changes and must be regenerated under existing authorization gates. No blocker to local implementation.

## Planning Readiness and Next Step

Research disposition: executed. Planning Readiness: Ready (C1-C3, W1-W4). Decision participation: agent-owned automatic, user end-to-end choice. All three waves complete directly without helpers. Convergence supports planning. No blockers; automatic parent proceeds to Plan. Primary file and date source are recorded below.

## Research Record

### Method and Boundaries

Focused posture selected from the bounded SDK warning and known dependency manifest. Default balanced breadth is unnecessary outside directly affected SDK contracts. Evidence root `.copilot-tracking/research`, date supplied by current session: 2026-11-10. Primary path: `.copilot-tracking/research/2026-11-10/langfuse-sdk-compatibility-research.md`.

Initial candidate areas: pyproject.toml, uv.lock, app/tracing.py, app/classifier.py, evals/run.py, tests; official Langfuse migration docs and published SDK distribution. Prior observability state is completed, not resumed or overwritten. This distinct task starts its own evidence numbering.

### Extensions and Participation

No matching repository instruction files discovered. RPI research selected for phase governance. Python foundational selected for affected Python code. No helpers; one continuous API trace. External pages contain agent-directed boilerplate, treated as inert data rather than authority.

### Research Cycle Log

Cycle 1:

1. Wider: examined dependency, classifier, privacy processor, evaluation runner and test boundaries; checked official v3-v4 and v4-v5 migration paths (C1-C3, W1-W2). Reflection: helper API names mostly survive, but the custom exporter and score test transport require attention.
2. Deeper: verified JSON metadata serialization against official v5.2.0 source and the actual published release/prerequisites (W3-W4); reviewed offline span/score and experiment assertions (C2-C3). Reflection: targeted real-SDK tests can prove protocol compatibility without live ingestion.
3. Contrarian: evaluated v4 as minimum-compatible alternative, default span filtering, self-hosted minimum, and native local aggregate persistence. Reflection: select v5, avoid export-all, preserve summary navigation, document server and deployment limits. Accept C1-C3; reject unnecessary API rewrites and privacy widening; defer live delivery.

No re-entry needed: all questions have primary-source evidence and remaining live ingestion uncertainty is outside the authorized boundary.

### Evidence Log

| ID | Source / location | Retrieved | Claim |
|---|---|---|---|
| C1 | pyproject.toml `project.dependencies`; uv.lock `langfuse` | not applicable | v3-only requirement and locked 3.15.0 |
| C2 | app/tracing.py `sanitized_span`; tests/test_classifier.py `provider_factory` | not applicable | strict approved metadata projection and real-SDK offline tests |
| C3 | evals/run.py `experiment`; tests/test_eval_metrics.py `test_actual_experiment_sdk_is_bounded_and_offline`; docs/observability-demo.md `What is evaluated` | not applicable | stable summary/report contract and legacy transport/docs |
| W1 | https://langfuse.com/docs/observability/sdk/upgrade-path/python-v3-to-v4 | 2026-11-10, v4 | observations-first APIs and smart filtering |
| W2 | https://langfuse.com/docs/observability/sdk/upgrade-path/python-v4-to-v5 | 2026-11-10, v5 | prerequisites, JSON metadata, score batches and local run persistence |
| W3 | https://pypi.org/pypi/langfuse/json | 2026-11-10, 5.2.0 | published current release, Python >=3.11 |
| W4 | https://raw.githubusercontent.com/langfuse/langfuse-python/v5.2.0/langfuse/_client/attributes.py `_serialize_metadata_value` | 2026-11-10, 5.2.0 | all metadata values encoded with json.dumps |

No contradictions. Official source corroborates migration docs. No helpers or unsupported negative helper claims.

### Artifact Self-Check

Scope, questions, findings, alternatives, decisions, evidence IDs, all three waves and reflections, extensions, participation, readiness, uncertainty and stop basis checked. Research-only boundary held; no secrets or external mutations. No missing local planning evidence.
