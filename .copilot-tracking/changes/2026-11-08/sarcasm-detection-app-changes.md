<!-- markdownlint-disable-file -->
# RPI Changes: Audience Sarcasm Detection App

## Metadata

* Task ID: `sarcasm-detection-app`
* Related plan: [.copilot-tracking/plans/2026-11-08/sarcasm-detection-app-plan.md](../../plans/2026-11-08/sarcasm-detection-app-plan.md)
* Implementation date: `2026-11-08`

## Execution Status

* Status: Partial; blocked on user/operator-owned live release.
* Declared invocation scope: Full plan.
* Completed scope markers: `P01`, `P02`, `P03`, `P04`; `P01-T01`, `P01-T02`, `P02-T01`, `P02-T02`, `P02-T03`, `P03-T01`, `P03-T02`, `P04-T01`, `P04-T02`, `P05-T01`.
* All remaining active-plan markers: `P05`, `P05-T02`.
* Status basis: Ten implementation tasks and all local checks complete. User reports Render variables set and main connected; live access/configuration and release evidence remain unobserved. No secrets inspected or copied.

## Execution Summary

Implemented the full application, evaluation harness, CI and deployment configuration with offline verification. No commit, push, resource purchase, production migration, deployment or paid API call was performed. Actual Render/hosted-CI access, canonical endpoint, reviewed gold data/thresholds, approved live caps and physical phone scanning remain user/operator-owned release inputs.

## Completed Work

### Reproducible Python foundation

* Related task: `P01-T01`.
* Files: [pyproject.toml](../../../pyproject.toml), [uv.lock](../../../uv.lock), [.python-version](../../../.python-version), [app/main.py](../../../app/main.py), [.env.example](../../../.env.example), [.gitignore](../../../.gitignore).
* Behavior: Python 3.12.12, locked runtime/dev/evaluation groups, importable FastAPI entry point; secret/editor artifacts ignored. No provider calls at import.
* Validation: Passed `uv lock --check`, locked sync, runtime-only app/maintenance imports, Ruff lint and format. Locked OpenAI 2.54.0 and Langfuse 3.15.0 integrations verified with actual SDKs and fake transports.

### Typed labels and validated operating settings

* Related task: `P01-T02`.
* Files: [app/contracts.py](../../../app/contracts.py), [app/config.py](../../../app/config.py), [tests/test_config.py](../../../tests/test_config.py).
* Behavior: Three exact enum labels; stable safe errors; bounded and relationally validated settings, production-explicit quotas, canonical URL validation, injected secret-safe DB-only settings.
* Validation: Four focused configuration cases pass, including invalid ports/hosts/whitespace and credential-safe canonical URL errors. Pytest root import and fixture loop scope explicitly configured.

### Durable audit and atomic quota schema

* Related task: `P02-T01`.
* Files: [app/database.py](../../../app/database.py), [app/maintenance.py](../../../app/maintenance.py), [migrations/env.py](../../../migrations/env.py), [migrations/versions/0001_audit.py](../../../migrations/versions/0001_audit.py), [tests/test_postgres.py](../../../tests/test_postgres.py).
* Behavior: Versioned metadata-only audits, independent short sessions, atomic minute/day/session reservations with rollback on rejection; dry-run-first bounded stale/expiry maintenance, no provider clients or destructive downgrade.
* Validation: Isolated real PostgreSQL migration/lifecycle, schema mismatch, concurrent quota/restart, rollback fairness and preview/concurrent reconciliation/retention cases pass. Test migrations use only a unique run-owned schema.

### Typed provider calls and privacy-filtered tracing

* Related task: `P02-T02`.
* Files: [app/classifier.py](../../../app/classifier.py), [app/tracing.py](../../../app/tracing.py), [tests/test_classifier.py](../../../tests/test_classifier.py).
* Behavior: Fixed GPT-5.4 mini snapshot, strict Responses parsing, one attempt, no application-state storage, observe span plus exactly one generation; public OTel export-copy filtering strips raw IO/error events/status descriptions while retaining safe error codes/levels and failure trace IDs. SDK log filtering also applies to pre-existing root handlers.
* Validation: Six actual locked-SDK cases pass; synthetic marker absent in exported attributes for success/refusal/incomplete/invalid label/provider error/timeout and in SDK diagnostics with pre-existing logging handlers. Usage/request/trace linkage verified; no live APIs contacted.

### Bounded all-HTTP admission and truthful responses

* Related task: `P02-T03`.
* Files: [app/lifecycle.py](../../../app/lifecycle.py), [app/services.py](../../../app/services.py), [app/main.py](../../../app/main.py), [tests/test_audit_api.py](../../../tests/test_audit_api.py).
* Behavior: Pending audit before bounded streamed-body handling; buffered success only after final commit; all-HTTP nonwaiting limits, persistent model quotas, timed signed cookies with derived quota keys, bounded cancellation cleanup and readiness without model probes. Pre-admission overload diagnostics are rate-coalesced and rejection delivery is timeboxed.
* Validation: API and isolated PG cases pass, including initial/final audit outage, parser/oversize/unmatched requests, all-HTTP saturation, provider cancellation/slot recovery and one combined DB/log/actual-export privacy-marker sweep.

### Audience form and actual interactive browser behavior

* Related task: `P03-T01`.
* Files: [app/templates/index.html](../../../app/templates/index.html), [app/static/app.js](../../../app/static/app.js), [app/static/app.css](../../../app/static/app.css), [tests/test_web_qr.py](../../../tests/test_web_qr.py).
* Behavior: Phone-first form with native controls, pending/exact-label/error regions, safe text insertion, same-origin submission, no duplicate active UI request and explicit processing/fallibility notice.
* Validation: Real headless Chromium at 320/1024 pixels passed keyboard focus, disabled/loading, successful Unknown, distinct injected service failure, no console errors and no horizontal overflow. Static/API checks passed. No physical phone or real AT attestation claimed.

### Canonical presenter QR downloads

* Related task: `P03-T02`.
* Files: [app/qr.py](../../../app/qr.py), [app/templates/presenter.html](../../../app/templates/presenter.html), [tests/test_web_qr.py](../../../tests/test_web_qr.py).
* Behavior: Presenter page plus standard QR SVG/PNG for validated configured HTTPS root; black-on-white four-module quiet zone, readable destination and downloads; missing URL never falls back to request Host.
* Validation: Both response formats and encoder arguments tested with reserved synthetic URL; actual live/device decoding remains `P05-T02`.

### Reviewed-data evaluation and revision-bound release gating

* Related task: `P04-T02`.
* Files: [evals/contracts.py](../../../evals/contracts.py), [evals/metrics.py](../../../evals/metrics.py), [evals/run.py](../../../evals/run.py), [evals/rubric.md](../../../evals/rubric.md), [tests/test_eval_metrics.py](../../../tests/test_eval_metrics.py).
* Behavior: Reviewed-data/split contracts, explicit paid authority/caps, conservative pre-dispatch reserves, Langfuse item/run evaluators and shared scikit-learn aggregates; errors/Unknown remain in denominators and empty/all-abstention/missing-class/stale/fixture evidence cannot pass. Missing SDK-isolated latency is null, disclosed and non-passing, never a fabricated timeout measurement.
* Validation: Eight synthetic metric/gate cases passed, including actual mocked Langfuse experiment SDK with three bounded fake provider calls and filtered exports. No actual gold dataset, review claim, thresholds or model accuracy generated.

### Integrated regression and continuous checks

* Related task: `P04-T01`.
* Files: [.github/workflows/ci.yml](../../../.github/workflows/ci.yml), [tests/conftest.py](../../../tests/conftest.py), [pyproject.toml](../../../pyproject.toml), [tests/](../../../tests/).
* Behavior: Required `checks` workflow provisions isolated PostgreSQL and Chromium, runs locked ordinary checks without live keys, fails absent prerequisites/zero tests and verifies production-only sync. Local fixtures own and clean their test instances/schemas.
* Validation: Final local suite passes all 40 independently collected cases in six canonical files, including actual PostgreSQL and headless Chromium. Lock/lint/format and GitHub Actions schema checks pass. Hosted GitHub execution is unobserved and must pass for the published candidate before release.

### Existing-service Render configuration and operator runbook

* Related task: `P05-T01`.
* Files: [render.yaml](../../../render.yaml), [.env.example](../../../.env.example), [README.md](../../../README.md), [docs/operations.md](../../../docs/operations.md).
* Behavior: Secret-free single-instance native service reference with automatic deploy off; existing-service build/start/health/environment instructions avoid duplicate provisioning. Operator-controlled migrations, preview-first retention/reconciliation, safe diagnostics, incident handling and revision/quality gates are documented.
* Validation: Blueprint passes Render's documented [schema](https://render.com/schema/render.yaml.json). Exact `uv sync --locked --no-dev` passes; final app/maintenance imports succeed without pytest/Ruff/scikit-learn/Playwright/pgserver. Selected development groups restored afterward. Shipped files contain no tracking-artifact references.

## Implementation-Time Plan Updates

### Existing Render setup and credential safety

* Affected plan areas: Confirmed User Direction, `D5`, `D6`, `P05-T02`.
* Triggering evidence: User reports environment variables configured in Render and main connected.
* Decision: Implement now; do not infer completed deployment, quality evidence or spending approval.
* Local observation: UV exists; Docker and PostgreSQL executables are unavailable. Existing user [.gitignore](../../../.gitignore) excludes the `.env` pattern; preserve it and add editor-swap protections without reading secret/editor files.
* Reconciliation: Implementation scope/state added to plan; original critique retained.

### Locked tracing privacy and isolated test-server clarification

* Affected markers: `P02-T01`, `P02-T02`, `P04-T01`.
* Evidence: Locked Langfuse 3.15.0 supports instrumented Responses parse but lacks the research's newer export-mask hook. Public OpenTelemetry `TracerProvider.add_span_processor`/`ReadableSpan` interfaces permit a sanitizing processor wrapper before export without private SDK mutation.
* Decision: Preserve requested decorators/provider wrapper; use public OTel span-copy filtering plus SDK IO masking and verify actual exports. No silent provider/API substitution.
* Isolation: Optional non-production `local-postgres` group uses pgserver's macOS wheel for a unique test-only local PostgreSQL instance, stopped/cleaned after tests. CI uses its separately provisioned PostgreSQL service.
* Source: `https://pypi.org/project/pgserver/` documents macOS wheels and explicit test cleanup; no shared host service installation.
* Planning/critique state: Evidence-backed implementation clarification; existing privacy/isolated-PG requirements unchanged.

### Functional browser verification tooling

* Affected markers: `P03-T01`, `P04-T01`.
* Evidence: System Node is unavailable; HTML checks alone do not decide keyboard/loading/error behavior.
* Local judgment: Add optional non-production Python Playwright group and task-local headless Chromium, strictly for interactive viewport/form checks, not an extra shipped frontend or screenshot-only stack. No system-wide browser/service installation.

### Final release guidance and evidence reconciliation

* Affected markers: `P04-T01`, `P05-T01`, `P05-T02`.
* Classification: Implementation-only annotations and ordinary local correctness judgment; no scope/architecture/requirement change or new user approval.
* Completed safeguards: Canonical URL parser rejects invalid hosts/ports/control whitespace; failure trace linkage, pre-existing-handler sanitization, bounded overload handling and unknown-latency disclosure preserve the original contracts.
* Guidance: `P05-T02` now points to the completed typed dataset/run contracts, release checker and existing-service operations instructions. Clean exact-candidate checkout and matching classification settings are documented.
* Reconciliation: Ten task entries and checked markers agree. `P05`/`P05-T02` remain unchecked; hosted CI, live quality/load/migration/deployment/trace/device evidence is not manufactured. Planning readiness and historical resolved critique remain unchanged.

## Business Alignment

* None.

## Validation Record

| Check | Scope | Status | Evidence or reason |
|-------|-------|--------|--------------------|
| `uv lock --check` | Final locked project | Passed | 72 locked packages; no lock edits required |
| Ruff lint/format | Final source | Passed | All checks pass; 32 Python files formatted |
| `uv run --locked --group eval --group browser --group local-postgres pytest --local-postgres -q` | Six canonical test files | Passed | 40 cases; final run 34.91 seconds, actual isolated PostgreSQL and headless Chromium |
| PostgreSQL isolation/migrations/quotas/maintenance | Real database | Passed | Unique temporary server and run-owned schemas; migrations repeated, concurrent/restarted admission and bounded preview/apply verified |
| `uv sync --locked --no-dev` and direct runtime imports | Exact Render build | Passed | App/maintenance import; development/eval/browser/test-server dependencies absent; local selected groups restored |
| GitHub Actions and Render JSON schemas | Deployment configuration | Passed | Isolated `check-jsonschema` tool; official Render schema endpoint and built-in GitHub workflow schema |
| Secret ignores and whitespace | Worktree | Passed | Existing `.env` ignore preserved; swap/environment/venv ignored, example included; `git diff --check` clean |
| Shipped-reference sweep | App/evals/migrations/tests/CI/README/operations/Blueprint | Passed | No tracking-artifact paths shipped |
| Artifact links/checklist reconciliation | Plan/changes/README/operations/evaluation guide | Passed | Links resolve; 16 unique markers, ten completed task entries, only P05/P05-T02 unchecked; document whitespace clean |
| Hosted candidate CI | Published revision | Unavailable | No commit/push performed; local passing checks are not a claimed GitHub run |
| Paid/live/model/Render/phone verification | `P05-T02` | Unavailable | Endpoint/access, reviewed gold/thresholds and approved live/load/device evidence not supplied; no paid calls authorized |

## Pre-Review Reconciliation

* Implementation execution: Partial for declared full-plan scope; `P01`-`P04` and `P05-T01` locally complete.
* Review readiness: No full-plan handoff while `P05-T02` remains unchecked. Standalone invocation does not start Review.
* Checklist, ten completed-work entries, validation, remaining work and handoff agree. Business Alignment and unrelated follow-up items are None.

## Blockers

* `P05-T02`, owner User/operator: Record authorized resources/configuration/endpoint and exact-candidate hosted CI, reviewed gold/thresholds, approved capped quality/load runs, migration/deployment/audit/trace evidence and both physical QR scans. Reported credentials/main connection alone do not clear these gates. Affected live work cannot continue until those inputs/permissions are recorded.

## Remaining Work

* `P05` / `P05-T02` only: Authorized live candidate release and final audience QR evidence. No executable local implementation work remains; no deployment/quality success is claimed.

## Follow-Up Items

* None.

## Return-to-Caller State

* Full-plan result is Partial/Blocked for live release; user/operator is standalone continuation owner. No commit, push, resource purchase or live deployment triggered. Complete the documented existing-service and reviewed/capped release steps before claiming audience-ready delivery.
