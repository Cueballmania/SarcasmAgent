"""Actual locked Responses parsing and sanitized SDK export with fake transport."""

import asyncio
import json
import logging
from uuid import uuid4

import httpx
import pytest
from langfuse import Langfuse
from langfuse.openai import AsyncOpenAI
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.trace import StatusCode

from app.classifier import Classifier
from app.contracts import AppError, Label
from app.tracing import PrivacyTracerProvider, configure_logging, mask_data
from tests.test_config import settings

MARKER = "PRIVATE_SYNTHETIC_MARKER"


def response_body(
    *, label: str = "Sarcasm Detected", refusal: bool = False, status: str = "completed"
) -> dict:
    """Build a synthetic Responses payload accepted by the actual SDK parser."""
    content = (
        {"type": "refusal", "refusal": MARKER}
        if refusal
        else {"type": "output_text", "text": json.dumps({"label": label}), "annotations": []}
    )
    return {
        "id": "resp_test",
        "object": "response",
        "created_at": 1,
        "status": status,
        "model": "gpt-5.4-mini-2026-03-17",
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
        "output": [
            {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [content],
            }
        ],
        "usage": {
            "input_tokens": 8,
            "output_tokens": 4,
            "total_tokens": 12,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
    }


@pytest.fixture
def provider_factory(monkeypatch: pytest.MonkeyPatch):
    """Capture actual export spans without a Langfuse network connection."""
    spans = []
    calls = []
    scores = []

    def export(self, batch):
        spans.extend(batch)
        return SpanExportResult.SUCCESS

    monkeypatch.setattr(OTLPSpanExporter, "export", export)

    def make(body=None, *, status=200, timeout=False):
        key = "pk-test-" + uuid4().hex
        config = settings(
            openai_api_key="test-key", langfuse_public_key=key, langfuse_secret_key="sk-test"
        )

        def score_transport(request):
            assert request.method == "POST"
            assert request.url.path == "/api/public/scores"
            scores.extend(json.loads(request.content))
            return httpx.Response(202, json={"message": "Accepted"})

        tracer = Langfuse(
            public_key=key,
            secret_key="sk-test",
            base_url="https://example.test",
            mask=mask_data,
            tracer_provider=PrivacyTracerProvider(
                environment=config.app_env, release=config.deploy_revision
            ),
            flush_at=1,
            timeout=1,
            httpx_client=httpx.Client(transport=httpx.MockTransport(score_transport)),
        )

        def transport(request):
            calls.append(json.loads(request.content))
            if timeout:
                raise httpx.ReadTimeout(MARKER, request=request)
            return httpx.Response(status, json=body or response_body())

        api = AsyncOpenAI(
            api_key="test-key",
            max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(transport)),
        )
        return Classifier(config, api=api, tracer=tracer)

    return make, spans, calls, scores


async def test_typed_parse_trace_and_export_privacy(provider_factory, caplog) -> None:
    configure_logging()
    logging.getLogger("openai").warning(MARKER)
    assert MARKER not in caplog.text and "telemetry_sdk_diagnostic" in caplog.text
    make, spans, calls, scores = provider_factory
    classifier = make()
    try:
        result = await classifier.classify(
            MARKER,
            str(uuid4()),
            langfuse_public_key=classifier.public_key,
        )
        classifier.tracer.flush()
        assert result.label == Label.SARCASM and result.input_tokens == 8
        assert result.trace_id
        assert calls[0]["store"] is False and calls[0]["reasoning"]["effort"] == "none"
        assert len(calls) == 1
        assert MARKER not in repr([dict(span.attributes) for span in spans])
        assert MARKER not in repr(scores)
        root = next(span for span in spans if span.name == "sarcasm-classification")
        attrs = root.attributes
        assert json.loads(attrs["langfuse.observation.metadata.outcome"]) == "success"
        assert (
            json.loads(attrs["langfuse.trace.metadata.request_id"]) == attrs["sarcasm.request_id"]
        )
        assert json.loads(attrs["langfuse.observation.metadata.input_length"]) == len(MARKER)
        assert root.resource.attributes["service.name"] == "sarcasm-agent"
        assert root.resource.attributes["deployment.environment"] == "test"
        assert {score["name"]: score["value"] for score in scores} == {
            "response_contract": 1,
            "abstained": 0,
            "latency_ms": pytest.approx(result.elapsed_ms, abs=20),
        }
        assert all(score["traceId"] == result.trace_id for score in scores)
        assert (
            len(
                [
                    s
                    for s in spans
                    if (s.attributes or {}).get("langfuse.observation.type") == "generation"
                ]
            )
            == 1
        )
        assert len(spans) == 3
        assert all(span.parent.span_id == root.context.span_id for span in spans if span != root)
        assert any(span.name == "validate.classification" for span in spans)
    finally:
        await classifier.close()


@pytest.mark.parametrize("kind", ["refusal", "incomplete", "invalid_label", "provider", "timeout"])
async def test_provider_failures_are_not_unknown(provider_factory, kind: str) -> None:
    make, spans, calls, scores = provider_factory
    body = response_body(
        refusal=kind == "refusal",
        status="incomplete" if kind == "incomplete" else "completed",
        label="wrong" if kind == "invalid_label" else "Unknown",
    )
    if kind == "provider":
        body = {"error": {"message": MARKER, "type": "server_error"}}
    classifier = make(body, status=500 if kind == "provider" else 200, timeout=kind == "timeout")
    try:
        with pytest.raises(AppError) as caught:
            await classifier.classify(
                MARKER, str(uuid4()), langfuse_public_key=classifier.public_key
            )
        assert caught.value.status in {422, 502, 504}
        assert caught.value.trace_id
        classifier.tracer.flush()
        assert len(calls) == 1
        assert any(
            (span.attributes or {}).get("sarcasm.error_code") == caught.value.code for span in spans
        )
        root = next(span for span in spans if span.name == "sarcasm-classification")
        assert json.loads(root.attributes["langfuse.observation.metadata.outcome"]) == "error"
        assert root.attributes["langfuse.observation.level"] == "ERROR"
        assert root.status.status_code == StatusCode.ERROR
        assert {score["name"]: score["value"] for score in scores} == {
            "response_contract": 0,
            "latency_ms": pytest.approx(root.attributes["sarcasm.elapsed_ms"]),
        }
        assert MARKER not in repr(scores)
        for span in spans:
            assert MARKER not in repr(dict(span.attributes or {}))
            assert not span.events and not span.status.description
    finally:
        await classifier.close()


async def test_unknown_is_valid_abstention_not_an_error(provider_factory) -> None:
    make, spans, _, scores = provider_factory
    classifier = make(response_body(label="Unknown"))
    try:
        result = await classifier.classify(
            MARKER, str(uuid4()), langfuse_public_key=classifier.public_key
        )
        classifier.tracer.flush()
        root = next(span for span in spans if span.name == "sarcasm-classification")
        assert result.label == Label.UNKNOWN
        assert root.attributes["sarcasm.outcome"] == "abstained"
        assert root.attributes["langfuse.observation.level"] == "WARNING"
        assert root.status.status_code != StatusCode.ERROR
        assert {score["name"]: score["value"] for score in scores}.items() >= {
            "response_contract": 1,
            "abstained": 1,
        }.items()
    finally:
        await classifier.close()


async def test_cancelled_attempt_has_failed_contract_and_no_abstention(
    provider_factory, monkeypatch
) -> None:
    make, spans, _, scores = provider_factory
    classifier = make()

    async def cancel(**kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(classifier.api.responses, "parse", cancel)
    try:
        with pytest.raises(asyncio.CancelledError):
            await classifier.classify(
                MARKER, str(uuid4()), langfuse_public_key=classifier.public_key
            )
        classifier.tracer.flush()
        root = next(span for span in spans if span.name == "sarcasm-classification")
        assert root.attributes["sarcasm.error_code"] == "request_cancelled"
        assert root.attributes["langfuse.observation.level"] == "ERROR"
        assert {score["name"]: score["value"] for score in scores} == {
            "response_contract": 0,
            "latency_ms": pytest.approx(root.attributes["sarcasm.elapsed_ms"]),
        }
    finally:
        await classifier.close()


async def test_export_drops_arbitrary_metadata_and_unapproved_prefixes(provider_factory) -> None:
    from opentelemetry import trace

    make, spans, _, _ = provider_factory
    classifier = make()
    try:
        with classifier.tracer.start_as_current_observation(name="privacy-check"):
            trace.get_current_span().set_attributes(
                {
                    "sarcasm.secret": MARKER,
                    "langfuse.trace.metadata.secret": MARKER,
                    "langfuse.observation.metadata.secret": MARKER,
                    "langfuse.experiment.metadata": MARKER,
                    "langfuse.experiment.item.metadata": MARKER,
                    "langfuse.experiment.item.expected_output": MARKER,
                    "langfuse.observation.status_message": MARKER,
                    "sarcasm.outcome": "success",
                    "langfuse.experiment.name": "approved-run",
                }
            )
        classifier.tracer.flush()
        attrs = dict(spans[0].attributes)
        assert MARKER not in repr(attrs)
        assert json.loads(attrs["langfuse.observation.metadata.outcome"]) == "success"
        assert attrs["langfuse.experiment.name"] == "approved-run"
    finally:
        await classifier.close()
