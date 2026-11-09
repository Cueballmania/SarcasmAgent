"""Bounded ASGI lifecycle: initial audit before work, final commit before success."""

import asyncio
import logging
from collections.abc import Awaitable
from time import monotonic
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import Settings
from app.contracts import AppError

logger = logging.getLogger(__name__)


class AuditStore(Protocol):
    """The short-transaction audit/admission contract, injectable for failure tests."""

    async def begin(self, request_id: UUID, *, kind: str, method: str, route: str) -> None: ...
    async def finish(self, request_id: UUID, *, status: int, **fields: object) -> None: ...
    async def reserve(
        self, quota_key: str, *, window_limit: int, day_limit: int, session_limit: int
    ) -> None: ...
    async def ready(self) -> None: ...
    async def close(self) -> None: ...


class Capacity:
    """Event-loop-local nonwaiting HTTP/model capacity for one worker."""

    def __init__(self, *, inflight: int, window_limit: int) -> None:
        self.maximum = inflight
        self.window_limit = window_limit
        self.active = 0
        self.window_count = 0
        self.window_started = monotonic()

    def enter(self) -> bool:
        """Acquire synchronously with no queued request/task allocation."""
        if monotonic() - self.window_started >= 60:
            self.window_count = 0
            self.window_started = monotonic()
        if self.active >= self.maximum or self.window_count >= self.window_limit:
            return False
        self.active += 1
        self.window_count += 1
        return True

    def leave(self) -> None:
        """Release exactly one active slot."""
        self.active -= 1


class AuditMiddleware:
    """Buffer the finite app response until the final audit transaction commits."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Audit all HTTP kinds, including framework errors; never capture raw paths/bodies."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        services = scope["app"].state.services
        settings: Settings = services.settings
        store: AuditStore = services.database
        request_id = uuid4()
        state = scope.setdefault("state", {})
        state["request_id"] = str(request_id)
        state["audit_fields"] = {}
        path = scope["path"]
        known = {"/", "/presenter", "/qr.svg", "/qr.png", "/api/classify", "/health"}
        route = (
            path
            if path in known
            else ("/static/{path}" if path.startswith("/static/") else "unmatched")
        )
        kind = "classify" if route == "/api/classify" else "http"
        if not services.http_capacity.enter():
            services.diagnostics["audit_capacity_unavailable"] += 1
            now = monotonic()
            if now - services.last_capacity_log >= 1:
                services.last_capacity_log = now
                logger.warning(
                    "audit_capacity_unavailable total=%s request_id=%s",
                    services.diagnostics["audit_capacity_unavailable"],
                    request_id,
                )
            try:
                async with asyncio.timeout(settings.audit_timeout_seconds):
                    await JSONResponse(
                        AppError(
                            "audit_capacity_unavailable",
                            503,
                            "Service is busy; try later.",
                        ).body(str(request_id)),
                        status_code=503,
                    )(scope, receive, send)
            except TimeoutError:
                services.diagnostics["rejection_delivery_timeout"] += 1
            return
        started = monotonic()
        pending = False
        deferred_release = False
        response_messages: list[Message] = []
        status = 500
        stage = "initial_audit"
        response_bytes = 0

        async def timed(operation: Awaitable[object]) -> object:
            async with asyncio.timeout(settings.audit_timeout_seconds):
                return await operation

        async def buffer(message: Message) -> None:
            nonlocal status, response_bytes
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"cache-control", b"no-store"),
                        (b"x-content-type-options", b"nosniff"),
                        (b"referrer-policy", b"no-referrer"),
                        (
                            b"content-security-policy",
                            b"default-src 'self'; frame-ancestors 'none'; "
                            b"form-action 'self'; base-uri 'none'",
                        ),
                        (b"x-request-id", str(request_id).encode()),
                    ]
                )
                message["headers"] = headers
            if message["type"] == "http.response.body":
                response_bytes += len(message.get("body", b""))
                if response_bytes > 262144:
                    raise AppError("response_too_large", 500, "Response could not be delivered.")
            response_messages.append(message)

        async def cleanup(error: AppError) -> None:
            try:
                async with asyncio.timeout(settings.cleanup_grace_seconds):
                    await timed(
                        store.finish(
                            request_id,
                            status=error.status,
                            error_code=error.code,
                            elapsed_ms=(monotonic() - started) * 1000,
                        )
                    )
            except (SQLAlchemyError, TimeoutError, AppError):
                services.diagnostics["audit_cleanup_unavailable"] += 1
                logger.error("audit_cleanup_unavailable request_id=%s", request_id)
            finally:
                services.http_capacity.leave()

        try:
            try:
                async with asyncio.timeout(settings.request_timeout_seconds):
                    await timed(
                        store.begin(
                            request_id,
                            kind=kind,
                            method=scope["method"],
                            route=route,
                        )
                    )
                    pending = True
                    stage = "body"
                    body = bytearray()
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            raise AppError("client_disconnected", 499, "Client disconnected.")
                        chunk = message.get("body", b"")
                        if len(body) + len(chunk) > settings.max_body_bytes:
                            raise AppError("body_too_large", 413, "Message body is too large.")
                        body.extend(chunk)
                        if not message.get("more_body", False):
                            break
                    delivered = False

                    async def replay() -> Message:
                        nonlocal delivered
                        if not delivered:
                            delivered = True
                            return {"type": "http.request", "body": bytes(body), "more_body": False}
                        return await receive()

                    stage = "handler"
                    await self.app(scope, replay, buffer)
                    stage = "final_audit"
                    await timed(
                        store.finish(
                            request_id,
                            status=status,
                            elapsed_ms=(monotonic() - started) * 1000,
                            **state["audit_fields"],
                        )
                    )
                    pending = False
            except (AppError, SQLAlchemyError, TimeoutError) as caught:
                deadline = isinstance(caught, TimeoutError) and stage not in {
                    "initial_audit",
                    "final_audit",
                }
                error = (
                    caught
                    if isinstance(caught, AppError)
                    else AppError(
                        "request_timeout" if deadline else "storage_unavailable",
                        504 if deadline else 503,
                        "Request could not complete; try later.",
                    )
                )
                logger.warning("request_failed code=%s request_id=%s", error.code, request_id)
                services.diagnostics[error.code] += 1
                if pending:
                    task = asyncio.create_task(cleanup(error))
                    services.cleanups.add(task)
                    task.add_done_callback(services.cleanups.discard)
                    deferred_release = True
                response_messages.clear()
                response_bytes = 0
                await JSONResponse(error.body(str(request_id)), status_code=error.status)(
                    scope, receive, buffer
                )
            except Exception as error:
                logger.error(
                    "request_failed type=%s request_id=%s", type(error).__name__, request_id
                )
                failure = AppError("internal_error", 500, "Request failed; contact the operator.")
                if pending:
                    task = asyncio.create_task(cleanup(failure))
                    services.cleanups.add(task)
                    task.add_done_callback(services.cleanups.discard)
                    deferred_release = True
                response_messages.clear()
                response_bytes = 0
                await JSONResponse(failure.body(str(request_id)), status_code=500)(
                    scope, receive, buffer
                )
            async with asyncio.timeout(settings.cleanup_grace_seconds):
                for message in response_messages:
                    await send(message)
            services.diagnostics[f"http_{status // 100}xx"] += 1
        except asyncio.CancelledError:
            if pending and not deferred_release:
                task = asyncio.create_task(cleanup(AppError("interrupted", 499, "Interrupted.")))
                services.cleanups.add(task)
                task.add_done_callback(services.cleanups.discard)
                deferred_release = True
            raise
        finally:
            if not deferred_release:
                services.http_capacity.leave()
