"""Short PostgreSQL audit/admission transactions; never store message text."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import DateTime, Float, Integer, String, Uuid, delete, select, text, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import DatabaseSettings, database_url
from app.contracts import AppError

REVISION = "0001"


@dataclass(frozen=True)
class MaintenanceResult:
    """Bounded preview/apply counts and the exact policy cutoff."""

    request_rows: int
    quota_rows: int
    cutoff: datetime


class Base(DeclarativeBase):
    """Versioned application tables."""


class AuditRequest(Base):
    """Metadata-only durable request lifecycle."""

    __tablename__ = "audit_requests"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    kind: Mapped[str] = mapped_column(String(32))
    method: Mapped[str] = mapped_column(String(16))
    route: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(16), index=True)
    http_status: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(64))
    label: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(64))
    prompt_revision: Mapped[str | None] = mapped_column(String(32))
    schema_revision: Mapped[str | None] = mapped_column(String(32))
    input_length: Mapped[int | None] = mapped_column(Integer)
    trace_id: Mapped[str | None] = mapped_column(String(32))
    provider_id: Mapped[str | None] = mapped_column(String(128))
    elapsed_ms: Mapped[float | None] = mapped_column(Float)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)


class AdmissionCounter(Base):
    """Durable aggregate quota reservations, not raw browser identifiers."""

    __tablename__ = "admission_counters"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    count: Mapped[int] = mapped_column(Integer)


class Database:
    """An app-lifetime engine with independent per-operation sessions."""

    def __init__(self, settings: DatabaseSettings, *, schema: str | None = None) -> None:
        url = database_url(settings.database_url.get_secret_value())
        self.schema = schema
        connect_args = {"options": f"-csearch_path={schema}"} if schema else {}
        self.engine: AsyncEngine = create_async_engine(
            url,
            pool_size=4,
            max_overflow=0,
            pool_timeout=2,
            connect_args=connect_args,
            hide_parameters=True,
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def ready(self) -> None:
        """Require the deployed migration head; do not auto-create tables."""
        async with self.engine.connect() as connection:
            version = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            if version != REVISION:
                raise AppError("storage_unavailable", 503, "Database migration is required.")
            await connection.execute(select(AuditRequest.id).limit(1))

    async def begin(self, request_id: UUID, *, kind: str, method: str, route: str) -> None:
        """Commit a pending request before any admitted work."""
        async with self.sessions.begin() as session:
            session.add(
                AuditRequest(
                    id=request_id,
                    started_at=datetime.now(UTC),
                    kind=kind,
                    method=method[:16],
                    route=route,
                    state="pending",
                )
            )

    async def finish(self, request_id: UUID, *, status: int, **fields: object) -> None:
        """Finalize exactly the pending row; an absent/stale row cannot succeed."""
        state = "completed" if status < 400 else ("rejected" if status < 500 else "failed")
        async with self.sessions.begin() as session:
            result = await session.execute(
                update(AuditRequest)
                .where(
                    AuditRequest.id == request_id,
                    AuditRequest.state == "pending",
                )
                .values(finalized_at=datetime.now(UTC), http_status=status, state=state, **fields)
            )
            if result.rowcount != 1:
                raise AppError("storage_unavailable", 503, "Request audit could not be finalized.")

    async def reserve(
        self, quota_key: str, *, window_limit: int, day_limit: int, session_limit: int
    ) -> None:
        """Atomically reserve all counters; rejected attempts change none."""
        now = datetime.now(UTC)
        minute = now.replace(second=0, microsecond=0)
        day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        counters = [
            ("global-minute", minute, minute + timedelta(minutes=1), window_limit),
            ("global-day", day, day + timedelta(days=1), day_limit),
            (f"session:{quota_key}", minute, minute + timedelta(minutes=1), session_limit),
        ]
        async with self.sessions.begin() as session:
            for key, start, expires, limit in counters:
                statement = insert(AdmissionCounter).values(
                    key=key,
                    window_start=start,
                    expires_at=expires,
                    count=1,
                )
                statement = statement.on_conflict_do_update(
                    index_elements=["key", "window_start"],
                    set_={"count": AdmissionCounter.count + 1},
                    where=AdmissionCounter.count < limit,
                ).returning(AdmissionCounter.count)
                if await session.scalar(statement) is None:
                    raise AppError("rate_limited", 429, "Request limit reached; try later.")

    async def maintenance(
        self,
        settings: DatabaseSettings,
        *,
        operation: str,
        apply: bool,
    ) -> MaintenanceResult:
        """Preview/apply a bounded stale or expired batch; preserve active quotas."""
        if operation not in {"reconcile", "purge"}:
            raise ValueError("Maintenance operation must be reconcile or purge")
        now = datetime.now(UTC)
        cutoff = now - (
            timedelta(seconds=settings.stale_after_seconds)
            if operation == "reconcile"
            else timedelta(days=settings.retention_days)
        )
        stale = (
            AuditRequest.state == "pending",
            AuditRequest.started_at < cutoff,
        )
        expired = (AuditRequest.started_at < cutoff,)
        filters = stale if operation == "reconcile" else expired
        async with self.sessions.begin() as session:
            ids = list(
                (
                    await session.scalars(
                        select(AuditRequest.id)
                        .where(*filters)
                        .limit(settings.maintenance_batch_size)
                        .with_for_update(skip_locked=True)
                    )
                ).all()
            )
            if apply and ids:
                if operation == "reconcile":
                    await session.execute(
                        update(AuditRequest)
                        .where(
                            AuditRequest.id.in_(ids),
                            *stale,
                        )
                        .values(state="interrupted", finalized_at=now, error_code="interrupted")
                    )
                else:
                    await session.execute(delete(AuditRequest).where(AuditRequest.id.in_(ids)))
            keys = []
            if operation == "purge":
                keys = list(
                    (
                        await session.execute(
                            select(AdmissionCounter.key, AdmissionCounter.window_start)
                            .where(AdmissionCounter.expires_at < cutoff)
                            .limit(settings.maintenance_batch_size)
                            .with_for_update(skip_locked=True)
                        )
                    ).all()
                )
                if apply and keys:
                    await session.execute(
                        delete(AdmissionCounter).where(
                            tuple_(AdmissionCounter.key, AdmissionCounter.window_start).in_(keys)
                        )
                    )
            return MaintenanceResult(len(ids), len(keys), cutoff)

    async def close(self) -> None:
        """Release engine connections at app/test shutdown."""
        await self.engine.dispose()
