"""Actual locked Responses parsing and sanitized SDK export with fake transport."""

import json
import logging
from uuid import uuid4

import httpx
import pytest
from langfuse import Langfuse
from langfuse.openai import AsyncOpenAI
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import SpanExportResult

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

    def export(self, batch):
        spans.extend(batch)
        return SpanExportResult.SUCCESS

    monkeypatch.setattr(OTLPSpanExporter, "export", export)

    def make(body=None, *, status=200, timeout=False):
        key = "pk-test-" + uuid4().hex
        config = settings(
            openai_api_key="test-key", langfuse_public_key=key, langfuse_secret_key="sk-test"
        )
        tracer = Langfuse(
            public_key=key,
            secret_key="sk-test",
            base_url="https://example.test",
            mask=mask_data,
            tracer_provider=PrivacyTracerProvider(),
            flush_at=1,
            timeout=1,
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

    return make, spans, calls


async def test_typed_parse_trace_and_export_privacy(provider_factory, caplog) -> None:
    configure_logging()
    logging.getLogger("openai").warning(MARKER)
    assert MARKER not in caplog.text and "telemetry_sdk_diagnostic" in caplog.text
    make, spans, calls = provider_factory
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
        assert len(spans) == 2
    finally:
        await classifier.close()


@pytest.mark.parametrize("kind", ["refusal", "incomplete", "invalid_label", "provider", "timeout"])
async def test_provider_failures_are_not_unknown(provider_factory, kind: str) -> None:
    make, spans, calls = provider_factory
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
        for span in spans:
            assert MARKER not in repr(dict(span.attributes or {}))
            assert not span.events and not span.status.description
    finally:
        await classifier.close()
