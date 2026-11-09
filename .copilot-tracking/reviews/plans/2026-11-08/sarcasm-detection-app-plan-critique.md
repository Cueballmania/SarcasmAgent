<!-- markdownlint-disable-file -->
# RPI Plan Critique: Audience Sarcasm Detection App

## Metadata

* Task ID: sarcasm-detection-app
* Critique date: 2026-11-08
* Plan: .copilot-tracking/plans/2026-11-08/sarcasm-detection-app-plan.md
* Critique execution: Complete
* Critique depth: standard
* Depth provenance: default; user requested planning, not deep critique or a skip
* Critique type: initial
* Earlier critique: Not applicable

## Inputs and Criterion Boundary

* Caller requirements: UV Python app, OpenAI GPT-5.4 mini, exact three labels, PostgreSQL/SQLAlchemy request logging, Langfuse observe tracing, Render audience site, QR navigation, industry-appropriate evaluation and observability.
* Research: .copilot-tracking/research/2026-11-08/sarcasm-detection-app-research.md; F1-F6, D1-D7, W1-W30.
* Plan: P01-P05; eleven tasks; FR-001 through FR-012; NFR-001 through NFR-008; planned technical assumptions D2-D4, user-owned release inputs D5-D6, workflow setting D7.
* Boundary: Complete supplied plan and research only; assess credibility, implementation coverage, evidence, dependencies and material risk. No production code exists to assess. No open-ended external research, no runtime tests and no plan/research edits by the critique.
* Test boundary: Producer-owned focused tests integrated by P04-T01; removals none; at most six canonical test files/40 ordinary collected cases and two opt-in live entrypoints; live model quality is distinct from deterministic tests.

## Lens Assessments

| Lens | Scope | Reasoning effort and source | Status | Candidates |
|------|-------|-----------------------------|--------|------------|
| Coverage | All task Goals/Requirements and FR/NFR goals | low; selected default standard lens effort | Complete | Four candidates adopted into PC-001 through PC-003; five rejected: NFR-003 already assigns targeted deadline tests; range citations are permitted; local/manual usability and live load have owners; P05-T02 depends on P04-T01 transitively |
| Evidence | All plan claims, decisions, Details/References and supplied research | medium; selected default standard lens effort | Complete | Four candidates adopted into PC-004 through PC-006; four rejected: user wording supports broad audit scope though divergence needs disclosure; research F1 records reasoning default; Alembic/metric-library selection is local judgment and runner authorship is not handmade-metric mandate; explicit version selection already covers UV pinning |
| Executability | All phases/tasks, dependencies, tools, test budgets and release gates | medium; selected default standard lens effort | Complete | Six candidates adopted/merged into PC-001, PC-003, PC-006 through PC-009; six rejected: test-cap overflow is an estimate not a demonstrated conflict; producer ownership already applies; reproduced incompatibility already requires replanning; threshold inequality is testable; runtime pin selection is permitted local judgment; shared HTTP status is valid with distinct error codes |
| Risk | All material public, shared-system, data, budget and irreversible-action risks | medium; selected default standard lens effort | Complete | Six candidates adopted/merged into PC-001, PC-002, PC-003, PC-010, PC-011. Scope-corrected: blanket omission/sampling of HTTP kinds conflicts with user's broad logging requirement; DB readiness is a deliberate critical-dependency check, not itself a defect. Langfuse destination/notice choices must be explicit release inputs |

## Coverage Assessment

| Requirement, research, phase, or task ID | Coverage | Evidence or concern |
|-----------------------------------------|----------|---------------------|
| FR-001-FR-003, FR-006-FR-009; NFR-001-NFR-003/NFR-006 | Covered with identified refinements | Typed model/error contracts, async traces, UI/QR, bounded configuration; PC-004/PC-005/PC-007/PC-008 refine provenance and method |
| FR-004, FR-007; NFR-003-NFR-005 | Partial | Classification admission exists but all-HTTP audit traffic needs bounded pre-audit backpressure: PC-010 |
| FR-005; NFR-004 | Partial | Maintenance promised without executable/preview/operator mechanism: PC-003 |
| NFR-005 | Partial | Cross-surface marker check and notice/destination gate: PC-002 |
| FR-010-FR-011; NFR-007-NFR-008 | Partial | Current release-report wiring and paid-run authority/bounds: PC-001/PC-011 |
| FR-012; P05-T01 | Partial | Initial migration route should not depend on unverified platform-native support: PC-006 |
| P04-T01; NFR-008 | Partial | Real PostgreSQL testing needs explicit isolated CI/local provisioning: PC-009 |
| P01-P05, eleven task Goals/Requirements/Details/References/Dependencies | Covered | Four completed lenses assessed supplied material scope; dependency graph is acyclic and transitive prerequisites count |

## Verdict

* Verdict: Revise.
* Rationale: The plan is broadly credible but two High findings and seven Medium/two Low refinements require parent disposition. Corrections fit existing scope; no immediate user response is needed. Deferred business/live-release inputs remain user-owned.

## Findings

<!-- rpi:critique id=PC-001 -->
### PC-001 [High]: Release gating must consume current quality evidence

* Related IDs: FR-011, NFR-008, P04-T01, P04-T02, P05-T01, P05-T02.
* Evidence: .copilot-tracking/plans/2026-11-08/sarcasm-detection-app-plan.md states "Configure Render After CI Checks Pass" and later "configure CI-backed redeploys", but describes no connection from the evaluator's non-passing gate to future deployment. Research F6/W24 identifies skipped-check behavior.
* Concern: Passing ordinary CI could enable a new release despite absent, skipped, failing or stale model-quality evidence.
* Impact: FR-011's substantive release requirement can be missed.
* Smallest useful change: Name the ordinary CI deliverable/job and explicitly keep automatic production deploy off until an approved policy connects release revision and passing required evaluation evidence. Define a usable operator-controlled release gate in the meantime.
* Action owner: Planning parent.
* Exact resolving evidence: P04-T01 owns a named actual workflow/job; P04-T02 rejects missing/failing/stale release reports; P05-T01/P05-T02 require that result for the exact revision and do not enable unapproved auto-deploy.
* Decision route: Direct planner correction; automatic deployment was not a confirmed user requirement.

<!-- rpi:critique id=PC-002 -->
### PC-002 [Medium]: Privacy verification must inspect all retained surfaces

* Related IDs: NFR-005, P02-T02, P03-T01, P04-T01, P05-T02.
* Evidence: The plan's synthetic-marker wording names exporter/provider/decorator paths, while its contract also promises no raw text in PostgreSQL or application logs. P03-T01 prepares a notice asserting no app/trace message retention.
* Concern: A span-only check could pass while error logs or database records retain the marker; the public notice must not precede verification.
* Impact: Misleading privacy claim or undiscovered content retention.
* Smallest useful change: Require one synthetic-marker sweep across DB rows, captured logs and exported spans, including failure paths, and gate the public notice/release on its passing result.
* Action owner: Planning parent.
* Exact resolving evidence: P04-T01 names all three surfaces and P03-T01/P05-T02 require passing checks before asserting the no-content-retention notice.
* Decision route: Direct planner correction within existing NFR-005.

<!-- rpi:critique id=PC-003 -->
### PC-003 [Medium]: Maintenance needs an executable and safe operating contract

* Related IDs: FR-005, NFR-004, P02-T01, P04-T01, P05-T01.
* Evidence: Plan Details promise "A purge command deletes expired request and session/admission metadata" and "purge/stale reconciliation scheduling and trigger", but specify no command surface or operating trigger.
* Concern: Required retention/interruption maintenance can remain descriptive and production deletion precautions unclear.
* Impact: Audit growth, stale outcomes, or unsafe first deletion.
* Smallest useful change: Name a maintenance CLI with preview-first purge, explicit apply semantics and bounded reconciliation; choose an operator-owned trigger without silently adding paid scheduler resources.
* Action owner: Planning parent.
* Exact resolving evidence: P02-T01 Requirements define the CLI/retention behavior; P04-T01 checks expiry/idempotence; P05-T01 names operator schedule, first-production-deletion precaution and protected target.
* Decision route: Direct planner correction; scheduled resources need separate approval if later selected.

<!-- rpi:critique id=PC-004 -->
### PC-004 [Low]: Quantitative planning choices are not workflow-confirmed values

* Related IDs: D7, NFR-003, P01-T02, P04-T01.
* Evidence: D7 labels both standard critique and the six-file/40-case budget "Confirmed by workflow constraint". The skill requires a locked addition budget but does not set those numbers. Operating bounds are explicitly baseline assumptions but lack a grouped provenance row.
* Concern: Planner-selected numbers can be mistaken for user or industry/workflow mandates.
* Impact: Unnecessary restrictions or false confidence about audience capacity.
* Smallest useful change: Separate standard-critique provenance from planner-selected test/operating bounds, preserving required behavior and labelling event capacity unverified.
* Action owner: Planning parent.
* Exact resolving evidence: D7 identifies the budget as planner-selected; a numeric-assumption row names local values and production confirmation gate; NFR-003 requires configured-value enforcement without claiming event sufficiency.
* Decision route: Direct planner correction.

<!-- rpi:critique id=PC-010 -->
### PC-010 [High]: Model-only quotas do not bound every-HTTP audit writes

* Related IDs: FR-004, FR-007, NFR-003-NFR-004, P02-T01, P02-T03, P05-T02.
* Evidence: P02-T01 audits every HTTP request before work; P02-T03's global quota counts model reservations, not asset, unmatched or health traffic. Its risk mitigation names a bounded pool/load test, not a bounded pre-audit admission rule.
* Concern: Arbitrary unauthenticated paths can create unlimited waiting audit work or sustained DB growth independently of model quotas.
* Impact: Resource exhaustion, event disruption and unexpected storage load.
* Smallest useful change: Bound all-HTTP work/rate before database admission, timebox audit acquisition/writes, promptly reject overload without model work, and expose diagnostic/rejection counts without claiming unpersisted requests were recorded. Preserve full metadata audit for admitted request kinds; do not silently sample away the user's requirement.
* Action owner: Planning parent.
* Exact resolving evidence: P01-T02/P02-T03 define required all-HTTP capacity/rate settings and no-unbounded-queue behavior; FR-004/NFR-004 state the honest unavailable-audit boundary; P04-T01/P05-T02 exercise non-classification flood behavior.
* Decision route: Direct planner correction within bounded operation and truthful auditing; residual pre-admission/storage-outage gaps must stay explicit.

<!-- rpi:critique id=PC-011 -->
### PC-011 [Medium]: Paid experiment runs need explicit authority and dispatch caps

* Related IDs: FR-010, NFR-003/NFR-008, P04-T02, P05-T02, D5.
* Evidence: P04-T02 defines a paid/live option and first pilot; numerical live-run call/cost bounds and separate authorization are not attached to that dispatch path.
* Concern: A developer or CI run can opt into an unbounded paid pilot before the deferred release settings are approved.
* Impact: Unapproved expense or live-data export.
* Smallest useful change: Require explicit manual authorization plus per-run request/concurrency/token and conservative cost-reservation caps; missing settings prevent dispatch, and PR CI has no live secrets/paid path.
* Action owner: Planning parent.
* Exact resolving evidence: P04-T02 gates every live/pilot invocation with approved config and non-passing absence; P05-T02 references those caps; D5 records provider/Langfuse destination and budget approval.
* Decision route: Direct planner correction; the future actual authorization remains user-owned.

<!-- rpi:critique id=PC-005 -->
### PC-005 [Low]: Carry conflicting cues into the Unknown rubric

* Related IDs: FR-002, P02-T02, P04-T02; research F1.
* Evidence: Research F1 lists "insufficient context, conflicting cues, or unsupported language", whereas P02-T02 names only insufficient context/unsupported language.
* Concern: The shortened wording may lose a relevant ambiguity case when authoring the model/evaluation rubric.
* Impact: Minor avoidable rubric divergence.
* Smallest useful change: Retain conflicting cues in classifier and evaluation-rubric guidance.
* Action owner: Planning parent.
* Exact resolving evidence: P02-T02 and P04-T02 explicitly preserve conflicting-cue abstention without making a claim about author intent.
* Decision route: Direct planner correction.

<!-- rpi:critique id=PC-006 -->
### PC-006 [Medium]: Do not assume a platform-native migration gate is verified

* Related IDs: FR-012, P05-T01; research F4/D6.
* Evidence: P05-T01 requires a "paid-compatible pre-deploy Alembic upgrade gate", while research leaves migration placement dependent on the approved service plan. The task contains a confirmation step, but no executable alternative if the platform gate is unavailable.
* Concern: A specific unverified deployment mechanism is treated as the sole migration route.
* Impact: Rework or blocked rollout when service-tier capabilities differ.
* Smallest useful change: Use a documented operator-controlled locked Alembic migration before rollout as the supported initial mechanism; platform-native automation remains optional pending verified support and authorization.
* Action owner: Planning parent.
* Exact resolving evidence: P05-T01 identifies the command, database-only environment, single execution owner and schema/rollback compatibility gate without asserting unsupported Render capability.
* Decision route: Direct planner correction; no extra research needed if unsupported platform dependency is removed.

<!-- rpi:critique id=PC-007 -->
### PC-007 [Medium]: Independent QR decoding needs an identified method and stage

* Related IDs: FR-009, NFR-006, P03-T02, P04-T01, P05-T02.
* Evidence: P03-T02 claims "Local mocked decode checks" while only an encoder is selected; P05-T02 asks for "an independent decoder" without naming a tool or manual method.
* Concern: Encoding/synthetic response checks can be mislabeled as independent decode evidence.
* Impact: Validation cannot be reproduced as described.
* Smallest useful change: Identify a native phone-camera QR reader applied to both rendered SVG and PNG as the manual independent-decode method at release; local automated tests verify URL/format behavior without claiming a decoder ran. An automated decoder is optional only if justified and separately verified.
* Action owner: Planning parent.
* Exact resolving evidence: P03-T02/P04-T01 distinguish automated encoding checks from P05-T02's named manual reader and final device/network evidence.
* Decision route: Direct planner correction, no additional runtime dependency or unsupported research claim.

<!-- rpi:critique id=PC-008 -->
### PC-008 [Medium]: Signed session fairness needs configuration and transport

* Related IDs: FR-007, NFR-005, P01-T02, P02-T03, P03-T01.
* Evidence: P02-T03 promises opaque signed identifiers; P05-T01 mentions a signing secret, but the early configuration and browser-transport contract do not name the signing setting or cookie/header path.
* Concern: Local fairness implementation can vary or mishandle secure-cookie transport and retention.
* Impact: Rework or identifier exposure despite the privacy contract.
* Smallest useful change: Name injected/production signing-key settings, bounded secure same-origin cookie transport and a persisted pseudonymous key distinct from raw cookie data; state that resetting fairness does not bypass global limits.
* Action owner: Planning parent.
* Exact resolving evidence: P01-T02 validates signing configuration; P02-T03 sets cookie/expiry/storage rules; P03-T01 relies on same-origin browser transport without logging cookie values.
* Decision route: Direct planner correction.

<!-- rpi:critique id=PC-009 -->
### PC-009 [Medium]: PostgreSQL tests need explicit isolated provisioning

* Related IDs: NFR-008, P04-T01.
* Evidence: The plan requires real isolated PostgreSQL migration/admission tests but names only pytest commands and no provisioned CI/local connection path.
* Concern: Critical tests can be silently skipped or point at a shared database.
* Impact: Unverified database behavior or unsafe teardown.
* Smallest useful change: Specify a PostgreSQL service in ordinary CI plus an explicit isolated TEST_DATABASE_URL for local PostgreSQL checks; missing prerequisites must fail the required job, and cleanup touches only the run-owned test schema.
* Action owner: Planning parent.
* Exact resolving evidence: P04-T01 names CI service/connection variable, optional local-container route, isolated-target safeguards and no silent skips.
* Decision route: Direct planner correction.

## Strengths and Residual Risk

* Provider choices, typed labels, error honesty, no default raw-content retention, one-worker topology, isolated failure tests and separate live-release gates are coherent with the brief.
* Deferred accounts, budget, reviewed labels/thresholds, destination and phone scan remain real release prerequisites, not evidence of a missing application requirement.
* Test-cap overflow was suggested only by estimate and is not a verified finding. Requirement-range formatting, transitive dependencies, source-backed reasoning default and permitted local package/runtime choice were not converted into artificial blockers.

## Questions or Blocking Evidence Gaps

* No research blocker if PC-006 removes the unverified platform-native migration dependency and PC-007 uses a named manual QR-reading method.
* No immediate user answer required for planner-owned corrections. Public deployment still needs D5/D6 operating approvals, accounts, reviewed evaluation data and actual URL/device.

## Limitations

* Source/evidence assessment only; no live deployment, SDK execution, database behavior, model accuracy or diagram rendering is verified by this critique.
* No earlier critique to reconcile.
* Coverage lens did not reread external research; evidence/executability lenses and parent source verification covered the material comparisons. Risk lens read the risk-relevant portions. No external capability is independently re-fetched by this critique.
* Candidate suggestions were verified at quoted plan/research locations before assigning IDs/severity; final findings are scoped to demonstrated concerns rather than all helper recommendations.

## Recommended Next Action

* Highest-impact findings: PC-001 release gating and PC-010 all-HTTP audit backpressure.
* Severity counts: Critical 0; High 2; Medium 7; Low 2.
* Action owner: Planning parent.
* Smallest next action: Dispose all eleven findings in the existing plan, apply direct corrections and finalize readiness without a second critique.
* User response required: No for current corrections; D5/D6 still gate later public release.
