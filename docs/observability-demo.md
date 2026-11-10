# Observability and evaluations: the maintenance loop

**Observability explains what happened. Evaluations measure whether it was right.
Release gates decide whether the evidence is good enough to ship.** A fast,
well-formed answer can still be wrong; a correct answer is not useful if requests
regularly fail. Neither traces nor a one-off accuracy number replaces the other.

This app deliberately has one model call, not a fictional multi-tool agent.
The same maintenance loop applies when an agent has more steps: trace the real
steps and evaluate the outcomes that matter.

## Prepare before the talk

Use the existing approved Langfuse project and deployment; no new infrastructure
or dashboard provisioning is required. Keep project access operator-only.
Choose a bounded time range and the correct environment/release in Langfuse.
Prepare these tabs so the talk does not depend on running RPI or a full evaluation:

1. The finished audience app and one previously authorized synthetic request.
2. Its `sarcasm-classification` trace, plus a saved `Unknown` example and an error
   trace if one already exists. Do not induce failures on a shared deployment.
3. A completed evaluation's `experiment-item-run` trace, its
   `experiment-item-task` child (the item score target), and its
   `evaluate.sarcasm` summary trace. The report's `run_name`,
   `summary_trace_id` and `cases[].trace_id` identify the exact evidence.
4. The corresponding local report and revision-bound checker result.

To prepare **real** evaluation evidence, use the commands in the
[README](../README.md#evaluations-and-release) with independently reviewed data,
approved pricing, thresholds and budgets. Run pilot work before opening the
holdout; do not tune against the holdout during the talk. No reviewed dataset or
quality claim is shipped with this repository. Unit-test fixtures are integration
evidence, not a demonstration of model accuracy.

The locked Python SDK is v5.2.0, compatible with the observations-first data
model. It requires Langfuse Cloud or a self-hosted server at v4.59.0 or later.
Local-data experiments now persist native run-level scores as well as item
scores. Use the Experiments view for grouping, or the trace names/IDs and Scores
view for direct navigation.

Deploy the updated locked dependencies before November 16, 2026; changing this
repository does not update an already running service. After deployment, check
that newly ingested observations report Python SDK v5 and that metadata, item
scores and run scores appear. The migration dashboard checks recent activity, so
older SDK configurations may remain visible during its three-day lookback.
Offline tests do not clear that dashboard warning or prove live delivery.

## Five-minute walkthrough

| Time | Show | Point to make |
|---|---|---|
| 0:00–0:45 | Finished app and its exact three-label contract | “We can walk through the RPI artifacts without waiting for a build. This is the product we maintain.” |
| 0:45–2:00 | `sarcasm-classification`, its OpenAI generation and `validate.classification` child | “Which release and prompt ran? Did the provider complete? How long did it take? What tokens were used?” |
| 2:00–2:45 | `Unknown` versus an error trace | “Abstention is a valid result, not a disguised timeout. A valid response is not proof of correctness.” |
| 2:45–4:15 | Item scores, run summary and report confusion matrix/slices | “Reviewed labels reveal mistakes that a healthy trace cannot. Aggregate accuracy alone hides minority-class and abstention failures.” |
| 4:15–5:00 | Holdout checker and maintenance loop | “Changes need fresh evidence. Diagnose, curate and review, evaluate, gate the release, then observe again.” |

Suggested closing line: **“An agent without traces is hard to debug. An agent
without evaluations is hard to trust. A maintained agent needs both.”**

## What is observable

The classification trace contains native Langfuse metadata for request UUID,
model, environment, deployment revision, prompt/schema revisions, input character
count, outcome, label, safe error code, duration and available token counts.
Resource attributes identify the service, version and environment. The
instrumented generation records provider usage; the validation child checks
completion, refusal and parsed-label availability after the typed SDK parser.
Malformed JSON/schema failures can occur inside the generation before that
validation child starts.

| Runtime score | Meaning | Not evidence of |
|---|---|---|
| `response_contract` | 1 for a completed allowed label, including `Unknown`; 0 for an unsuccessful attempt | Semantic correctness, successful HTTP delivery or final audit commit |
| `abstained` | 1 for `Unknown`, 0 for an answered label; absent on failures | Correctness of the abstention decision |
| `latency_ms` | Classifier duration, including unsuccessful attempts | End-to-end HTTP or database latency |

Successful abstention is marked `WARNING`; failed classification is `ERROR`.
Use error codes rather than exception text. Request cancellation is recorded as
`request_cancelled` and is re-raised, never converted into `Unknown`.
The HTTP audit remains the source for admission limits, pending requests,
database failures and final response commitment; join it with trace/request IDs.
Export is best-effort, not a dependency of classification success.

## What is evaluated

Each reviewed case gets `exact_label`, `eval_response_contract`,
`abstention_correct` and `latency_within_target` scores on its experiment
observation. `abstention_correct` checks whether to abstain, not whether a
non-abstaining label is correct. The latency score is a per-case diagnostic;
the release policy uses the run's p95.

The separate `evaluate.sarcasm` trace persists numeric aggregate scores for local
datasets, including accuracy, macro-F1, coverage, answered accuracy when defined,
Unknown/failure rates, p50/p95, missing measurements and each class's
precision/recall/F1/support. This summary preserves the report's stable trace
link and explicit release-gate signal alongside v5's native experiment scores.

The local report also contains the confusion matrix, full metrics by dataset
tag, failure-code counts, and per-case expected/predicted labels, trace ID,
latency and available usage/cost. No message text is included. Tiny slices have
no statistical sufficiency claim. Missing SDK-isolated cases remain in the
denominator as failures with unavailable trace/latency/usage fields.

`release_gate_passed` is 0 for pilot runs and failing holdouts. It is a useful
dashboard signal, **not deployment authorization**: the CLI checker still binds
holdout evidence to the candidate revision and source/dataset/config hashes.
Unknown cost stays unknown; Langfuse may independently infer provider costs in
its UI, but those estimates do not become an invoice or local report evidence.

## Keep the loop running

Monitor latency, failures, usage, Unknown rate and exporter diagnostics within
bounded environment/release/time windows. An Unknown-rate shift is a reason to
investigate, not a ground-truth quality score. Review representative approved
examples, adjudicate labels independently, add regression cases to pilot data,
and re-evaluate relevant code/prompt/model changes before release.

Compare saved runs with matching reviewed dataset versions and operating
conditions; explain changed conditions rather than attributing every difference
to the prompt. After inspecting a holdout, follow the curation policy before
reusing it as future release evidence.

Audience text, prompts, arbitrary metadata, cookies, identities, exception
payloads and provider status messages remain excluded from telemetry. Scores
use a separate ingestion path and contain only fixed names, numeric values and
fixed comments. Review traces **and score payloads** after SDK upgrades.

For an offline rehearsal of the integration paths without credentials or paid
calls:

```bash
uv run --locked --group eval pytest tests/test_classifier.py tests/test_eval_metrics.py -q
```

These tests do not populate Langfuse or establish actual model quality.
