// Copyright (c) Microsoft Corporation. Licensed under the MIT License.
(function () {
  'use strict';
  const sources = {
    rpi: {
      title: 'HVE Core: RPI coordination and progression',
      url: 'https://github.com/microsoft/hve-core/blob/main/.github/skills/rpi/rpi/SKILL.md',
      note: 'Checked 2026-11-10. Research, Plan, Implement, Review and Follow-up; manual/automatic progression, retained decisions and stop boundaries. Moving upstream source.'
    },
    research: {
      title: 'HVE Core: Research evidence and readiness',
      url: 'https://github.com/microsoft/hve-core/blob/main/.github/skills/rpi/rpi-research/SKILL.md',
      note: 'Installed skill and owning contract checked 2026-11-10. Research owns evidence and planning readiness, not implementation.'
    },
    planning: {
      title: 'HVE Core: task-centered implementation planning',
      url: 'https://github.com/microsoft/hve-core/blob/main/.github/skills/rpi/rpi-plan/SKILL.md',
      note: 'Checked 2026-11-10. Requirements, task scope, dependencies, critique and readiness.'
    },
    implementation: {
      title: 'HVE Core: implementing and recording evidence',
      url: 'https://github.com/microsoft/hve-core/blob/main/.github/skills/rpi/rpi-implement/SKILL.md',
      note: 'Owning skill contract checked 2026-11-10. Plan-driven implementation, changes records and actual validation.'
    },
    review: {
      title: 'HVE Core: reviewing implementation against evidence',
      url: 'https://github.com/microsoft/hve-core/blob/main/.github/skills/rpi/rpi-review/SKILL.md',
      note: 'Owning skill contract checked 2026-11-10. Review execution is separate from acceptance outcome.'
    },
    application: {
      title: 'Sarcasm Agent: implementation and operating contract',
      url: 'https://github.com/Cueballmania/SarcasmAgent/blob/ccd0e72c32a3571190e40048be80e4bad32a3d64/README.md',
      note: 'Pinned feature-branch source, 2026-11-10. A single-model classifier with three exact labels, metadata-only telemetry and explicit failures. Source existence is not deployment evidence.'
    },
    operations: {
      title: 'Sarcasm Agent: release and operations policy',
      url: 'https://github.com/Cueballmania/SarcasmAgent/blob/ccd0e72c32a3571190e40048be80e4bad32a3d64/docs/operations.md',
      note: 'Pinned source. Passing CI and current reviewed holdout evidence, approved migration/rollout and post-release verification are separate requirements.'
    },
    ci: {
      title: 'Sarcasm Agent: current offline CI workflow',
      url: 'https://github.com/Cueballmania/SarcasmAgent/blob/ccd0e72c32a3571190e40048be80e4bad32a3d64/.github/workflows/ci.yml',
      note: 'Pinned source. Offline checks with PostgreSQL and Chromium. No paid evaluation workflow exists here.'
    },
    hosting: {
      title: 'Sarcasm Agent: existing-service Render configuration',
      url: 'https://github.com/Cueballmania/SarcasmAgent/blob/ccd0e72c32a3571190e40048be80e4bad32a3d64/render.yaml',
      note: 'Pinned source. Locked build, Uvicorn, health check and environment settings for the existing service. Reference configuration is not proof of a performed rollout.'
    },
    tracing: {
      title: 'Sarcasm Agent: classification trace and runtime scores',
      url: 'https://github.com/Cueballmania/SarcasmAgent/blob/ccd0e72c32a3571190e40048be80e4bad32a3d64/app/classifier.py',
      note: 'Pinned source. One instrumented generation, post-parse validation and operational contract/latency/abstention scores. Audience text is excluded from exported telemetry.'
    },
    evaluations: {
      title: 'Sarcasm Agent: evaluation metrics and release evidence',
      url: 'https://github.com/Cueballmania/SarcasmAgent/blob/ccd0e72c32a3571190e40048be80e4bad32a3d64/evals/run.py',
      note: 'Pinned source. Item scores, explicit run-summary scores, case trace linkage and reviewed-data/budget gates. Detailed matrix and slice reports remain JSON.'
    },
    langfuse: {
      title: 'Langfuse: SDK-based application experiments',
      url: 'https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk',
      note: 'Checked 2026-11-10. Traced tasks, evaluators and configurable concurrency. Current documentation covers newer SDK/server versions than the pinned application SDK; do not assume UI parity.'
    },
    dashboards: {
      title: 'Langfuse: custom dashboards',
      url: 'https://langfuse.com/docs/metrics/features/custom-dashboards',
      note: 'Checked 2026-11-10. Widgets visualize traces, observations and scores. The deck does not claim that a project dashboard has already been populated or provisioned.'
    },
    demo: {
      title: 'Sarcasm Agent: prepared observability walkthrough',
      url: 'https://github.com/Cueballmania/SarcasmAgent/blob/ccd0e72c32a3571190e40048be80e4bad32a3d64/docs/observability-demo.md',
      note: 'Pinned source. Prepared browser tabs, honest runtime/evaluation semantics and a short maintenance-loop demonstration.'
    }
  };
  const examples = {};
  const demos = {};
  function moveStep(index, action, length) {
    if (!Number.isInteger(length) || length < 1 || !Number.isInteger(index) || index < 0 || index >= length) {
      throw new Error('Invalid walkthrough state.');
    }
    if (action === 'reset') return 0;
    if (action === 'next') return Math.min(length - 1, index + 1);
    if (action === 'back') return Math.max(0, index - 1);
    throw new Error(`Unknown walkthrough action: ${action}`);
  }
  function diffStats(rows) {
    if (!Array.isArray(rows) || rows.some(row => !['add', 'remove', 'context'].includes(row.type) || typeof row.text !== 'string')) {
      throw new Error('Invalid displayed diff rows.');
    }
    return {
      added: rows.filter(row => row.type === 'add').length,
      removed: rows.filter(row => row.type === 'remove').length
    };
  }
  globalThis.DeckContent = { sources, examples, demos, moveStep, diffStats };
}());
