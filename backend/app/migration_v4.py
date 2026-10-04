"""Frozen Module 4 additive intelligence tables. Never imports current models."""

import sqlalchemy as sa

metadata = sa.MetaData()
for name, type in [
    ("companies", sa.String(36)),
    ("contacts", sa.String(36)),
    ("profiles", sa.Integer()),
    ("outreach", sa.String(36)),
    ("jobs", sa.String(36)),
]:
    sa.Table(name, metadata, sa.Column("id", type, primary_key=True))
sa.Table(
    "candidates",
    metadata,
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column("domain", sa.String(length=255), primary_key=False, nullable=False),
    sa.Column("name", sa.String(length=255), primary_key=False, nullable=False),
    sa.Column("website", sa.Text(), primary_key=False, nullable=False),
    sa.Column("industry", sa.String(length=100), primary_key=False, nullable=False),
    sa.Column("distance_miles", sa.Float(), primary_key=False, nullable=True),
    sa.Column("status", sa.String(length=30), primary_key=False, nullable=False),
    sa.Column(
        "company_id",
        sa.String(length=36),
        sa.ForeignKey("companies.id"),
        primary_key=False,
        nullable=True,
    ),
    sa.Column("observations", sa.JSON(), primary_key=False, nullable=False),
    sa.Column("contexts", sa.JSON(), primary_key=False, nullable=False),
    sa.Column(
        "updated_at", sa.DateTime(timezone=True), primary_key=False, nullable=False
    ),
    sa.UniqueConstraint("domain"),
)
sa.Table(
    "contact_observations",
    metadata,
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column(
        "company_id",
        sa.String(length=36),
        sa.ForeignKey("companies.id"),
        primary_key=False,
        nullable=False,
    ),
    sa.Column(
        "contact_id",
        sa.String(length=36),
        sa.ForeignKey("contacts.id"),
        primary_key=False,
        nullable=False,
    ),
    sa.Column("field", sa.String(length=40), primary_key=False, nullable=False),
    sa.Column("value", sa.Text(), primary_key=False, nullable=False),
    sa.Column("provider", sa.String(length=30), primary_key=False, nullable=False),
    sa.Column("external_id", sa.String(length=255), primary_key=False, nullable=False),
    sa.Column("source_url", sa.Text(), primary_key=False, nullable=False),
    sa.Column("confidence", sa.String(length=30), primary_key=False, nullable=False),
    sa.Column(
        "retrieved_at", sa.DateTime(timezone=True), primary_key=False, nullable=False
    ),
    sa.Column(
        "verified_at", sa.DateTime(timezone=True), primary_key=False, nullable=True
    ),
)
sa.Index(
    "ix_contact_observations_company_id",
    metadata.tables["contact_observations"].c["company_id"],
)
sa.Index(
    "ix_contact_observations_contact_id",
    metadata.tables["contact_observations"].c["contact_id"],
)
sa.Table(
    "student_facts",
    metadata,
    sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
    sa.Column(
        "profile_id",
        sa.Integer(),
        sa.ForeignKey("profiles.id"),
        primary_key=False,
        nullable=False,
    ),
    sa.Column("profile_hash", sa.String(length=64), primary_key=False, nullable=False),
    sa.Column("field", sa.String(length=40), primary_key=False, nullable=False),
    sa.Column("text", sa.Text(), primary_key=False, nullable=False),
    sa.Column(
        "verified_at", sa.DateTime(timezone=True), primary_key=False, nullable=False
    ),
)
sa.Index(
    "ix_student_facts_profile_hash", metadata.tables["student_facts"].c["profile_hash"]
)
sa.Table(
    "generations",
    metadata,
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column(
        "company_id",
        sa.String(length=36),
        sa.ForeignKey("companies.id"),
        primary_key=False,
        nullable=False,
    ),
    sa.Column(
        "outreach_id",
        sa.String(length=36),
        sa.ForeignKey("outreach.id"),
        primary_key=False,
        nullable=True,
    ),
    sa.Column(
        "job_id",
        sa.String(length=36),
        sa.ForeignKey("jobs.id"),
        primary_key=False,
        nullable=True,
    ),
    sa.Column(
        "prompt_version", sa.String(length=100), primary_key=False, nullable=False
    ),
    sa.Column("provider", sa.String(length=40), primary_key=False, nullable=False),
    sa.Column("model", sa.String(length=80), primary_key=False, nullable=False),
    sa.Column("settings", sa.JSON(), primary_key=False, nullable=False),
    sa.Column("input_hash", sa.String(length=64), primary_key=False, nullable=False),
    sa.Column("evidence_ids", sa.JSON(), primary_key=False, nullable=False),
    sa.Column("student_fact_ids", sa.JSON(), primary_key=False, nullable=False),
    sa.Column("subject", sa.String(length=200), primary_key=False, nullable=False),
    sa.Column("body", sa.Text(), primary_key=False, nullable=False),
    sa.Column("review", sa.JSON(), primary_key=False, nullable=False),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), primary_key=False, nullable=False
    ),
)
sa.Index("ix_generations_company_id", metadata.tables["generations"].c["company_id"])
sa.Index("ix_generations_input_hash", metadata.tables["generations"].c["input_hash"])
sa.Index("ix_generations_outreach_id", metadata.tables["generations"].c["outreach_id"])
