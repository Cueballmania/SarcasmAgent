"""Establish metadata-only audit and durable quota tables."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the initial schema; no audience text column."""
    op.create_table(
        "audit_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True)),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("route", sa.String(64), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("http_status", sa.Integer()),
        sa.Column("error_code", sa.String(64)),
        sa.Column("label", sa.String(32)),
        sa.Column("model", sa.String(64)),
        sa.Column("prompt_revision", sa.String(32)),
        sa.Column("schema_revision", sa.String(32)),
        sa.Column("input_length", sa.Integer()),
        sa.Column("trace_id", sa.String(32)),
        sa.Column("provider_id", sa.String(128)),
        sa.Column("elapsed_ms", sa.Float()),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("cost_usd", sa.Float()),
    )
    op.create_index("ix_audit_requests_started_at", "audit_requests", ["started_at"])
    op.create_index("ix_audit_requests_state", "audit_requests", ["state"])
    op.create_table(
        "admission_counters",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
    )
    op.create_index("ix_admission_counters_expires_at", "admission_counters", ["expires_at"])


def downgrade() -> None:
    """Require an operator-approved recovery plan rather than erase audits."""
    raise RuntimeError(
        "Destructive downgrade disabled; restore/roll forward under operator control"
    )
