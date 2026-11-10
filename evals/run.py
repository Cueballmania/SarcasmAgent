"""Explicitly authorized Langfuse experiment runner and revision-bound release checker."""

import argparse
import asyncio
import hashlib
import json
import logging
from pathlib import Path
from time import monotonic
from uuid import uuid4

from langfuse import Evaluation, Langfuse
from langfuse.openai import AsyncOpenAI
from opentelemetry import trace
from pydantic import ValidationError

from app.classifier import Classifier
from app.config import Settings
from app.contracts import MODEL, PROMPT_REVISION, SCHEMA_REVISION, AppError, Label
from app.tracing import PrivacyTracerProvider, configure_logging
from evals.contracts import Budget, Dataset, RunConfig, file_hash
from evals.metrics import passes, summarize

ROOT = Path(__file__).resolve().parent.parent


def source_hash() -> str:
    """Bind release evidence to actual code/lock/schema/rubric bytes, not revision alone."""
    files = [ROOT / "pyproject.toml", ROOT / "uv.lock", ROOT / ".python-version"]
    for directory in ("app", "migrations", "evals"):
        files.extend(
            path
            for path in (ROOT / directory).rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix in {".py", ".html", ".js", ".css", ".md"}
        )
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def experiment(
    dataset: Dataset, config: RunConfig, *, split: str, settings: Settings
) -> dict[str, object]:
    """Run reviewed cases with bounded per-item clients on the SDK-owned event loop."""
    cases = dataset.reviewed_cases(split)
    if len(cases) > config.max_requests:
        raise ValueError("Dataset exceeds the approved run request cap")
    budget = Budget(config)
    for case in cases:
        budget.reserve(case.message)
    if not all(
        (settings.openai_api_key, settings.langfuse_public_key, settings.langfuse_secret_key)
    ):
        raise ValueError("Live evaluation requires configured provider/trace credentials")
    settings = settings.model_copy(
        update={"max_output_tokens": config.max_output_tokens, "deploy_revision": config.revision}
    )
    key = settings.langfuse_public_key.get_secret_value()
    tracer = Langfuse(
        public_key=key,
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        base_url=settings.langfuse_base_url,
        environment=settings.app_env,
        release=config.revision,
        timeout=2,
        tracer_provider=PrivacyTracerProvider(
            environment=settings.app_env, release=config.revision
        ),
    )
    results: dict[str, dict] = {}
    run_name = f"sarcasm-{config.revision[:12]}-{uuid4().hex[:8]}"
    run_metadata = {
        "sarcasm.run_name": run_name,
        "sarcasm.split": split,
        "sarcasm.dataset_version": dataset.version,
        "sarcasm.deploy_revision": config.revision,
        "sarcasm.prompt_revision": PROMPT_REVISION,
        "sarcasm.schema_revision": SCHEMA_REVISION,
        "sarcasm.model": MODEL,
    }

    async def task(*, item: dict) -> str | None:
        started = monotonic()
        case_id = item["metadata"]["case_id"]
        output = None
        cost = None
        failure = None
        input_tokens = output_tokens = None
        trace_id = tracer.get_current_trace_id()
        trace.get_current_span().set_attributes(
            {
                **run_metadata,
                "sarcasm.case_id": case_id,
                "sarcasm.expected_label": item["expected_output"],
            }
        )
        try:
            async with AsyncOpenAI(
                api_key=settings.openai_api_key.get_secret_value(),
                max_retries=0,
                timeout=settings.request_timeout_seconds,
            ) as api:
                classifier = Classifier(settings, api=api, tracer=tracer)
                async with asyncio.timeout(settings.request_timeout_seconds):
                    result = await classifier.classify(
                        item["input"],
                        str(uuid4()),
                        langfuse_public_key=key,
                    )
                output = result.label.value
                cost = result.cost_usd
                input_tokens, output_tokens = result.input_tokens, result.output_tokens
                trace_id = result.trace_id or trace_id
        except (AppError, TimeoutError) as error:
            failure = error.code if isinstance(error, AppError) else "request_timeout"
            logging.warning("evaluation_case_failed code=%s", failure)
        current_span = trace.get_current_span()
        current_span.set_attribute(
            "sarcasm.outcome",
            "error" if failure else "abstained" if output == Label.UNKNOWN else "success",
        )
        if failure:
            current_span.set_attribute("sarcasm.error_code", failure)
        if output is not None:
            current_span.set_attribute("sarcasm.label", output)
        results[case_id] = {
            "output": output,
            "elapsed_ms": (monotonic() - started) * 1000,
            "cost": cost,
            "failure": failure,
            "trace_id": trace_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        return output

    def evaluate_case(
        *, output: str | None, expected_output: str, metadata: dict, **kwargs
    ) -> list[Evaluation]:
        observed = results[metadata["case_id"]]
        valid = output in {label.value for label in Label}
        return [
            Evaluation(name="exact_label", value=int(output == expected_output)),
            Evaluation(name="eval_response_contract", value=int(valid)),
            Evaluation(
                name="abstention_correct",
                value=int(
                    valid and (output == Label.UNKNOWN.value) == (expected_output == Label.UNKNOWN)
                ),
                comment="Correct abstention decision, not correctness of an answered label.",
            ),
            Evaluation(
                name="latency_within_target",
                value=int(observed["elapsed_ms"] <= config.thresholds.p95_ms),
                comment="Per-case diagnostic; release latency gate uses run p95.",
            ),
        ]

    def observations() -> list[dict]:
        return [
            results.get(
                case.case_id,
                {
                    "output": None,
                    "elapsed_ms": None,
                    "cost": None,
                    "failure": "experiment_case_missing",
                    "trace_id": None,
                    "input_tokens": None,
                    "output_tokens": None,
                },
            )
            for case in cases
        ]

    def aggregate(**kwargs) -> list[Evaluation]:
        metrics = measure()
        scores = [
            Evaluation(name=name, value=value)
            for name, value in metrics.items()
            if isinstance(value, (int, float))
        ]
        for label, values in metrics["per_class"].items():
            prefix = {
                Label.SARCASM: "sarcasm",
                Label.LITERAL: "literal",
                Label.UNKNOWN: "unknown",
            }[label]
            scores.extend(
                Evaluation(name=f"{prefix}_{name}", value=value) for name, value in values.items()
            )
        return scores

    def measure() -> dict[str, object]:
        observed = observations()
        return summarize(
            [case.expected.value for case in cases],
            [item["output"] for item in observed],
            elapsed_ms=[item["elapsed_ms"] for item in observed],
            costs=[item["cost"] for item in observed],
        )

    try:
        tracer.run_experiment(
            name="sarcasm-" + split,
            run_name=run_name,
            data=[
                {
                    "input": case.message,
                    "expected_output": case.expected.value,
                    "metadata": {"case_id": case.case_id},
                }
                for case in cases
            ],
            task=task,
            evaluators=[evaluate_case],
            run_evaluators=[aggregate],
            max_concurrency=config.max_concurrency,
            metadata={
                "revision": config.revision,
                "dataset_version": dataset.version,
                "prompt_revision": PROMPT_REVISION,
                "schema_revision": SCHEMA_REVISION,
                "split": split,
            },
        )
        # Missing SDK-isolated cases are explicit failures, not omitted observations.
        observed = observations()
        metrics = measure()
        slices = {}
        for tag in sorted({tag for case in cases for tag in case.tags}):
            indices = [i for i, case in enumerate(cases) if tag in case.tags]
            slices[tag] = {
                **summarize(
                    [cases[i].expected.value for i in indices],
                    [observed[i]["output"] for i in indices],
                    elapsed_ms=[observed[i]["elapsed_ms"] for i in indices],
                    costs=[observed[i]["cost"] for i in indices],
                ),
                "limitation": "No statistical sufficiency claim",
            }
        # Keep a stable summary trace/report link alongside native experiment scores.
        with tracer.start_as_current_observation(name="evaluate.sarcasm") as summary:
            trace.get_current_span().set_attributes(run_metadata)
            for score in aggregate():
                tracer.create_score(
                    trace_id=summary.trace_id,
                    name=score.name,
                    value=score.value,
                    data_type="NUMERIC",
                )
            gate_passed = split == "holdout" and passes(metrics, config.thresholds)
            tracer.create_score(
                trace_id=summary.trace_id,
                name="release_gate_passed",
                value=int(gate_passed),
                data_type="BOOLEAN",
                comment="Pilot runs never authorize release; use the revision-bound CLI checker.",
            )
            summary_trace_id = summary.trace_id
        return {
            "fixture": False,
            "split": split,
            "revision": config.revision,
            "dataset_version": dataset.version,
            "model": MODEL,
            "prompt_revision": PROMPT_REVISION,
            "schema_revision": SCHEMA_REVISION,
            "source_hash": source_hash(),
            "metrics": metrics,
            "slices": slices,
            "run_name": run_name,
            "summary_trace_id": summary_trace_id,
            "failure_counts": {
                code: sum(item["failure"] == code for item in observed)
                for code in sorted({item["failure"] for item in observed if item["failure"]})
            },
            "cases": [
                {
                    "case_id": case.case_id,
                    "expected": case.expected.value,
                    "predicted": item["output"],
                    "trace_id": item["trace_id"],
                    "failure": item["failure"],
                    "elapsed_ms": item["elapsed_ms"],
                    "input_tokens": item["input_tokens"],
                    "output_tokens": item["output_tokens"],
                    "cost_usd": item["cost"],
                }
                for case, item in zip(cases, observed, strict=True)
            ],
            "reserved_cost_usd": budget.reserved_usd,
            "pass": gate_passed,
        }
    finally:
        tracer.shutdown()


def check_release(report: dict, *, dataset_path: Path, config_path: Path, revision: str) -> None:
    """Reject stale/nonpassing/fixture reports; operator retains deployment authority."""
    if not isinstance(report, dict):
        raise ValueError("Release report must be a JSON object")
    dataset = Dataset.model_validate_json(dataset_path.read_text())
    config = RunConfig.model_validate_json(config_path.read_text())
    cases = dataset.reviewed_cases("holdout")
    if (
        report.get("fixture") is not False
        or report.get("pass") is not True
        or report.get("split") != "holdout"
        or report.get("revision") != revision
        or config.revision != revision
        or report.get("source_hash") != source_hash()
        or report.get("dataset_hash") != file_hash(dataset_path)
        or report.get("config_hash") != file_hash(config_path)
        or report.get("model") != MODEL
        or report.get("prompt_revision") != PROMPT_REVISION
        or report.get("schema_revision") != SCHEMA_REVISION
        or report.get("metrics", {}).get("count") != len(cases)
        or not passes(report["metrics"], config.thresholds)
    ):
        raise ValueError("Release requires current reviewed passing holdout evidence")


def main() -> None:
    """Require --live before any model/trace construction or paid dispatch."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["run", "check"])
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--split", choices=["pilot", "holdout"], default="holdout")
    parser.add_argument("--revision")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    configure_logging()
    try:
        if args.action == "check":
            if not args.revision:
                raise ValueError("Release check requires --revision")
            check_release(
                json.loads(args.report.read_text()),
                dataset_path=args.dataset,
                config_path=args.config,
                revision=args.revision,
            )
        else:
            if not args.live:
                raise ValueError("Paid runs require explicit --live and approved run configuration")
            dataset = Dataset.model_validate_json(args.dataset.read_text())
            config = RunConfig.model_validate_json(args.config.read_text())
            report = experiment(dataset, config, split=args.split, settings=Settings())
            report.update(dataset_hash=file_hash(args.dataset), config_hash=file_hash(args.config))
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + "\n")
            if not report["pass"]:
                raise ValueError("Run is nonpassing or pilot-only; inspect the report")
    except (ValueError, ValidationError, OSError, KeyError, TypeError) as error:
        logging.error(
            "evaluation_gate_failed type=%s; verify data/config/report", type(error).__name__
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
