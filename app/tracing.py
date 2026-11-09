"""Public OpenTelemetry export filtering for metadata-only Langfuse traces."""

import logging
from typing import Any

from opentelemetry.context import Context
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor, TracerProvider
from opentelemetry.trace import Status

SAFE_ATTRIBUTES = {
    "langfuse.observation.type",
    "langfuse.observation.model.name",
    "langfuse.observation.usage_details",
    "langfuse.observation.cost_details",
    "langfuse.environment",
    "langfuse.release",
    "langfuse.observation.version",
    "langfuse.observation.level",
}


def mask_data(*, data: Any) -> str:
    """Remove SDK-captured input/output/metadata before span creation."""
    return "[redacted]"


def sanitized_span(span: ReadableSpan) -> ReadableSpan:
    """Copy a span without prompts, exception details, links or arbitrary attributes."""
    attributes = {
        key: value
        for key, value in (span.attributes or {}).items()
        if key in SAFE_ATTRIBUTES or key.startswith("sarcasm.")
    }
    resource = Resource(
        {
            key: value
            for key, value in span.resource.attributes.items()
            if key.startswith("telemetry.sdk.") or key in {"service.name"}
        }
    )
    return ReadableSpan(
        name=span.name,
        context=span.context,
        parent=span.parent,
        resource=resource,
        attributes=attributes,
        kind=span.kind,
        status=Status(span.status.status_code),
        start_time=span.start_time,
        end_time=span.end_time,
        instrumentation_scope=span.instrumentation_scope,
    )


class PrivacyProcessor(SpanProcessor):
    """Sanitize before delegating to the SDK's batch/export processor."""

    def __init__(self, delegate: SpanProcessor) -> None:
        self.delegate = delegate

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        """Preserve SDK context propagation."""
        self.delegate.on_start(span, parent_context)

    def on_end(self, span: ReadableSpan) -> None:
        """Export only the sanitized copy through the delegated processor."""
        self.delegate.on_end(sanitized_span(span))

    def shutdown(self) -> None:
        """Stop the delegated exporter."""
        self.delegate.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Flush on operator shutdown/evaluation completion, not per request."""
        return self.delegate.force_flush(timeout_millis)


class PrivacyTracerProvider(TracerProvider):
    """Wrap every attached processor through the supported public extension point."""

    def add_span_processor(self, span_processor: SpanProcessor) -> None:
        """Apply the same export policy to Langfuse's automatically installed processor."""
        super().add_span_processor(PrivacyProcessor(span_processor))


class SafeSDKLogs(logging.Filter):
    """Retain actionable SDK degradation diagnostics without provider payloads."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Replace third-party SDK error content with an operator-safe category."""
        if record.name.startswith(("langfuse", "openai", "opentelemetry", "httpx", "httpcore")):
            record.msg = "telemetry_sdk_diagnostic; verify operator trace/provider connectivity"
            record.args = ()
            record.exc_info = None
            record.exc_text = None
            record.stack_info = None
        return True


def configure_logging() -> None:
    """Use bounded safe diagnostics; never enable raw provider HTTP debug logging."""
    handler = logging.StreamHandler()
    handler.addFilter(SafeSDKLogs())
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    for existing in logging.getLogger().handlers:
        if not any(isinstance(policy, SafeSDKLogs) for policy in existing.filters):
            existing.addFilter(SafeSDKLogs())
    for name in ("langfuse", "openai", "httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
