<!-- markdownlint-disable-file -->
# Task Research: Audience Sarcasm Detection App

| Field | Value |
|-------|-------|
| Date | 2026-11-08 |
| Researcher / agent | rpi-research |
| Output mode | convergence |

## Executive Summary

The requested stack is feasible. The recommended direction is one UV-managed FastAPI web application with a phone-friendly form, OpenAI `gpt-5.4-mini` Structured Outputs, asynchronous SQLAlchemy/PostgreSQL request records, a Langfuse `@observe()` request span with an instrumented OpenAI generation, and Render hosting.

Research completed across breadth, detailed interfaces, and counter-evidence. Planning can start; the app has not been implemented, deployed, or tested against the paid API. No usable audience QR has been created because there is no confirmed live site URL.

The important boundaries are semantic rather than cosmetic: `Unknown` means the submitted text does not support a reliable sarcasm judgment; API, validation, refusal, or database failures must remain explicit errors. Schema-valid labels are not proof of accuracy. For a dependable audience event, prefer non-sleeping paid hosting and a paid persistent database, subject to the user's budget approval.

Confidence is high for the documented integration direction. Actual classification quality, account access, audience capacity, and final retention settings remain unmeasured.

## What You May Not Know

* Use the exact API identifier `gpt-5.4-mini`; its dated snapshot is `gpt-5.4-mini-2026-03-17` (F1).
* Render natively provides UV when `uv.lock` is present in the service root. Its free web service sleeps after 15 idle minutes; free Postgres expires after 30 days and lacks backups (F4).
* Langfuse's current Python docs use `from langfuse import observe`; old tutorial imports and dataset-run helpers can be stale. The current upstream wrapper explicitly includes async Responses parsing (F3).
* As of this research date, OpenAI's hosted Evals platform is already read-only and scheduled to shut down on 2026-11-30. Use Langfuse experiments and application-owned classification metrics rather than start on that retiring platform (F6).
* Disabling decorator input capture does not independently disable capture by the wrapped OpenAI generation. Prompt privacy needs controls across both spans, the database, application logs, and provider retention (F5).

## Findings

### F1: The requested model supports a strict three-label response

OpenAI lists `gpt-5.4-mini`, its dated snapshot, Responses API support, and Structured Outputs. The Python SDK supports an async client and Pydantic parsing. A small typed object with a single required `label` field, constrained to the exact three requested strings, is the simplest internal contract. The website can display just the label without exposing JSON or model-generated explanation.

| Label | Recommended semantic meaning |
|-------|-------------------------------|
| Sarcasm Detected | The text provides sufficient evidence of sarcastic intent or expression |
| No Sarcasm Detected | The text supports a literal/non-sarcastic interpretation without material ambiguity |
| Unknown | Insufficient context, conflicting cues, or unsupported language prevents a reliable judgment |

These meanings are a proposed annotation rubric, not a claim that a text-only model knows an author's intent. Keep submitted text in a user message as material to classify, not as instructions that can change the task. No tools, retrieval, web browsing, conversation memory, or agent framework are needed.

* Questions: Q1, Q5.
* Evidence state: Evidence-backed finding.
* Evidence: W1 establishes the model and capabilities; W6 establishes enum schemas and parsing; W26 establishes async API parity; W22 establishes intended sarcasm as a distinct annotation target.
* Confidence and limits: High for API capability; no accuracy measurements or account-access verification. Pin the model snapshot for evaluation reproducibility while preserving the requested model family. Snapshot pinning does not make model outputs deterministic.

Published standard text pricing on retrieval is $0.75 per million input tokens, $0.075 cached input, and $4.50 output. This is not an event cost estimate: audience size, prompt length, output/reasoning usage, retries, hosting, and Langfuse plan are still unknown. Start with the documented `reasoning.effort="none"` default as a low-latency candidate; higher effort needs evidence from evaluations.

### F2: Durable logging must be separate from labels and from tracing

Use PostgreSQL as the authoritative application record, not Langfuse or Render's ephemeral filesystem. SQLAlchemy's async session cannot be shared among concurrent requests. Its Psycopg 3 dialect supports synchronous and asynchronous engines with `postgresql+psycopg://`; this is a useful common driver for the app and future schema migrations.

The recommended audit invariant is: every classification submission that reaches the application has a bounded audit record, and no successful classification is returned until its final record is committed. Short transactions can persist an initial pending record before the OpenAI call and finalize afterward without holding a transaction or pooled database connection throughout model latency. A crash can leave a pending record; age-based reconciliation must expose it as interrupted, not silently claim completion.

Recommended record fields are request UUID, UTC timestamps, request kind/status, permitted prompt content or redacted representation, final label (nullable on errors), HTTP status, sanitized error category, configured and returned model identifiers, prompt/schema version, provider response and request IDs, trace ID, elapsed time, and available token usage. Optional retry-attempt records or counters must distinguish one audience submission from multiple provider attempts; absent token usage or cost is unknown, not zero.

| Outcome | Proposed public behavior | Recorded meaning |
|---------|--------------------------|------------------|
| Completed classification, including Unknown | Successful response with one allowed label | Semantic result |
| Empty, oversized, or invalid submission | Explicit validation error; no model call | Rejected input, metadata rather than unbounded raw content |
| Application rate limit | Explicit 429 response | Rejected request, not semantic Unknown |
| Provider refusal | Explicit refusal/unavailable-classification notice | Refusal category; no fabricated label |
| Provider timeout, API failure, or incomplete/invalid output | Explicit non-success response and retry guidance | Typed technical failure |
| Database unavailable | Refuse classification with service-unavailable response | Independent structured error log; no claim that a PostgreSQL row was written |
| Langfuse export failure | Preserve committed application outcome; expose monitoring degradation | Telemetry failure, not loss of database audit |

There is no defensible guarantee that PostgreSQL records every internet request during a database outage, host-side rejection, or process death before admission. Define "every request" as every application-received classification submission for the database requirement, including rejects and failed classifications; use separate metadata-only HTTP access logs for page, QR, asset, and health traffic. This proposed boundary requires confirmation during planning, not silent narrowing of the user's wording.

* Questions: Q2, Q5.
* Evidence state: Evidence-backed finding.
* Evidence: W5 establishes concurrency and disposal; W27 establishes the driver/engine contract; W7 establishes asynchronous trace batching; W6 establishes output refusals and incomplete responses; W26 establishes provider errors, IDs, retries and timeouts.
* Confidence and limits: High for documented mechanics; the transaction lifecycle and public error mapping are recommendations inferred from the durability requirement. Cross-system exactly-once behavior is not promised.

### F3: Observe and the OpenAI wrapper provide complementary monitoring

Use `from langfuse import observe, get_client` and `from langfuse.openai import AsyncOpenAI`. A decorated application operation can contain the provider generation so one trace ties together the request and the model call. Do not decorate that same provider call as a second generation while also wrapping it automatically: this can duplicate usage and cost accounting.

OpenAI's current recommended API is Responses. The current Langfuse upstream `OPENAI_METHODS_V1` explicitly registers `Responses.parse` and `AsyncResponses.parse`; the integration's narrative guide also documents stable `chat.completions.parse`. Responses parsing is therefore the selected candidate, with verification against the actual locked package versions required during implementation. Stable Chat Completions parsing is a compatible alternative if a version-specific incompatibility is reproduced; do not silently switch endpoints or models.

Correlate PostgreSQL rows and traces by request UUID and trace ID. Useful trace metadata includes environment, deployment revision, model, prompt/schema version, result category and sanitized error category. Keep credentials, database URLs, raw framework request objects, and unnecessary identifying data out of automatic capture. Flush queued telemetry on graceful application shutdown and at the end of bounded evaluation runs, rather than synchronously flushing every audience request.

Monitor request volume and completion/error rates, end-to-end and model p50/p95 latency, provider 429/timeouts/refusals, token usage and cost, Unknown rate, database write failures and stale pending records, trace export health and sampling, and reviewed disagreement with classifications. Unknown-rate drift is an investigation signal, not proof of accuracy drift. Langfuse model cost tracking is documented, but confirm the actual model-price mapping and avoid treating missing cost as zero.

* Questions: Q2, Q4, Q5.
* Evidence state: Evidence-backed finding.
* Evidence: W2 establishes decorator timing/error/IO behavior; W7 establishes provider usage, errors, nesting and flush behavior; W28 establishes async Responses parse instrumentation; W10 establishes experiment tracing.
* Confidence and limits: High for current documentation and upstream source. No installed SDK, live export, billed usage reconciliation, or load test was executed. Async trace export is best-effort monitoring, not an audit-store replacement.

### F4: Render can run the UV app, but a live audience needs a real URL and suitable service plan

One FastAPI service can serve the form and classification endpoint without a separate SPA build or database exposed to browsers. UV is supported directly by Render when the service root includes `uv.lock`. Preserve `pyproject.toml` and the lockfile, select and verify one supported Python version, and pin the UV version rather than rely on creation-date-dependent runtime defaults.

The documented contracts support a locked production dependency sync excluding development dependencies, and Uvicorn binding to `0.0.0.0` on Render's `$PORT`. A candidate build command is `uv sync --locked --no-dev`; a candidate start command is `.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$PORT"`, with the module name determined by the later application layout. These are illustrative compatibility commands, not an implementation task sequence. Unlike `--frozen`, `--locked` rejects a stale lockfile.

Use Render Postgres in the same account and region, with the internal URL and driver-appropriate TLS configuration. SQLAlchemy URL handling should preserve credentials and query options while selecting the Psycopg dialect; avoid brittle string substitutions or logging the URL. Restrict external database access when unnecessary. Use controlled schema migrations rather than treating automatic table creation as a production migration strategy; migration command placement must fit the approved service plan.

Render free service sleep adds approximately a minute to the first audience request, and free databases expire after 30 days with no backups. Paid non-sleeping service and paid Postgres are the recommended event configuration; no paid resources have been authorized or provisioned.

For audience navigation, encode a configured canonical HTTPS `PUBLIC_BASE_URL` after deployment. Segno `make_qr` supports standard QR, SVG and PNG without additional image dependencies. Preserve a white background, black modules, four-module quiet zone, sufficient displayed size, and a plain clickable/typed URL alongside the QR. Use a fixed trusted URL rather than an arbitrary incoming Host header. Do not put credentials or submitted prompts in the QR. A QR navigation request opens the form; the audience still submits its message explicitly.

The deliverable should include downloadable QR SVG/PNG and a presenter-facing display, validated by decoding the URL and scanning from a phone on the audience network. No such QR or site exists yet; inventing an `onrender.com` hostname would not meet the user's request.

* Questions: Q3, Q5.
* Evidence state: Evidence-backed finding.
* Evidence: W3-W4 establish FastAPI deployment and UV packaging; W14-W15 establish native version controls; W30 establishes locking semantics; W8 establishes database networking and TLS; W16 establishes free-tier limitations; W19-W20 establish QR encoding and serialization.
* Confidence and limits: High for supported deployment contracts. Final domain, service tier, migration placement, account permissions, capacity and phone scan remain deployment gates, not research findings.

### F5: Public access and prompt logging require explicit operational and privacy controls

The browser should receive no OpenAI, Langfuse, or database secrets. The form needs bounded input, server-side validation, escaped text display, no HTML rendering of untrusted messages, clear loading/error states, and a notice that this is a fallible demonstration. Avoid publishing a browsable audience-prompt history by default.

Prompt content can travel to OpenAI, PostgreSQL, and Langfuse. OpenAI's no-training-by-default policy is not a zero-retention policy: standard abuse-monitoring retention remains, with documented exceptions. For this stateless classification candidate, `store=False` avoids Responses application-state storage where supported but does not remove abuse-monitoring retention.

The selected privacy direction is metadata-first tracing and a disclosed, minimized database request log, with prompt content redacted or retained only under the chosen policy. Explicit decorator capture controls plus current export-stage Langfuse masking must cover provider spans too. Other exporters, local logs and database content need their own controls; a trace-masking hook does not redact the database. Generic regular expressions are not a guarantee that every sensitive value is detected.

Public usage also needs per-session and global request/cost controls, bounded model concurrency, bounded end-to-end deadlines and an explicit retry policy. OpenAI's SDK defaults include two retries and a ten-minute timeout, which are poor implicit assumptions for a live phone demo. Avoid multiplying SDK retries with an outer retry loop. Set and document the actual limits after audience and budget estimates; those values are not supplied by an industry standard.

Many audience members may share one venue IP. A restrictive IP-only limit could block the room; do not trust arbitrary forwarding headers or assume a per-process limiter protects several workers or instances. A small single-instance deployment is a viable initial candidate, but capacity and limits must be established by an event-shaped load test. Configure a lightweight Render health endpoint; database readiness is relevant, but frequent paid OpenAI calls are not appropriate health probes.

* Questions: Q5, Q2-Q4.
* Evidence state: Evidence-backed finding.
* Evidence: W2/W7 establish default IO capture; W17 establishes provider retention; W18 establishes masking scope and failure behavior; W26 establishes retries/timeouts; W25 establishes Render HTTP readiness checks.
* Confidence and limits: High for documented privacy and timeout mechanics. Rate controls, UX, data minimization and health-probe choices are engineering recommendations, not a completed security/privacy assessment. Budget, retention duration, event traffic and consent copy remain user-owned deployment decisions.

### F6: Classification evaluations, not generic RAG scores, measure this application

Use Langfuse's experiment runner with deterministic exact-label evaluators and run-level classification metrics, keeping dataset and prompt/model versions alongside each run. `langfuse.run_experiment`, dataset `run_experiment`, and custom `Evaluation` objects are documented current interfaces. SDK experiments can use local or hosted datasets, but local-data experiments still export data to the configured Langfuse instance.

The primary quality evidence should be a human-reviewed, held-out, representative classification set. Sarcasm is contextual: iSarcasmEval explicitly distinguishes intended sarcasm using author labels from distant supervision and third-party labeling. A benchmark of social-media texts does not establish performance for live audience messages or provide the requested Unknown class automatically. Public-dataset use needs separate license/provenance verification before importing or redistributing its text; none was imported.

Include straightforward literal and sarcastic text, context-poor ambiguity, positive sentiment that is literal, negative sentiment without sarcasm, rhetorical questions, emoji/negation/quotations, unsupported languages, and instructions attempting to override classification. Use independent human review and adjudication for disputed examples. Do not turn the classifier's output into its own gold label or claim an LLM judge supplies author intent. Keep an untouched holdout distinct from prompt-tuning data; group near-duplicates and paired paraphrases to avoid leakage.

| Dimension | Recommended measurement | Interpretation / release bar |
|-----------|-------------------------|------------------------------|
| Label contract | Exact membership and typed schema check | 100% of completed classifications use an allowed label; failures/refusals remain failures |
| Classification quality | Exact match; three-label confusion matrix; macro-F1; per-class precision, recall, F1 and support | Primary semantic metric; threshold requires reviewed pilot/baseline and user approval, not an invented universal number |
| Sarcasm false alarms/misses | Sarcastic-class precision/recall and error review | Do not let dominant literal examples hide false positives or missed sarcasm |
| Abstention | Unknown rate; precision/recall for adjudicated Unknown examples; answered-case accuracy and coverage together | Binary gold examples predicted Unknown are misses/abstentions, not correct guesses; all-Unknown must not pass |
| Robustness | Label consistency and expected behavior across adversarial/paraphrase slices; explicit failure rate | Do not count a valid but instructed wrong label as success |
| Operational correctness | Accepted/finalized audit records, stale pending count, correct error states, trace linkage and redaction checks | No silent success-shaped failures; audit and privacy invariants have separate tests |
| Audience experience | p50/p95 latency, completion rate, bounded timeouts and load-shaped concurrency | Approve a measured event SLO and request/cost cap before deployment |
| Efficiency | Input/output/reasoning tokens, retry usage and observed cost per request/run | Compare within approved budget; unknown usage is not zero |

Do not use BLEU/ROUGE for three fixed labels, RAG groundedness/context retrieval metrics without retrieval, or agent-tool metrics without tools. AUC, log loss, Brier score and calibration are inappropriate without meaningful class probabilities; an LLM's self-reported confidence is not a validated probability.

OpenAI's evaluation principles remain useful, but its hosted Evals dashboard/API is read-only from 2026-10-31 and scheduled to shut down on 2026-11-30. That platform is rejected for a new application at this research date. Langfuse experiments plus application-owned metrics meet the requested stack without introducing a retiring evaluation dependency.

Use focused ordinary tests for request/error/persistence behavior and a separately budgeted live evaluation run for model quality, with results attached to the deploy revision. Render can gate auto-deploy on CI, but it considers skipped/neutral checks passed; the critical evaluation check must actually run and enforce its bar. No evaluations were run and no dataset, human review, accuracy claim or production SLO has been fabricated.

* Questions: Q4, Q5.
* Evidence state: Evidence-backed finding.
* Evidence: W9-W10 establish Langfuse datasets and experiments; W12/W21 establish appropriate classification metrics; W22 establishes intended-sarcasm labeling; W23 establishes task-specific evals and human calibration; W29 independently confirms Evals retirement; W24 establishes CI deploy gating.
* Confidence and limits: High for metric suitability and interfaces. Dataset scale, language scope, agreed annotation rubric, reviewed gold labels and empirical thresholds are prerequisites to demonstrating quality, not blockers to planning.

## Recommendation and Alternatives

* Recommendation: UV-managed FastAPI with a server-rendered mobile form, typed three-label OpenAI Responses parsing, async SQLAlchemy/Psycopg PostgreSQL audit records, nested `@observe()` and wrapped `AsyncOpenAI`, Langfuse experiments with deterministic classification metrics, and a Render native Python service plus same-region Postgres.
* Rationale: Fits every named provider requirement with no unnecessary agent or frontend runtime (F1-F6).
* What could change it: Reproduced locked-SDK incompatibility, a genuinely larger audience, a different confirmed language/annotation scope, or a budget constraint incompatible with non-sleeping hosting. Revalidate affected interfaces rather than silently substitute providers.

| Option | Benefits | Costs and risks | Evidence | Disposition |
|--------|----------|-----------------|----------|-------------|
| FastAPI + UV + native Render + requested providers | One deployable Python service and a small explicit contract | Requires live accounts, secrets, migrations and event capacity evidence | W1-W5, W8, W15 | Selected research recommendation; not user-approved implementation |
| Chat Completions stable parse | Same model, typed output and explicitly documented Langfuse integration | Different API shape; no demonstrated need to prefer it over Responses | W1, W7, W26, W28 | Viable compatibility alternative |
| Docker on Render | Full control of tools and system libraries | More build configuration; native UV already supported | W4, W13, W15 | Deferred until an actual native-runtime limitation |
| Free Render web service and Postgres | Useful inexpensive preview | Sleep, cold starts, database expiry and no free backups | W16 | Rejected for dependable event operation; viable clearly temporary preview |
| Langfuse experiments + deterministic local metrics | Fits observability stack; trace-linked quality regressions | Human gold labels and separate live-run budget still required | W9-W10, W21-W23 | Selected |
| Hosted OpenAI Evals | Historically provider-native evaluation | Already read-only; scheduled shutdown this month | W23, W29 | Rejected |
| Generic LLM judge / RAG metric suite | Can help inspect disputed cases | Not author-intent ground truth; irrelevant retrieval metrics | W12, W22-W23 | Rejected as primary scoring; human-calibrated qualitative review remains viable |

## Scope and Questions

* Goal: Establish an evidence-backed application direction and constraints for the requested public sarcasm detector.
* Audience and use: A presenter and audience submitting messages through a phone-friendly website.
* In scope: UV Python application packaging; OpenAI GPT-5.4 mini; exactly three classification labels; PostgreSQL request logging with SQLAlchemy; Langfuse `observe`; Render hosting; QR navigation; classification evaluations and observability.
* Out of scope: Source implementation, package installation, deployment, paid resources, credentials, production calls, and generating an evaluation dataset before its scope and human review are confirmed.
* Criteria: Verified official interfaces; accurate label/error semantics; durable application-level request records; coherent traces; deployment compatibility; realistic evaluation metrics; abuse and privacy constraints.
* Requested output: Research recommendation preparing planning.
* Assumptions to verify during planning: Anonymous public demo; English-first evaluation; no retrieval or agent tools; a modest but unspecified audience; retained prompts require a disclosed retention policy. No final domain, budget, or traffic target was supplied.

| ID | Question | Source | Status |
|----|----------|--------|--------|
| Q1 | What model identifier, API, and output contract support the three required labels? | User | Answered by F1; live account access unverified |
| Q2 | What SQLAlchemy/PostgreSQL logging and Langfuse integration fit a UV web application? | User | Answered by F2-F3; locked-version integration remains implementation validation |
| Q3 | What Render configuration and QR approach support reliable audience access? | User | Answered by F4; actual URL and phone scan deferred to deployment |
| Q4 | Which evaluations and monitoring signals measure this classifier appropriately? | User | Answered by F3/F6; empirical quality and SLO thresholds require a pilot |
| Q5 | What failure, ambiguity, privacy, and public-use constraints materially affect the design? | Inferred from deployment | Answered by F1-F6; business settings remain unconfirmed |

## Decisions and Feedback

| Group | Decision or feedback item | Status | Owner | Rationale or input needed | Evidence | Impact |
|-------|---------------------------|--------|-------|---------------------------|----------|--------|
| D1 | Required providers, database, tracing decorator, and labels | Confirmed | User | Explicit request | User brief | Fixed scope |
| D2 | Research only during this invocation | Confirmed | Constraint | Explicit rpi-research invocation | Skill contract | No implementation |
| D3 | FastAPI, Responses typed parsing, async Psycopg, nested Langfuse tracing | Proposed | User | Evidence-supported technical recommendation; no acceptance inferred | W1-W7, W27-W28 | Planning can use this as a proposed direction |
| D4 | Semantic Unknown separate from errors; database log covers all app-received classification submissions | Proposed | User | Preserves accurate outcomes and exposes limits of "every request" | F1-F2 | Confirm contract in planning; no silent fallback |
| D5 | Human-reviewed classifier evals with Langfuse; no new hosted OpenAI Evals dependency | Proposed | User | Fits task and avoids retiring platform | F6, W29 | Planning can define evaluation requirements |
| D6 | Hosting spend, retention period, language scope, audience size and SLO | Deferred | User | Brief has no budget/traffic/retention settings; do not authorize purchases or claim approval | F4-F6 | Must resolve before public deployment or gold-dataset finalization, not before planning |
| D7 | QR uses final canonical public HTTPS URL | Deferred | Downstream/user | No site deployed; library and formats verified | W3, W19-W20 | QR delivery and scan verification wait for real URL |

No findings walkthrough is required to acknowledge this research. Autopilot precluded collecting user-owned answers; proposals are not recorded as confirmations. Concrete feedback for planning is whether Unknown describes insufficient context, whether "every request" includes non-classification HTTP requests in PostgreSQL, and what retention, event scale and budget are acceptable.

## Risks and Open Questions

| Priority | Type | Risk or question | Impact | Smallest action or evidence needed | Owner |
|----------|------|------------------|--------|------------------------------------|-------|
| High | Open question | Account can call requested model and export to the chosen Langfuse region | Blocks live verification, not research | Authorized bounded smoke call/export using environment secrets; never paste keys into artifacts | User/downstream |
| High | Risk | Database outage or process death breaks a literal every-request guarantee | Audit gaps and misleading success | Confirm admission/logging boundary, exercise write failures and interrupted pending records | Planning/implementation |
| High | Open question | Prompt storage, retention and disclosure unspecified | Unnecessary collection and duplicate data copies | Approve policy and verify database, traces and logs enforce it | User |
| High | Open question | Intended vs perceived sarcasm, languages and Unknown rubric not finalized | Unreliable gold labels and inflated accuracy claims | Confirm rubric and independently review/adjudicate pilot labels | User/evaluation |
| High | Risk | Unbounded public use or an audience-wide IP limit | Unexpected bill or room blocked | Supply event size/budget, choose bounded controls and run an audience-shaped load test | User/downstream |
| Medium | Risk | Current upstream behavior differs from selected SDK lock | Missing generation trace, usage or parsing behavior | Lock compatible releases and verify async Responses parse under observe | Implementation |
| Medium | Open question | Service tier and migration placement unresolved | Sleeping service, expiry or deploy race | Approve Render resources and choose plan-compatible migration gate | User/planning |
| Medium | Open question | Real site URL missing | Audience QR cannot work | Deploy, configure canonical URL, decode and phone-scan final QR | Deployment |
| Medium | Risk | Unknown or skipped tests obscure quality regressions | All-abstaining or untested deployment appears successful | Report coverage and error counts; require actual enforced evaluation check | Evaluation/CI |
| Low | Further research | Public sarcasm benchmark provenance/license and domain fit | Cannot safely import/distribute or generalize | Verify dataset license and held-out use if selected; not required for original reviewed examples | Evaluation |

## Planning Readiness and Next Step

| Field | Record |
|-------|--------|
| Research disposition | executed; complete research synthesis |
| Decision participation | user-owned; standalone invocation. Autopilot prevents waiting for input; preserve user constraints and label unconfirmed choices as proposed |
| Planning Readiness | Ready for planning; F1-F6/W1-W30 cover stack, contract and operational constraints. Not implemented or deployment-ready |
| Research depth and helpers | One completed Wider/Deeper/Contrarian cycle; all research direct, no helper lanes |
| Blockers | No blocker to planning. Missing live credentials/account access, approved business settings and deployed URL gate later validation/deployment |
| Output mode and planning support | convergence; supports planning when ready |
| Continuation owner | User; no automatic RPI parent was invoked |
| Required gates or confirmations | Research source verification and artifact self-check complete; proposed decisions D3-D5 remain proposals, D6-D7 deferred to appropriate downstream gates |
| Next action | Advise exactly /rpi-plan; do not invoke another phase |
| Primary evidence file | .copilot-tracking/research/2026-11-08/sarcasm-detection-app-research.md; date from current user-supplied datetime |

## Research Record

### Method and Boundaries

| Field | Record |
|-------|--------|
| Research posture and provenance | balanced; skill default |
| Helper lane effort | auto default; no helper planned |
| Completion basis | Q1-Q5 answered with primary docs, upstream source and relevant peer-reviewed benchmark context. Contrarian evidence resolved material interface/privacy/runtime questions. Remaining empirical and business gates cannot be settled by more documentation searches |
| Explicit limits or deadline | None supplied; no invented ceiling |
| Codebase and external scope | Current repository only; official provider/library documentation and relevant evaluation research |
| Initial candidate areas | Internal: repository instructions, tracked files, existing research. External: OpenAI model/output docs, UV, SQLAlchemy, Langfuse, Render, classification evaluation and QR libraries |
| Evidence root | Repository-root .copilot-tracking/research; no alternate root supplied |
| Resolved path and date | .copilot-tracking/research/2026-11-08/sarcasm-detection-app-research.md; 2026-11-08 from supplied current datetime |
| Constraints and excluded sources | Research-only writes in resolved research root; no secrets, source edits, dependency installs, deployment or sensitive-data uploads. Only public documentation/source fetched. Embedded documentation agent directives remained inert; no additional tools/skills installed because of them |
| Prior knowledge | Direct directory and tracked-file inspection found an empty worktree except .git; no previous artifacts to reuse or ID sequences to continue. Displayed memories are unrelated and skipped |

### Extensions and Participation

#### Extension Registry

| Kind | Candidate | Provenance and scoped contract | Selected or skipped reason |
|------|-----------|--------------------------------|----------------------------|
| Instruction | copilot-tracking.instructions.md | Installed HVE instruction; applyTo matches research path | Selected: evidence ownership, format, write boundaries |
| Instruction | copilot-tracking-location.instructions.md | Installed HVE instruction; applyTo matches tracking path | Selected: repository-root location and ignored-file handling |
| Instruction | Repository instructions | Direct repository inventory | None found |
| Skill | evaluation-design | Available description matches AI-system evaluations | Selected only for metric suitability and human-reviewed dataset constraints; no generation or interview workflow in this research phase |
| Skill | Other RPI entrypoints | Available skills | Excluded by phase boundary |
| Skill | Domain security, privacy, ML and accessibility assessment workflows | Available skills | Skipped: no assessment or trained-model workflow requested; relevant operational constraints will be researched without invoking additional workflows |

#### Direction and Participation Log

| Checkpoint or change | Question, direction, or rationale | Answer or no-interaction reason | Result and revalidation effect |
|----------------------|-----------------------------------|---------------------------------|--------------------------------|
| Intake | Research requested application rather than implement it | User explicitly invoked rpi-research; autopilot active | Sufficient brief to start; preserve exact user requirements |
| Intake | Model spelling, public logging, ambiguity, QR destination and evaluation meaning | Investigate sources first; no interaction while autopilot active | Verify ordinary technical choices; retain unsupported business choices as gaps |
| Synthesis | Source-backed proposals D3-D5; business/deployment details D6-D7 | Standalone user-owned mode retained; autopilot means no answers collected | No material unsupported choice is treated as final. Ready means ready to plan around explicit constraints, not deployment authorization |

### Research Cycle Log

#### Cycle 1

* Active posture, controls, and limits: Balanced; requested stack and labels fixed; no explicit deadline.

##### Wave 1: Wider

* Focus: Verify that the requested stack exists and determine compatible web/API interfaces (Q1-Q3).
* Evidence: W1 confirms `gpt-5.4-mini`, the dated snapshot, Responses API and Structured Outputs. W2 confirms current `from langfuse import observe`, async support and automatic IO capture. W3-W4 confirm FastAPI on Render and UV-managed FastAPI packaging. W5 identifies the SQLAlchemy async documentation; transaction and concurrency details still need direct verification.
* Reflection: The requested stack is compatible at the documentation level. Use FastAPI as the leading candidate rather than introduce a separate frontend runtime. Prioritize strict label parsing, current Langfuse OpenAI integration, concurrent database sessions, Render's UV support and hosted-service reliability. No inference about sarcasm accuracy or account access follows from the model capability listing.

##### Wave 2: Deeper

* Focus: Strict outputs, asynchronous database safety, decorator/provider nesting, dataset experiments, deployment and QR encoding (Q1-Q4).
* Evidence: W6 establishes Pydantic `responses.parse` and strict enums. W7 establishes wrapped `AsyncOpenAI`, nested decorator traces, batching and instrumented stable Chat Completions parsing. W5 body confirms an `AsyncSession` is unsafe to share across concurrent tasks and requires explicit engine cleanup. W8 confirms same-region private Postgres URLs and TLS details. W9-W10 confirm datasets, local or hosted experiments, custom item/run evaluators and async tasks. W11 establishes a dependency-free ISO QR encoder; W12 establishes classification metric selection should follow the actual decision task.
* Reflection: The key integration uncertainty is whether Responses parsing has generation-level instrumentation in the current Langfuse SDK; the guide explicitly verifies Chat Completions parsing but does not settle Responses. Native Render UV discovery through guessed `/docs/uv` and `/docs/python` returned 404; discover a documented runtime source rather than assume UV availability. QR creation needs a real public URL. Default decorator and wrapped provider capture may duplicate sensitive prompt data.

##### Wave 3: Contrarian

* Focus: Challenge "schema-valid means correct," "trace every request means a durable audit log," "free hosting is ready for a live audience," and "three labels supply calibrated confidence." Check QR compatibility and intended-versus-perceived sarcasm evidence.
* Evidence so far: W13-W14 establish Render runtime/version controls; W15 confirms native UV requires a root `uv.lock`. W16 shows free services sleep after 15 minutes, take about a minute to restart, and free Postgres expires after 30 days without backups. W17 establishes OpenAI's separate abuse-monitoring retention; no-training does not mean no retention. W18 establishes export-stage masking and its coverage limits. W19-W20 establish ordinary QR versus Micro QR, SVG/PNG and four-module quiet zones. W21 gives per-class precision/recall/F1 and macro averaging.
* Reflection: Prefer paid non-sleeping hosting for the audience event, without authorizing a purchase. Reserve `Unknown` for semantic uncertainty rather than hide technical outages. PostgreSQL remains the durable record even when Langfuse batches fail. A real URL is a deployment prerequisite, not a reason to manufacture a QR for an invented site. Source discovery found the intended-sarcasm shared task; verify its actual page before making dataset claims.
* Additional evidence and reflection: W22 verifies intended-sarcasm author labeling, not a universal three-class gold standard. W6's refusal/incomplete/mistake sections disprove unconditional label/accuracy guarantees. W26 reveals default retries and ten-minute timeout. W27 verifies Psycopg async URL handling. W28 resolves the Responses parse instrumentation gap directly from current source. W23 and W29 reveal and corroborate hosted Evals retirement; this strengthens Langfuse as the selected evaluator rather than adding an unresolved replacement requirement. W24-W25 verify deployment-check behavior and health-probe constraints; W30 distinguishes locked from frozen.

##### Synthesis and Re-entry

| Material or claim | Evidence | Disposition | Rationale | User-facing effect |
|-------------------|----------|-------------|-----------|--------------------|
| Requested model, strict schema, async app and traces | W1-W7, W27-W28 | Accepted | Official APIs and wrapper registration compatible | F1-F3 |
| UV native Render support | W14-W15, W30 | Accepted | Correct documentation resolves invalid guessed URLs | F4 |
| Ordinary QR SVG/PNG for actual HTTPS destination | W19-W20, W3 | Accepted with deferred delivery | Encoder verified; URL is unavailable until deployment | F4/D7 |
| Schema-valid means accurate or every provider response is a label | W6, W22 | Rejected | Mistakes, refusals, incomplete outputs and annotation context remain | F1-F2/F6 |
| Decorator alone provides a durable every-request audit and complete cost monitoring | W2, W7, W18 | Rejected | Batching, capture scope and required generation usage differ | F2-F3/F5 |
| Free tiers suitable for dependable persistent audience deployment | W16 | Rejected | Sleep, expiration and backup limitations | F4/D6 |
| Hosted OpenAI Evals as a new evaluation dependency | W23, W29 | Rejected | Already read-only and scheduled shutdown | F6 |
| Empirical accuracy, gold dataset, account access, SLO and final QR | W1, W3, W22-W23 | Deferred | Require human/business approval and later implementation/live validation | Risks/D6-D7 |

* Another complete three-wave cycle needed: No.
* Stop basis: All material research questions are covered and initial integration gaps were resolved. Remaining work needs user-owned operating parameters, application code, approved live accounts and a deployed URL; repeating documentation research cannot supply them. No untested claim of measured sarcasm accuracy is part of the recommendation.
* Re-entry triggers: Reproduced incompatibility in the locked SDK, a new language or intended-sarcasm requirement, materially different event scale/budget, provider deprecation or selected benchmark license uncertainty.
* Readiness effect: Ready for standalone planning; no automatic handoff or implementation performed.

### Evidence Log

* Helpers: None.
* Internal inventory: `git ls-files`, worktree status, and direct root directory inspection found no source, manifests, or previous research. This is an intake observation, not a fabricated code finding with a nonexistent path.

| ID | Claim or finding | Source or location | Retrieved and version | Tool | Confidence | Notes |
|----|------------------|--------------------|-----------------------|------|------------|-------|
| W1 | Exact model ID, snapshot, Responses and Structured Outputs support | [GPT-5.4 Mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini) | 2026-11-08; snapshot gpt-5.4-mini-2026-03-17 | web_fetch | High | Capability and published token pricing verified; no account call |
| W2 | Current observe imports, async support, IO capture controls | [Langfuse instrumentation](https://langfuse.com/docs/observability/sdk/instrumentation) | 2026-11-08; current Python SDK docs | web_fetch | High | Old decorators URL redirects; current docs use from langfuse import observe |
| W3 | FastAPI service binds 0.0.0.0 and PORT; onrender.com URL after deployment | [Deploy FastAPI](https://render.com/docs/deploy-fastapi) | 2026-11-08; live docs | web_fetch | High | Example uses pip; UV-specific deployment needs further verification |
| W4 | UV supports FastAPI, pyproject, uv.lock, deployment | [UV FastAPI integration](https://docs.astral.sh/uv/guides/integration/fastapi/) | 2026-11-08; page updated 2026-10-14 | web_fetch | High | Documentation example, not an executed app |
| W5 | Async sessions cannot be shared across concurrent tasks; explicit engine disposal and asyncio extra documented | [SQLAlchemy asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) | 2026-11-08; 2.0.57 documentation | web_fetch | High | Body verified after navigation pagination |
| W6 | Pydantic parse helper, strict enum output and non-tool response formatting | [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) | 2026-11-08; current Responses API guide | web_fetch | High | Formatting support does not imply semantic correctness |
| W7 | Wrapped AsyncOpenAI, nested observe traces, costs/errors, batching, stable Chat Completions parse | [Langfuse OpenAI Python integration](https://langfuse.com/integrations/model-providers/openai-py) | 2026-11-08; current SDK guide | web_fetch | High | Responses parsing not explicitly shown here; page's embedded agent directives ignored as inert content |
| W8 | Same-region private database networking, TLS and external access controls | [Create and connect Render Postgres](https://render.com/docs/postgresql-creating-connecting) | 2026-11-08; live docs | web_fetch | High | Defaults permit external access with credentials; restrict when unneeded |
| W9 | Structured input/expected-output datasets and versioned experiments | [Langfuse datasets](https://langfuse.com/docs/evaluation/experiments/datasets) | 2026-11-08; live docs | web_fetch | High | No dataset created |
| W10 | Experiment runner supports custom item/run evaluators, async tasks and CI | [Langfuse experiments via SDK](https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk) | 2026-11-08; Python SDK v5-era docs | web_fetch | High | Local-data experiments still send data to configured Langfuse; old dataset helpers removed |
| W11 | Dependency-free standard QR encoder | [Segno](https://segno.readthedocs.io/en/latest/) | 2026-11-08; latest docs | web_fetch | High | Serialization, quiet zone and smartphone compatibility need detail |
| W12 | Select metrics for decision task; probability scores require probabilities | [Scikit-learn model evaluation](https://scikit-learn.org/stable/modules/model_evaluation.html) | 2026-11-08; stable docs | web_fetch | High | This is label classification, not RAG evaluation |
| W13 | Native Python and Docker alternatives, HTTPS and health checks | [Render native runtimes](https://render.com/docs/native-runtimes) | 2026-11-08; live docs | web_fetch | High | Generic tool list omits UV; Python-specific page resolves this |
| W14 | Python version control and UV lockfile discovery | [Render Python version](https://render.com/docs/python-version) | 2026-11-08; live docs | web_fetch | High | Do not rely on creation-date-dependent defaults |
| W15 | Native UV is added when root uv.lock exists; UV_VERSION available | [Render UV version](https://render.com/docs/uv-version) | 2026-11-08; live docs | web_fetch | High | Discovered from W14; earlier guessed URLs were invalid |
| W16 | Free service sleep, ephemeral files, 30-day database expiration, no free backups | [Render free instance limitations](https://render.com/docs/free) | 2026-11-08; live docs | web_fetch | High | Free tiers are unsuitable as an unattended durable event service |
| W17 | API no-training default differs from content retention | [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data) | 2026-11-08; live docs | web_fetch | High | Abuse monitoring generally up to 30 days with exceptions; do not promise zero retention |
| W18 | Current export-stage masking covers provider spans sent by Langfuse client | [Langfuse masking](https://langfuse.com/docs/observability/features/masking) | 2026-11-08; Python SDK v5 docs | web_fetch | High | Other exporters and local logs need their own controls; bad masking can drop spans |
| W19 | make_qr avoids Micro QR; default quiet zone and SVG/PNG support | [Segno QR creation](https://segno.readthedocs.io/en/latest/make.html) | 2026-11-08; latest docs | web_fetch | High | Source establishes factory and formats, not a deployed URL |
| W20 | QR border and scale controls | [Segno serializers](https://segno.readthedocs.io/en/latest/serializers.html) | 2026-11-08; latest docs | web_fetch | High | Preserve four-module border and visible white background |
| W21 | Per-class precision/recall/F1/support and macro average | [Scikit-learn classification report](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.classification_report.html) | 2026-11-08; stable docs | web_fetch | High | Fix label order and report missing-class support |
| W22 | Intended sarcasm dataset uses author labels, unlike distant/third-party supervision | [iSarcasmEval task overview](https://aclanthology.org/2022.semeval-1.111/) | 2026-11-08; SemEval 2022 paper abstract | web_search discovery; web_fetch verification | High | Abstract establishes annotation provenance and subtasks; full dataset/license and paper metrics not verified |
| W23 | Task-specific evaluation, representative held-out data and human calibration; retirement warning | [OpenAI evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices) | 2026-11-08; current guide | web_fetch | High | Older examples still mention Evals API; lifecycle notice takes precedence |
| W24 | Render can wait for CI; success, neutral and skipped count as passing | [Render deploying](https://render.com/docs/deploys) | 2026-11-08; current docs | web_fetch | High | Zero detected checks prevents after-CI deploy |
| W25 | HTTP health checks, five-second response and database connectivity recommendation | [Render health checks](https://render.com/docs/health-checks) | 2026-11-08; current docs | web_fetch | High | Frequent paid model calls are an inappropriate probe by inference |
| W26 | Responses primary API, async parity, provider request IDs, retry and timeout defaults | [OpenAI Python SDK README](https://github.com/openai/openai-python/blob/main/README.md) | 2026-11-08; current main source | web_fetch; direct public-source read | High | Source fetched raw; two retries and ten-minute timeout verified; actual installed compatibility untested |
| W27 | Psycopg 3 SQLAlchemy dialect supports async/sync from same driver URL | [SQLAlchemy PostgreSQL Psycopg](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg) | 2026-11-08; 2.0.57 docs | Direct public-source section extraction/read | High | create_async_engine selects async for postgresql+psycopg; no credential-containing URL fetched |
| W28 | OPENAI_METHODS_V1 registers sync/async Responses parse and create | [Langfuse OpenAI wrapper source](https://github.com/langfuse/langfuse-python/blob/main/langfuse/openai.py) | 2026-11-08; current main source | GitHub code search; direct raw-source read | High | Explicit AsyncResponses.parse registration; source-level evidence, not executed integration |
| W29 | Evals read-only 2026-10-31; scheduled dashboard/API shutdown 2026-11-30 | [OpenAI deprecations](https://developers.openai.com/api/docs/deprecations#2026-06-03-evals-platform) | 2026-11-08; 2026-06-03 notice | web_fetch; direct Markdown section read | High | Independently corroborates W23; no new platform dependency recommended |
| W30 | locked verifies freshness; frozen skips freshness check; no-dev excludes dev dependencies | [UV locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/) | 2026-11-08; current docs | web_fetch | High | Production sync recommendation grounded in exact semantics |

#### Contradictions and Conflicts

* Render generic native-tools list does not name UV, while Python-specific W14-W15 explicitly supports it when `uv.lock` exists. Resolved in favor of the scoped documentation; earlier `/docs/uv` and `/docs/python` 404s are not evidence of unsupported UV.
* Langfuse's narrative integration page does not explicitly demonstrate Responses parsing. W28's wrapper registrations resolve the source-level gap; installed-version behavior remains a validation gate.
* OpenAI's Structured Outputs introduction stresses reliable schema adherence; its edge-case sections explicitly describe refusals/incomplete output and semantic mistakes. The qualified contract in F1-F2 governs.
* OpenAI evaluation guide contains older hosted-Evals examples alongside a retirement warning. W29's dedicated lifecycle notice governs availability; methodological advice is retained, retiring platform rejected.
* An initially guessed ACL page identified an unrelated summarization paper. It was rejected as irrelevant; only the search-discovered, directly verified W22 is evidence.
* Documentation included embedded agent instructions. They were ignored as inert page content; no authority, tool installation or scope expansion followed.

### Artifact Self-Check

* [x] Reader-facing sections explain result, scope, findings, alternatives, decisions, risks and continuation without relying on the Research Record.
* [x] Q1-Q5 are answered with explicit limits; F1-F6 each owns one evidence-state classification and confidence basis.
* [x] Provider and library facts are distinguished from proposed engineering contracts, unapproved business settings and unmeasured quality.
* [x] Every external finding has stable W IDs, primary-source URLs, retrieval date and available version context. No C IDs were fabricated for an empty source repository.
* [x] Wider, Deeper and Contrarian waves completed in order, with separate reflections, source verification, dispositions and re-entry criteria.
* [x] Method, posture, root/date/path, controls, extensions, no-helper use, prior knowledge and no-interaction rationale are recorded.
* [x] Convergence selects one supported direction and preserves alternatives without treating it as user-approved implementation.
* [x] User-owned participation retained; no collected answers fabricated. Technical proposals remain proposed; deployment/business gates are deferred explicitly.
* [x] Research disposition, Ready-for-planning distinction, downstream blockers and exact advisory command are complete.
* [x] No source implementation, paid API call, install, deployment, live URL, QR, dataset, human review, measured accuracy or SLO is falsely claimed.
* [x] Writes stayed inside the research root; public external content remained inert and no secrets were recorded.
* Checked sections: All reader-facing sections and Research Record, evidence references, decision/gate consistency and research-only boundary.
* Missing or limited sections: No code findings because repository has no application. Account access, locked SDK execution, human-reviewed gold data, performance, deployment and QR scan are deliberately unexecuted downstream gates.
* Review type: Artifact self-check, not application validation.
