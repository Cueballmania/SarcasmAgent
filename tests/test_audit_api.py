"""Audited API failures, bounded admission and cross-surface privacy."""

import asyncio
from contextlib import asynccontextmanager
from uuid import UUID

import httpx
import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.classifier import Result
from app.contracts import Label
from app.database import AuditRequest, Database
from app.main import create_app
from tests.test_classifier import MARKER
from tests.test_classifier import provider_factory as provider_factory
from tests.test_config import settings


class MemoryAudit:
    """Synthetic audit port exposing commits/failures, never a database test proxy."""

    def __init__(self, *, failure: str | None = None) -> None:
        self.rows = {}
        self.failure = failure
        self.reservations = []

    async def begin(self, request_id: UUID, **fields: object) -> None:
        if self.failure == "initial":
            raise SQLAlchemyError(MARKER)
        self.rows[request_id] = {"state": "pending", **fields}

    async def finish(self, request_id: UUID, *, status: int, **fields: object) -> None:
        if self.failure == "final":
            raise SQLAlchemyError(MARKER)
        self.rows[request_id].update(
            state="completed" if status < 400 else "failed", status=status, **fields
        )

    async def reserve(self, quota_key: str, **limits: int) -> None:
        self.reservations.append(quota_key)

    async def ready(self) -> None:
        return None

    async def close(self) -> None:
        return None


class StubDetector:
    """Inject controlled latency without paid work."""

    public_key = None

    def __init__(self, *, delay: float = 0) -> None:
        self.calls = 0
        self.delay = delay
        self.cancelled = False
        self.started = asyncio.Event()

    async def classify(self, message: str, request_id: str, **kwargs: object) -> Result:
        self.calls += 1
        self.started.set()
        try:
            await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return Result(Label.UNKNOWN)

    async def close(self) -> None:
        return None


@asynccontextmanager
async def client_for(*, store=None, detector=None, **overrides):
    """Start injected resources without reading local secrets."""
    store = store or MemoryAudit()
    detector = detector or StubDetector()
    app = create_app(settings=settings(**overrides), database=store, detector=detector)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="https://example.test",
        ) as client:
            yield client, store, detector, app


async def test_success_follows_commit_and_cookie_is_opaque() -> None:
    async with client_for() as (client, store, detector, app):
        response = await client.post("/api/classify", json={"message": MARKER})
        assert response.json()["label"] == "Unknown"
        row = store.rows[UUID(response.json()["request_id"])]
        assert row["state"] == "completed"
        assert MARKER not in repr(store.rows)
        assert "httponly" in response.headers["set-cookie"].lower()
        assert "samesite=lax" in response.headers["set-cookie"].lower()
        first = store.reservations[0]
        await client.post("/api/classify", json={"message": "literal"})
        assert store.reservations[1] == first
        cookie, replacement = app.state.services.session("tampered")
        assert replacement != first and first not in cookie


@pytest.mark.parametrize("failure", ["initial", "final"])
async def test_audit_failure_never_returns_label(failure: str, caplog) -> None:
    async with client_for(store=MemoryAudit(failure=failure)) as (client, store, detector, app):
        response = await client.post("/api/classify", json={"message": MARKER})
        assert response.status_code == 503 and "label" not in response.json()
        assert detector.calls == (0 if failure == "initial" else 1)
        assert MARKER not in caplog.text


@pytest.mark.parametrize(
    "body,path,status",
    [
        (b"x" * 16385, "/api/classify", 413),
        (b"{", "/api/classify", 400),
        (b'{"message":12}', "/api/classify", 422),
        (b'{"message":"  "}', "/api/classify", 422),
        (b"", "/unmatched-PRIVATE_SYNTHETIC_MARKER", 404),
    ],
)
async def test_invalid_and_unmatched_requests_are_audited(body, path, status) -> None:
    async with client_for() as (client, store, detector, app):

        async def chunks():
            yield body[:8192]
            yield body[8192:]

        response = await client.post(path, content=chunks() if status == 413 else body)
        assert response.status_code == status
        await asyncio.sleep(0)
        assert len(store.rows) == 1 and detector.calls == 0
        assert MARKER not in repr(store.rows)


async def test_all_http_capacity_rejects_before_database() -> None:
    async with client_for(http_window_limit=1) as (client, store, detector, app):
        assert (await client.get("/missing")).status_code == 404
        response = await client.get("/other")
        assert response.status_code == 503 and len(store.rows) == 1
        assert detector.calls == 0
        assert app.state.services.diagnostics["audit_capacity_unavailable"] == 1


async def test_deadline_cancels_provider_and_recovers_capacity() -> None:
    detector = StubDetector(delay=1)
    async with client_for(detector=detector, request_timeout_seconds=0.03) as (
        client,
        store,
        detector,
        app,
    ):
        response = await client.post("/api/classify", json={"message": "hello"})
        assert response.status_code == 504 and detector.cancelled
        await asyncio.sleep(0.01)
        assert app.state.services.model_active == 0
        assert app.state.services.http_capacity.active == 0


async def test_model_slots_reject_busy_without_provider_or_quota_reservation() -> None:
    detector = StubDetector(delay=0.1)
    async with client_for(detector=detector, model_slots=1) as (client, store, detector, app):
        first = asyncio.create_task(client.post("/api/classify", json={"message": "one"}))
        async with asyncio.timeout(2):
            await detector.started.wait()
        busy = await client.post("/api/classify", json={"message": "two"})
        assert busy.status_code == 429 and len(store.reservations) == 1
        assert (await first).status_code == 200
        assert (await client.post("/api/classify", json={"message": "three"})).status_code == 200
        assert len(store.reservations) == detector.calls == 2
        assert app.state.services.model_active == 0


@pytest.mark.postgres
async def test_synthetic_marker_sweep_db_logs_actual_exports(
    db: Database, provider_factory, caplog
) -> None:
    make, spans, calls = provider_factory
    detector = make()
    async with client_for(store=db, detector=detector) as (client, store, detector, app):
        response = await client.post("/api/classify", json={"message": MARKER})
        assert response.status_code == 200
        detector.tracer.flush()
        async with db.sessions() as session:
            row = await session.get(AuditRequest, UUID(response.json()["request_id"]))
            values = {
                column.name: getattr(row, column.name) for column in AuditRequest.__table__.columns
            }
            assert row.trace_id and row.label == "Sarcasm Detected"
            assert MARKER not in repr(values)
        assert MARKER not in caplog.text
        assert MARKER not in repr([dict(span.attributes or {}) for span in spans])
