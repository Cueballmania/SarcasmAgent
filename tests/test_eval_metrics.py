"""Synthetic metric/gate fixtures, not model-quality data."""

import json
from uuid import uuid4

import httpx
import pytest
from langfuse import Langfuse
from langfuse.openai import AsyncOpenAI

from app.classifier import Classifier
from app.contracts import MODEL, PROMPT_REVISION, SCHEMA_REVISION, Label
from evals.contracts import Budget, Case, Dataset, RunConfig, Thresholds, file_hash
from evals.metrics import passes, summarize
from evals.run import check_release, experiment, source_hash
from tests.test_classifier import provider_factory as provider_factory
from tests.test_classifier import response_body
from tests.test_config import settings


def thresholds() -> Thresholds:
    """Toy bounds for testing gate behavior only."""
    return Thresholds(
        macro_f1=0.5,
        coverage=0.5,
        per_class_precision=0.5,
        per_class_recall=0.5,
        max_failure_rate=0.1,
        p95_ms=100,
    )


def config(**overrides) -> RunConfig:
    return RunConfig(
        **{
            "approval_reference": "fixture-only",
            "revision": "a" * 40,
            "max_requests": 3,
            "max_concurrency": 1,
            "max_input_tokens": 32000,
            "max_output_tokens": 128,
            "max_cost_usd": 1,
            "input_usd_per_million": 1,
            "output_usd_per_million": 1,
            "thresholds": thresholds(),
            **overrides,
        }
    )


def test_perfect_three_class_metrics_and_missing_cost() -> None:
    labels = [label.value for label in Label]
    metrics = summarize(labels, labels, elapsed_ms=[1, 2, 3], costs=[None] * 3)
    assert metrics["macro_f1"] == 1 and metrics["coverage"] == pytest.approx(2 / 3)
    assert metrics["available_cost_usd"] is None and metrics["missing_cost_count"] == 3
    assert passes(metrics, thresholds())


def test_all_unknown_and_errors_cannot_pass() -> None:
    labels = [label.value for label in Label]
    for predictions in [[Label.UNKNOWN.value] * 3, [None] * 3]:
        metrics = summarize(labels, predictions, elapsed_ms=[1] * 3, costs=[None] * 3)
        assert not passes(metrics, thresholds()) and metrics["count"] == 3
    with pytest.raises(ValueError):
        summarize([], [], elapsed_ms=[], costs=[])
    missing = summarize(labels, labels, elapsed_ms=[None] * 3, costs=[None] * 3)
    assert missing["p95_ms"] is None and missing["missing_latency_count"] == 3
    assert not passes(missing, thresholds())


def test_missing_class_and_failed_case_denominators() -> None:
    labels = [Label.SARCASM.value, Label.LITERAL.value]
    metrics = summarize(labels, [Label.SARCASM.value, None], elapsed_ms=[1, 2], costs=[None, None])
    assert metrics["accuracy"] == 0.5 and metrics["failure_rate"] == 0.5
    assert not passes(metrics, thresholds())


def test_dataset_review_and_split_leakage() -> None:
    first = Case(
        case_id="one",
        message="fixture",
        expected=Label.SARCASM,
        group_id="pair",
        split="pilot",
        provenance="synthetic",
    )
    dataset = Dataset(
        version="fixture", language="en", annotation="fixture", fixture=True, cases=[first]
    )
    with pytest.raises(ValueError, match="reviewed"):
        dataset.reviewed_cases("pilot")
    with pytest.raises(ValueError, match="cross"):
        Dataset(
            version="fixture",
            language="en",
            annotation="fixture",
            cases=[
                first,
                first.model_copy(update={"case_id": "two", "split": "holdout"}),
            ],
        )


def test_request_token_cost_caps_prevent_dispatch() -> None:
    budget = Budget(config(max_requests=1))
    budget.reserve("fixture")
    with pytest.raises(ValueError, match="cap reached"):
        budget.reserve("fixture")
    for overrides in [{"max_input_tokens": 1}, {"max_cost_usd": 0.000001}]:
        with pytest.raises(ValueError):
            Budget(config(**overrides)).reserve("fixture")


def test_fixture_release_report_is_rejected(tmp_path) -> None:
    case = Case(
        case_id="one",
        message="fixture",
        expected=Label.UNKNOWN,
        group_id="one",
        split="holdout",
        provenance="synthetic",
    )
    dataset = Dataset(
        version="fixture", language="en", annotation="fixture", fixture=True, cases=[case]
    )
    data_path, config_path = tmp_path / "dataset.json", tmp_path / "config.json"
    data_path.write_text(dataset.model_dump_json())
    config_path.write_text(config().model_dump_json())
    with pytest.raises(ValueError):
        check_release(
            {"fixture": True, "pass": True},
            dataset_path=data_path,
            config_path=config_path,
            revision="a" * 40,
        )


def test_release_rejects_stale_revision_source_dataset_and_config(tmp_path) -> None:
    """Synthetic schema/metric fixtures drive integrity checks, not quality attestations."""
    labels = list(Label)
    cases = [
        Case(
            case_id=f"c{i}",
            message="synthetic contract fixture",
            expected=label,
            group_id=f"c{i}",
            split="holdout",
            provenance="synthetic",
            reviewed=True,
        )
        for i, label in enumerate(labels)
    ]
    dataset = Dataset(
        version="contract-test",
        language="en",
        annotation="perceived",
        review_reference="synthetic-contract-test",
        cases=cases,
    )
    data_path, config_path = tmp_path / "dataset.json", tmp_path / "config.json"
    data_path.write_text(dataset.model_dump_json())
    config_path.write_text(config().model_dump_json())
    report = {
        "fixture": False,
        "pass": True,
        "split": "holdout",
        "revision": "a" * 40,
        "source_hash": source_hash(),
        "dataset_hash": file_hash(data_path),
        "config_hash": file_hash(config_path),
        "model": MODEL,
        "prompt_revision": PROMPT_REVISION,
        "schema_revision": SCHEMA_REVISION,
        "metrics": summarize(
            [label.value for label in labels],
            [label.value for label in labels],
            elapsed_ms=[1, 2, 3],
            costs=[None] * 3,
        ),
    }
    check_release(report, dataset_path=data_path, config_path=config_path, revision="a" * 40)
    for field in ("revision", "source_hash", "dataset_hash", "config_hash"):
        with pytest.raises(ValueError):
            check_release(
                {**report, field: "stale"},
                dataset_path=data_path,
                config_path=config_path,
                revision="a" * 40,
            )


@pytest.mark.parametrize("failure_mode", ["none", "provider", "isolated"])
def test_actual_experiment_sdk_is_bounded_and_offline(
    monkeypatch, provider_factory, failure_mode
) -> None:
    """Synthetic reviewed-flag fixtures exercise the SDK, not a real gold evaluation."""
    _, spans, _, _ = provider_factory
    labels = list(Label)
    calls = []
    scores = []
    cases = [
        Case(
            case_id=f"c{i}",
            message=f"fixture{i}",
            expected=label,
            group_id=f"c{i}",
            split="holdout",
            provenance="synthetic",
            reviewed=True,
            tags=["all-cases", f"class-{i}"],
        )
        for i, label in enumerate(labels)
    ]
    dataset = Dataset(
        version="sdk-contract-test",
        language="en",
        annotation="perceived",
        review_reference="synthetic-test-only",
        cases=cases,
    )
    cfg = settings(
        openai_api_key="test-key",
        langfuse_public_key="pk-test-" + uuid4().hex,
        langfuse_secret_key="sk-test",
    )

    def tracer_factory(**kwargs):
        def transport(request):
            if request.method == "GET":
                assert request.url.path == "/api/public/projects"
                return httpx.Response(200, json={"data": []})
            assert request.method == "POST"
            assert request.url.path == "/api/public/scores"
            scores.extend(json.loads(request.content))
            return httpx.Response(202, json={"message": "Accepted"})

        return Langfuse(
            **kwargs,
            httpx_client=httpx.Client(transport=httpx.MockTransport(transport)),
        )

    def api_factory(**kwargs):
        def transport(request):
            payload = json.loads(request.content)
            calls.append(payload)
            index = int(payload["input"][0]["content"][-1])
            if failure_mode == "provider" and index == 1:
                return httpx.Response(
                    500, json={"error": {"message": "PRIVATE_EVAL_MARKER", "type": "server_error"}}
                )
            return httpx.Response(200, json=response_body(label=labels[index].value))

        return AsyncOpenAI(
            **kwargs,
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(transport),
            ),
        )

    monkeypatch.setattr("evals.run.Langfuse", tracer_factory)
    monkeypatch.setattr("evals.run.AsyncOpenAI", api_factory)
    if failure_mode == "isolated":
        original_classify = Classifier.classify

        async def isolated_failure(self, message, *args, **kwargs):
            result = await original_classify(self, message, *args, **kwargs)
            if message == "fixture1":
                raise RuntimeError("PRIVATE_EVAL_MARKER")
            return result

        monkeypatch.setattr(Classifier, "classify", isolated_failure)
    limits = config(thresholds=thresholds().model_copy(update={"p95_ms": 10000}))
    report = experiment(dataset, limits, split="holdout", settings=cfg)
    assert report["metrics"]["count"] == 3 and report["pass"] is (failure_mode == "none")
    assert len(calls) == 3 and report["reserved_cost_usd"] <= limits.max_cost_usd
    exported = repr([dict(span.attributes or {}) for span in spans])
    assert all(f"fixture{i}" in exported for i in range(3))
    assert "PRIVATE_EVAL_MARKER" not in repr(scores) + repr(report) + exported
    assert "fixture0" not in json.dumps(report) + repr(scores)
    assert report["run_name"].startswith("sarcasm-" + limits.revision[:12])
    summary = next(span for span in spans if span.name == "evaluate.sarcasm")
    assert report["summary_trace_id"] == format(summary.context.trace_id, "032x")
    summary_scores = {
        score["name"]: score["value"]
        for score in scores
        if score.get("traceId") == report["summary_trace_id"]
    }
    assert summary_scores["macro_f1"] == report["metrics"]["macro_f1"]
    assert summary_scores["unknown_recall"] == 1
    assert summary_scores["missing_cost_count"] == 3
    assert "available_cost_usd" not in summary_scores
    assert summary_scores["release_gate_passed"] == int(failure_mode == "none")
    case_traces = {item["trace_id"] for item in report["cases"] if item["trace_id"]}
    assert len(case_traces) == (2 if failure_mode == "isolated" else 3)
    assert report["summary_trace_id"] not in case_traces
    experiment_roots = [span for span in spans if span.name == "experiment-item-run"]
    assert len(experiment_roots) == 3
    assert all(
        span.attributes["langfuse.experiment.name"] == report["run_name"]
        for span in experiment_roots
    )
    experiment_tasks = [span for span in spans if span.name == "experiment-item-task"]
    assert len(experiment_tasks) == 3
    assert all(
        json.loads(span.attributes["langfuse.observation.metadata.expected_label"]) in labels
        for span in experiment_tasks
    )
    root_ids = {span.context.span_id for span in experiment_roots}
    assert all(span.parent.span_id in root_ids for span in experiment_tasks)
    assert all(
        span.attributes["langfuse.experiment.item.root_observation_id"]
        == format(span.context.span_id, "016x")
        for span in experiment_tasks
    )
    experiment_ids = {span.attributes["langfuse.experiment.id"] for span in experiment_roots}
    assert len(experiment_ids) == 1
    experiment_id = experiment_ids.pop()
    run_scores = {
        score["name"]: score["value"]
        for score in scores
        if score.get("datasetRunId") == experiment_id
    }
    assert run_scores["macro_f1"] == report["metrics"]["macro_f1"]
    assert run_scores["unknown_recall"] == 1
    assert report["slices"]["all-cases"]["macro_f1"] == report["metrics"]["macro_f1"]
    for item in report["cases"]:
        if not item["trace_id"]:
            assert failure_mode == "isolated" and item["case_id"] == "c1"
            assert item["failure"] == "experiment_case_missing"
            continue
        case_scores = {
            score["name"]: score["value"]
            for score in scores
            if score.get("traceId") == item["trace_id"]
        }
        assert case_scores["exact_label"] == int(item["failure"] is None)
        assert case_scores["eval_response_contract"] == int(item["failure"] is None)
        assert case_scores["abstention_correct"] == int(item["failure"] is None)
        assert "latency_within_target" in case_scores
        task_span = next(
            span
            for span in experiment_tasks
            if format(span.context.trace_id, "032x") == item["trace_id"]
        )
        assert all(
            score["observationId"] == format(task_span.context.span_id, "016x")
            for score in scores
            if score.get("traceId") == item["trace_id"]
            and score["name"]
            in {
                "exact_label",
                "eval_response_contract",
                "abstention_correct",
                "latency_within_target",
            }
        )
        assert item["cost_usd"] is None
    if failure_mode != "none":
        code = "provider_error" if failure_mode == "provider" else "experiment_case_missing"
        assert report["failure_counts"] == {code: 1}
        assert report["cases"][1]["predicted"] is None
        assert report["cases"][1]["input_tokens"] is None
    else:
        assert report["failure_counts"] == {}
        assert all(item["input_tokens"] == 8 for item in report["cases"])
