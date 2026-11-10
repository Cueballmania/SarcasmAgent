"""One-attempt typed OpenAI classification with complementary Langfuse spans."""

import asyncio
from dataclasses import dataclass
from time import monotonic

from langfuse import Langfuse, observe
from langfuse.openai import AsyncOpenAI
from openai import APITimeoutError, OpenAIError
from opentelemetry import trace
from pydantic import ValidationError

from app.config import Settings
from app.contracts import (
    INSTRUCTION,
    PROMPT_REVISION,
    SCHEMA_REVISION,
    AppError,
    Label,
    ModelLabel,
)
from app.tracing import PrivacyTracerProvider


@dataclass(frozen=True)
class Result:
    """Metadata-only classification outcome for the audit."""

    label: Label
    trace_id: str | None = None
    provider_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    elapsed_ms: float = 0


class Classifier:
    """Own the application-lifetime provider and tracing clients."""

    def __init__(
        self, settings: Settings, *, api: AsyncOpenAI | None = None, tracer: Langfuse | None = None
    ) -> None:
        self.settings = settings
        self.public_key = (
            settings.langfuse_public_key.get_secret_value()
            if settings.langfuse_public_key
            else None
        )
        self.tracer = tracer or Langfuse(
            public_key=self.public_key,
            secret_key=settings.langfuse_secret_key.get_secret_value()
            if settings.langfuse_secret_key
            else None,
            base_url=settings.langfuse_base_url,
            environment=settings.app_env,
            release=settings.deploy_revision,
            timeout=2,
            tracer_provider=PrivacyTracerProvider(
                environment=settings.app_env, release=settings.deploy_revision
            ),
            debug=False,
        )
        if api is None and not settings.openai_api_key:
            raise AppError("configuration_unavailable", 503, "OpenAI is not configured.")
        self.api = api or AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            max_retries=0,
            timeout=settings.request_timeout_seconds,
        )

    @observe(name="sarcasm-classification", capture_input=False, capture_output=False)
    async def classify(
        self, message: str, request_id: str, *, langfuse_public_key: str | None = None
    ) -> Result:
        """Return exactly one label or a safe typed failure; never downgrade errors to Unknown."""
        started = monotonic()
        label = None
        span = trace.get_current_span()
        self.tracer.update_current_span(input={"message": message})
        span.set_attributes(
            {
                "sarcasm.request_id": request_id,
                "sarcasm.prompt_revision": PROMPT_REVISION,
                "sarcasm.schema_revision": SCHEMA_REVISION,
                "sarcasm.environment": self.settings.app_env,
                "sarcasm.deploy_revision": self.settings.deploy_revision,
                "sarcasm.model": self.settings.model,
                "sarcasm.input_length": len(message),
            }
        )

        def failure(code: str, status: int, message: str) -> AppError:
            span.set_attribute("sarcasm.error_code", code)
            return AppError(code, status, message, trace_id=self.tracer.get_current_trace_id())

        try:
            try:
                response = await self.api.responses.parse(
                    model=self.settings.model,
                    instructions=INSTRUCTION,
                    input=[{"role": "user", "content": message}],
                    text_format=ModelLabel,
                    reasoning={"effort": "none"},
                    store=False,
                    max_output_tokens=self.settings.max_output_tokens,
                    langfuse_public_key=self.public_key,
                )
            except APITimeoutError:
                raise failure(
                    "request_timeout", 504, "Classification timed out; try later."
                ) from None
            except (ValidationError, ValueError):
                raise failure(
                    "invalid_provider_output", 502, "Invalid classifier response."
                ) from None
            except OpenAIError:
                raise failure(
                    "provider_error", 502, "Classifier service unavailable; try later."
                ) from None
            with self.tracer.start_as_current_observation(name="validate.classification"):
                for output in response.output:
                    for content in getattr(output, "content", []):
                        if content.type == "refusal":
                            raise failure(
                                "provider_refusal", 422, "The classifier declined this input."
                            )
                if response.status != "completed" or response.output_parsed is None:
                    raise failure(
                        "invalid_provider_output", 502, "Classifier did not complete a valid label."
                    )
                label = response.output_parsed.label
            span.set_attribute("sarcasm.label", label.value)
            self.tracer.update_current_span(output={"label": label.value})
            usage = response.usage
            if usage:
                span.set_attributes(
                    {
                        "sarcasm.input_tokens": usage.input_tokens,
                        "sarcasm.output_tokens": usage.output_tokens,
                    }
                )
            return Result(
                label=label,
                trace_id=self.tracer.get_current_trace_id(),
                provider_id=response.id,
                input_tokens=usage.input_tokens if usage else None,
                output_tokens=usage.output_tokens if usage else None,
                elapsed_ms=(monotonic() - started) * 1000,
            )
        except asyncio.CancelledError:
            span.set_attribute("sarcasm.error_code", "request_cancelled")
            raise
        finally:
            elapsed_ms = (monotonic() - started) * 1000
            span.set_attributes(
                {
                    "sarcasm.elapsed_ms": elapsed_ms,
                    "sarcasm.outcome": (
                        "abstained" if label == Label.UNKNOWN else "success" if label else "error"
                    ),
                }
            )
            trace_id = self.tracer.get_current_trace_id()
            if trace_id:
                self.tracer.create_score(
                    trace_id=trace_id,
                    name="response_contract",
                    value=int(label is not None),
                    data_type="BOOLEAN",
                    comment="Operational validity only; not semantic correctness.",
                )
                self.tracer.create_score(
                    trace_id=trace_id, name="latency_ms", value=elapsed_ms, data_type="NUMERIC"
                )
                if label is not None:
                    self.tracer.create_score(
                        trace_id=trace_id,
                        name="abstained",
                        value=int(label == Label.UNKNOWN),
                        data_type="BOOLEAN",
                    )

    async def close(self) -> None:
        """Close the provider and flush/shut down batched trace resources."""
        await self.api.close()
        await asyncio.to_thread(self.tracer.shutdown)
