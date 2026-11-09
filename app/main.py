"""Audience-facing FastAPI routes; all HTTP passes the audited ASGI lifecycle."""

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import ValidationError
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from app.classifier import Classifier
from app.config import Settings
from app.contracts import PROMPT_REVISION, SCHEMA_REVISION, AppError, Label, Submission
from app.database import Database
from app.lifecycle import AuditMiddleware, AuditStore
from app.qr import qr_bytes
from app.services import Detector, Services
from app.tracing import configure_logging


def create_app(
    *,
    settings: Settings | None = None,
    database: AuditStore | None = None,
    detector: Detector | None = None,
) -> FastAPI:
    """Create an injectable app; configuration/provider construction happens at startup."""

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        configure_logging()
        config = settings or Settings()
        store = database or Database(config)
        classifier = detector
        if classifier is None and config.openai_api_key:
            classifier = Classifier(config)
        services = Services(config, store, classifier)
        application.state.services = services
        try:
            yield
        finally:
            if services.cleanups:
                await asyncio.gather(*services.cleanups)
            if classifier:
                await classifier.close()
            await store.close()

    application = FastAPI(
        title="Sarcasm detector", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )
    application.add_middleware(AuditMiddleware)
    assets = Path(__file__).parent
    templates = Jinja2Templates(directory=assets / "templates")
    application.mount("/static", StaticFiles(directory=assets / "static"), name="static")

    @application.get("/", response_class=HTMLResponse)
    async def form(request: Request) -> Response:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "labels": [label.value for label in Label],
                "retention_days": request.app.state.services.settings.retention_days,
            },
        )

    @application.get("/presenter", response_class=HTMLResponse)
    async def presenter(request: Request) -> Response:
        url = request.app.state.services.settings.public_base_url
        if not url:
            raise AppError("configuration_unavailable", 503, "Public URL is not configured.")
        return templates.TemplateResponse(
            request=request,
            name="presenter.html",
            context={"public_url": url},
        )

    @application.get("/qr.{kind}")
    async def download_qr(request: Request, kind: str) -> Response:
        url = request.app.state.services.settings.public_base_url
        if not url:
            raise AppError("configuration_unavailable", 503, "Public URL is not configured.")
        if kind not in {"svg", "png"}:
            raise AppError("not_found", 404, "QR format unavailable.")
        image = qr_bytes(url, kind="svg" if kind == "svg" else "png")
        return Response(
            image,
            media_type="image/svg+xml" if kind == "svg" else "image/png",
            headers={"Content-Disposition": f'attachment; filename="sarcasm-qr.{kind}"'},
        )

    @application.exception_handler(AppError)
    async def safe_error(request: Request, error: AppError) -> JSONResponse:
        request.state.audit_fields["error_code"] = error.code
        if error.trace_id:
            request.state.audit_fields["trace_id"] = error.trace_id
        return JSONResponse(error.body(request.state.request_id), status_code=error.status)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        return await safe_error(request, AppError("invalid_message", 422, "Invalid message."))

    @application.exception_handler(HTTPException)
    async def framework_error(request: Request, error: HTTPException) -> JSONResponse:
        code = "not_found" if error.status_code == 404 else "method_not_allowed"
        return await safe_error(request, AppError(code, error.status_code, "Route unavailable."))

    @application.post("/api/classify")
    async def classify(request: Request) -> JSONResponse:
        services: Services = request.app.state.services
        try:
            submission = Submission.model_validate(await request.json())
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise AppError("invalid_json", 400, "Send a valid JSON message.") from None
        except ValidationError:
            raise AppError("invalid_message", 422, "Send 1 to 2,000 text characters.") from None
        if not submission.message.strip():
            raise AppError("invalid_message", 422, "Message cannot be blank.")
        request.state.audit_fields.update(
            {
                "input_length": len(submission.message),
                "model": services.settings.model,
                "prompt_revision": PROMPT_REVISION,
                "schema_revision": SCHEMA_REVISION,
            }
        )
        if not services.detector:
            raise AppError("configuration_unavailable", 503, "Classifier is not configured.")
        cookie, quota_key = services.session(request.cookies.get("sarcasm_session"))
        if services.model_active >= services.settings.model_slots:
            raise AppError("rate_limited", 429, "Classifier is busy; try later.")
        services.model_active += 1
        try:
            async with asyncio.timeout(services.settings.audit_timeout_seconds):
                await services.database.reserve(
                    quota_key,
                    window_limit=services.settings.global_window_limit,
                    day_limit=services.settings.global_day_limit,
                    session_limit=services.settings.session_window_limit,
                )
            result = await services.detector.classify(
                submission.message,
                request.state.request_id,
                langfuse_public_key=services.detector.public_key,
            )
        finally:
            services.model_active -= 1
        fields = asdict(result)
        fields["label"] = result.label.value
        fields.pop("elapsed_ms")
        request.state.audit_fields.update(
            {
                **fields,
                "input_length": len(submission.message),
                "model": services.settings.model,
                "prompt_revision": PROMPT_REVISION,
                "schema_revision": SCHEMA_REVISION,
            }
        )
        response = JSONResponse(
            {"label": result.label.value, "request_id": request.state.request_id}
        )
        response.set_cookie(
            "sarcasm_session",
            cookie,
            max_age=services.settings.session_ttl_seconds,
            secure=services.settings.app_env == "production",
            httponly=True,
            samesite="lax",
        )
        return response

    @application.get("/health")
    async def health(request: Request) -> dict[str, str]:
        services: Services = request.app.state.services
        await services.database.ready()
        if not services.detector:
            raise AppError("configuration_unavailable", 503, "Classifier is not configured.")
        return {"status": "ready"}

    return application


app = create_app()
