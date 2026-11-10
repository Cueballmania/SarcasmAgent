# Operations and release runbook

## Release sequence

1. Approve hosting/database plan, same-region connection, Langfuse destination/data
   policy, metadata retention, event SLO and request/spend limits. Keep automatic
   production deploys off. Do not provision duplicate resources for an existing app.
2. Verify candidate source/lock/runtime, complete required CI `checks`, review data,
   approve thresholds before the untouched holdout and run the capped candidate
   evaluation locally or on an authorized isolated preview.
   Use a clean checkout of that exact commit. Keep input, timeout and output-token
   settings consistent with deployment; relevant changes invalidate that evidence.
3. Consume the current passing revision/source/dataset/config-bound report checker.
   Run `uv run --locked --no-dev alembic upgrade head` using database-only settings
   against the approved database and record success. A schema mismatch returns 503;
   worker startup never creates or migrates tables.
4. Manually roll out the exact candidate. Verify external HTTPS, `/health`, one
   authorized synthetic classification, its committed audit UUID, matching
   Langfuse request/generation trace, usage and redacted content.
5. Perform an approved event-shaped test on isolated resources with explicit HTTP
   count/duration, model call/token/cost ceilings and pass/fail SLO. Include
   non-classification traffic, overload rejection and recovery; never flood or
   inject failures into shared/public resources.
6. Download final QR SVG/PNG, read both rendered images with a native phone camera,
   record decoded URL/device and reach the form from the audience network. Check
   keyboard/result/error/reflow and any required real assistive-technology pass.

No live quality, load, external trace or physical QR result is inferred from unit
tests. Automatic release is optional only after an explicitly approved policy
enforces both exact-revision CI and current reviewed quality gates.

## Audit and public limits

Every admitted HTTP kind is logged: pages/assets/health, invalid/unmatched routes,
rate rejection and classification. Initial pending commit precedes work; no
success is sent before final commit. Transactions never span provider latency.
Raw bodies/query strings/cookies/IPs/authorization are not persisted or logged.
Unmatched paths use a fixed route marker.

The app bounds streamed input to 16 KiB/2,000 characters, classification to 20
seconds, provider attempts to one and concurrent model slots to four by default.
Single worker/instance is required; multi-worker/instance scaling needs revisiting
process-local HTTP/model concurrency. Global model counters are atomic PostgreSQL
UTC-minute/day reservations and are not refunded after uncertain provider attempts.
Signed cookies provide fairness, not authentication; session resets cannot reset
global caps. Keep the signing key stable; rotate it deliberately if compromised.

Pre-audit saturation, storage outage, process death/pre-app rejection and deadline
interruption cannot promise complete/exactly-once auditing or billing. Explicit
non-success diagnostics and unavailable-audit counters expose those boundaries.
Cancelled/deadline failures have bounded tracked audit cleanup; aged pending rows
are later reconciled. Never show a label after a failed final audit write.

## Maintenance

Run these from the approved database environment. Both default to a bounded preview:

```bash
uv run --locked python -m app.maintenance reconcile
uv run --locked python -m app.maintenance purge
```

Review the exact UTC cutoff and eligible request/quota counts. Add `--apply` only
after checking target/policy and first-production backup/export precautions:

```bash
uv run --locked python -m app.maintenance reconcile --apply
uv run --locked python -m app.maintenance purge --apply
```

Reconcile after startup/incidents and periodically when pending-age monitoring
requires it. Trigger purge on the operator's approved retention cadence; no
scheduler or paid cron resource is implicitly installed. Batches default to
1,000 rows per table; repeat approved batches as needed. Concurrent reconciliation
is safe. Purge preserves active quota windows and evaluation datasets.
Copies/backups/exports follow approved retention, not indefinite preservation of
expired metadata.

## Monitoring and incidents

Use request UUIDs and trace IDs, not audience messages, for diagnosis. Keep database
and Langfuse dashboard access operator-only. Query bounded UTC periods:

```sql
SELECT state, http_status, error_code, count(*)
FROM audit_requests
WHERE started_at >= now() - interval '1 hour'
GROUP BY state, http_status, error_code;

SELECT label, count(*), percentile_cont(0.95) WITHIN GROUP (ORDER BY elapsed_ms)
FROM audit_requests
WHERE started_at >= now() - interval '1 hour' AND kind = 'classify'
GROUP BY label;
```

Watch request volume/completion/error counts, pending age, DB failures, Unknown
distribution, latency, nullable usage/cost and export degradation. Unknown drift
is not a gold-quality measurement. Health probes never call OpenAI and Langfuse
unavailability does not replace a valid label or block classification.

For database failure, stop/limit admissions and restore required connectivity/schema;
do not pretend missing rows exist. For provider failure/budget pressure, pause
public admissions at the operator level or reduce explicit caps; do not substitute
Unknown or enable SDK retries. For trace degradation, inspect safe exporter
diagnostics, project credentials/region and dashboard connectivity.

Uvicorn raw access logs are disabled; app diagnostics use safe codes/templates.
Hosted proxies/providers may have their own logging/retention outside app control.
SDK export filtering drops raw IO, exception events/status text and unapproved
attributes. Recheck actual locked exports and privacy notice after SDK changes.
The explicit application metadata allowlist is projected into native Langfuse
metadata after masking; arbitrary `sarcasm.*` and SDK metadata are not admitted.
Check the score ingestion channel too: it is separate from span masking.
Runtime contract/abstention/latency scores describe model attempts, not HTTP audit
commitment or ground-truth accuracy. For score names, linked experiment reports
and a short prepared demo, see the [observability guide](observability-demo.md).

## Recovery and secret safety

Use Render-managed keys/URLs and ignored local files; never place them in Git,
browser code, logs or evaluation reports. Disable unnecessary external database
access and use the approved tier's backup/export policy. Schema downgrade is
deliberately non-destructive: incompatible rollback requires an operator-reviewed
restore or roll-forward plan, not blindly dropping audit tables.
