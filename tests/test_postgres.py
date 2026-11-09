"""Real PostgreSQL migration, quota and maintenance behavior."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update

from app.config import DatabaseSettings
from app.contracts import AppError
from app.database import AdmissionCounter, AuditRequest, Database

pytestmark = pytest.mark.postgres


async def test_migrated_schema_and_audit_lifecycle(db: Database) -> None:
    await db.ready()
    request_id = uuid4()
    await db.begin(request_id, kind="classify", method="POST", route="/api/classify")
    await db.finish(request_id, status=200, label="Unknown")
    async with db.sessions() as session:
        row = await session.get(AuditRequest, request_id)
        assert row.state == "completed" and row.label == "Unknown"
        assert "message" not in AuditRequest.__table__.columns
    with pytest.raises(AppError):
        await db.finish(request_id, status=200)


async def test_concurrent_atomic_quota_and_restart(db: Database) -> None:
    async def reserve() -> bool:
        try:
            await db.reserve("opaque", window_limit=2, day_limit=2, session_limit=2)
            return True
        except AppError as error:
            assert error.code == "rate_limited"
            return False

    assert sum(await asyncio.gather(*(reserve() for _ in range(8)))) == 2
    async with db.sessions() as session:
        assert (await session.scalars(select(AdmissionCounter.count))).all() == [2, 2, 2]
    await db.close()
    restarted = Database(
        DatabaseSettings(
            _env_file=None, database_url=db.engine.url.render_as_string(hide_password=False)
        ),
        schema=db.schema,
    )
    try:
        with pytest.raises(AppError, match="rate_limited"):
            await restarted.reserve("new-session", window_limit=2, day_limit=2, session_limit=2)
    finally:
        await restarted.close()


async def test_schema_mismatch_blocks_readiness(db: Database) -> None:
    from sqlalchemy import text

    async with db.engine.begin() as connection:
        await connection.execute(text("UPDATE alembic_version SET version_num = 'wrong'"))
    with pytest.raises(AppError, match="storage_unavailable"):
        await db.ready()


async def test_rejected_session_rolls_back_global_reservation(db: Database) -> None:
    await db.reserve("same", window_limit=3, day_limit=3, session_limit=1)
    with pytest.raises(AppError):
        await db.reserve("same", window_limit=3, day_limit=3, session_limit=1)
    await db.reserve("new", window_limit=3, day_limit=3, session_limit=1)
    async with db.sessions() as session:
        assert (
            await session.scalar(
                select(AdmissionCounter.count).where(AdmissionCounter.key == "global-day")
            )
            == 2
        )


async def test_preview_reconcile_and_retention(db: Database) -> None:
    stale, fresh, expired = uuid4(), uuid4(), uuid4()
    for request_id in (stale, fresh, expired):
        await db.begin(request_id, kind="page", method="GET", route="/")
    async with db.sessions.begin() as session:
        await session.execute(
            update(AuditRequest)
            .where(AuditRequest.id == stale)
            .values(started_at=datetime.now(UTC) - timedelta(seconds=120))
        )
        await session.execute(
            update(AuditRequest)
            .where(AuditRequest.id == expired)
            .values(started_at=datetime.now(UTC) - timedelta(days=40))
        )
    settings = DatabaseSettings(_env_file=None, database_url="postgresql://localhost/test")
    preview = await db.maintenance(settings, operation="reconcile", apply=False)
    assert preview.request_rows == 2 and preview.quota_rows == 0
    async with db.sessions() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(AuditRequest)
                .where(AuditRequest.state == "pending")
            )
            == 3
        )
    batches = await asyncio.gather(
        *(db.maintenance(settings, operation="reconcile", apply=True) for _ in range(2))
    )
    assert sum(batch.request_rows for batch in batches) == 2
    assert (await db.maintenance(settings, operation="reconcile", apply=True)).request_rows == 0
    await db.reserve("active", window_limit=3, day_limit=3, session_limit=3)
    async with db.sessions.begin() as session:
        session.add(
            AdmissionCounter(
                key="expired",
                window_start=datetime.now(UTC) - timedelta(days=40),
                expires_at=datetime.now(UTC) - timedelta(days=40),
                count=1,
            )
        )
    purge = await db.maintenance(settings, operation="purge", apply=False)
    assert purge.request_rows == purge.quota_rows == 1
    applied = await db.maintenance(settings, operation="purge", apply=True)
    assert applied.request_rows == applied.quota_rows == 1
    async with db.sessions() as session:
        assert await session.get(AuditRequest, fresh) is not None
        assert await session.get(AuditRequest, expired) is None
        assert len((await session.scalars(select(AdmissionCounter))).all()) == 3
