"""Synthetic metric/gate fixtures, not model-quality data."""

import json
from uuid import uuid4

import httpx
import pytest
from langfuse import Langfuse
from langfuse.openai import AsyncOpenAI

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


def test_actual_experiment_sdk_is_bounded_and_offline(monkeypatch, provider_factory) -> None:
    """Synthetic reviewed-flag fixtures exercise the SDK, not a real gold evaluation."""
    _, spans, _ = provider_factory
    labels = list(Label)
    calls = []
    cases = [
        Case(
            case_id=f"c{i}",
            message=f"fixture{i}",
            expected=label,
            group_id=f"c{i}",
            split="holdout",
            provenance="synthetic",
            reviewed=True,
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
        return Langfuse(
            **kwargs,
            httpx_client=httpx.Client(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, json={"successes": [], "errors": []}),
                )
            ),
        )

    def api_factory(**kwargs):
        def transport(request):
            payload = json.loads(request.content)
            calls.append(payload)
            index = int(payload["input"][0]["content"][-1])
            return httpx.Response(200, json=response_body(label=labels[index].value))

        return AsyncOpenAI(
            **kwargs,
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(transport),
            ),
        )

    monkeypatch.setattr("evals.run.Langfuse", tracer_factory)
    monkeypatch.setattr("evals.run.AsyncOpenAI", api_factory)
    limits = config(thresholds=thresholds().model_copy(update={"p95_ms": 10000}))
    report = experiment(dataset, limits, split="holdout", settings=cfg)
    assert report["metrics"]["count"] == 3 and report["pass"] is True
    assert len(calls) == 3 and report["reserved_cost_usd"] <= limits.max_cost_usd
    assert "fixture0" not in repr([dict(span.attributes or {}) for span in spans])
