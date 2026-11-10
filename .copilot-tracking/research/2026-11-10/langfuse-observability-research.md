# Langfuse observability research

## Executive Summary

Research complete. Enhance the current metadata-only traces with operational signals, validation visibility, native Langfuse metadata and experiment linkage. Persist run-level scores explicitly for local-data experiments. Preserve all existing release and paid-call gates.

## What You May Not Know

The app intentionally exports metadata only; readable prompts must not be added for demo convenience. The current export filter also removes experiment linkage, while the locked SDK persists aggregate scores only for hosted-dataset runs, not local-data runs.

## Findings

### Operational visibility is not correctness

C1: `app/classifier.py:Classifier.classify` already emits a classification span and an instrumented generation, but lacks explicit success/abstention, validation timing, and operational scores. `app/main.py:classify` and `docs/operations.md:Audit and public limits` establish that HTTP admission and final audit commit are separate from model execution. Runtime contract validity cannot establish semantic accuracy. Evidence-backed, high confidence from source; real exporter delivery remains an operator check.

### Privacy filtering removes useful native fields

C2: `app/tracing.py:sanitized_span` drops experiment attributes and native metadata while admitting every `sarcasm.*` attribute. Explicit allowlists plus projection of approved application fields into native Langfuse metadata can improve UI utility without admitting raw metadata, prompts, arbitrary status messages or exception events. Evidence-backed from the locked SDK's `_client/attributes.py` and exporter path.

### Local experiment aggregate scores need explicit persistence

C3: `evals/run.py:experiment` uses local data and ignores the SDK result. Locked Langfuse 3.15.0 `_client/client.py:_run_experiment_async` stores aggregate evaluations only when `dataset_run_id` exists. `_process_experiment_item` creates per-item scores with trace and observation IDs; preserve those links and add an explicit run-summary trace for aggregate scores. Capture per-case trace IDs and failures in text-free reports.

W1: https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk (retrieved 2026-11-10) confirms task tracing, item/run evaluators and configurable concurrency. Its current v4/v5 UI guidance is newer than this repository's locked v3 SDK; installed SDK contracts govern implementation and no UI-version guarantee is inferred.

### Existing evaluation metrics are appropriately domain-specific

C4: `evals/metrics.py:summarize`, `evals/contracts.py:Dataset.reviewed_cases`, and `evals/rubric.md:Metrics and gates` provide exact-label scoring, abstention/failure separation, macro-F1 and review/budget gates. Do not invent gold labels, confidence probabilities, tool/RAG metrics, or paid LLM judges for this classifier.

## Recommendation and Alternatives

Select deterministic operational scores plus richer experiment scoring and text-free case reports. Retain the single provider attempt and existing audit semantics. Reject raw prompt capture and LLM judges: they conflict with the privacy boundary or add cost without grounded value. Defer hosted dataset synchronization: it introduces remote writes and a new data policy; local-data experiments already fit the repository.

## Scope and Questions

Audience: a talk showing a completed agentic application and the maintenance feedback loop.
Q1: Which request stages and quality signals are currently visible?
Q2: How can experiments expose regressions and connect reports to Langfuse without leaking text?
Q3: What concise walkthrough makes observability versus evaluation clear?
Local changes only; no external mutations or live model requests. No synthetic gold dataset or accuracy claims.

## Decisions and Feedback

D1: Agent-owned decisions under host autopilot. Preserve existing privacy and budget/review gates.
D2: Use an explicit run-summary trace to persist aggregate scores for local-data experiments (C3).
D3: Show a prepared trace-to-evaluation-to-release-gate walkthrough, not a live RPI run; document that this is a single-model classifier rather than inventing agent tools (C1, C4).

## Risks and Open Questions

Scores use a separate ingestion channel and are not protected by span masking. Emit only fixed evaluator names, numeric values and fixed comments; test actual score HTTP payloads as well as exported spans. Live delivery and reviewed quality evidence remain unverified without an authorized run.

## Planning Readiness and Next Step

Research disposition: executed. Planning Readiness: Ready (C1-C4, W1).
Participation: agent-owned, automatic through Review. No unresolved material choices or blockers. Active parent continues to Plan; no user acknowledgment required.

## Research Record

Evidence root: `.copilot-tracking/research`; date supplied by current host time, 2026-11-10.
Primary path: `.copilot-tracking/research/2026-11-10/langfuse-observability-research.md`.
Mode: convergence. Posture: balanced. Starting areas: app tracing/classifier/lifecycle, evaluation runner/contracts/metrics, installed Langfuse SDK and official documentation.
Extensions: telemetry-foundations and python-foundational selected for metadata and implementation constraints; evaluation-design selected for honest metric semantics, not gold-dataset generation. No dataset generation requested. No helper lanes; direct research.
Prior-knowledge gate: README and code establish metadata-only tracing, one-attempt classification, reviewed datasets, and explicit live authorization.
Cycle 1:
- Wider: examined request, tracing, audit, evaluation, rubric and operations boundaries (C1-C4).
- Deeper: verified installed SDK signatures, native flattened attributes, experiment score ingestion and result linkage (C2-C3); compared official documentation (W1).
- Contrarian: tested design against privacy, Unknown/error semantics, local-versus-hosted SDK behavior, absent cost and gold-review constraints. Raw metadata/IO and hosted synchronization rejected; native linkage and an explicit summary trace selected.
- Synthesis: all three questions answered. Source contracts sufficient; no additional research cycle is indicated.
Self-check: source pointers, decisions, alternatives, extension boundaries, three waves, uncertainty and continuation recorded. No helper lanes ran. No external mutations or secret reads.
