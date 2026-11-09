# Evaluation guide

This is a curation contract, not a reviewed gold dataset. No quality score or
human-review claim exists until the operator supplies independently reviewed data.

## Scope and annotation

Confirm English audience populations and whether labels represent author intent
or third-party perception before labeling. Use the three exact labels.
`Unknown` covers insufficient context, unsupported language and unresolved
conflicting cues; refusal, timeout and provider/output failures are errors.
Review/adjudicate disputed labels independently of classifier predictions.

## Dataset format

Supply JSON accepted by `evals.contracts.Dataset`: version, language (`en`),
annotation (`intended` or `perceived`), review_reference, fixture (`false`) and cases.
Each case has case_id, message, expected, group_id, split (`pilot`/`holdout`), tags,
provenance (`synthetic`/`licensed`/`consented`) and reviewed. Related paraphrases
stay in one split. All three classes need holdout support; review claims are
operator-supplied, never automated attestations. Do not include identifying data.

Include literal positives/negatives, clear sarcasm, ambiguous/unsupported input,
quotation/negation/emoji and prompt-override attempts where the reviewed scope
supports them. Record slice support; a tiny slice is not statistical certainty.

## Metrics and gates

Macro-F1 and per-class precision/recall/support reveal minority-class errors.
Exact match and confusion matrix include every failure in the denominator.
Coverage, answered accuracy, Unknown and failure rates prevent all-abstention
success. Report p50/p95 latency and available cost; unknown cost is not zero.
There are no meaningful probabilities, retrieval or tool calls here: do not use
calibration, RAG metrics, BLEU/ROUGE or an LLM judge as gold.

Use a reviewed pilot to approve quality/coverage/latency bars before the untouched
holdout. `RunConfig` requires approval_reference, candidate revision, request,
concurrency, token and conservative cost caps, current approved pricing and all
threshold fields. Reservations do not guarantee the actual provider invoice.

## Tooling and cadence

Langfuse experiments are the traced runner; scikit-learn computes classification
metrics. Re-evaluate relevant code/prompt/model/dataset changes. The checker binds
the report to candidate revision and source/data/config hashes. Pilot/fixture,
empty, unreviewed, stale or nonpassing evidence cannot authorize a release.
Do not use public audience messages to build gold under the metadata-only policy.

The operator owns review records, threshold approval and release authorization.
Revisit the rubric when audience/language/model scope changes.
