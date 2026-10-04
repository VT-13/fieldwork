"""Frozen additive durable job leases and response linkage."""

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "jobs", sa.Column("available_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "jobs",
        sa.Column("owner_token", sa.String(36), server_default="", nullable=False),
    )
    op.add_column(
        "jobs", sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index("ix_jobs_available_at", "jobs", ["available_at"])
    for name, table in [("contact_id", "contacts"), ("outreach_id", "outreach")]:
        with op.batch_alter_table("events") as batch:
            batch.add_column(sa.Column(name, sa.String(36), nullable=True))
            batch.create_foreign_key("events_" + name + "_fk", table, [name], ["id"])
    op.add_column(
        "events",
        sa.Column(
            "campaign_id", sa.String(40), server_default="personal", nullable=False
        ),
    )


def downgrade():
    raise RuntimeError(
        "Runtime history rollback requires verified backup; never erase response linkage"
    )
