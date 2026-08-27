from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)

metadata = MetaData()

journeys = Table(
    "journeys",
    metadata,
    Column("journey_id", String, primary_key=True),
    Column("state", String, nullable=False),
    Column("objective_json", Text, nullable=False),
    Column("schema_version", Integer, nullable=False, default=1),
    Column("created_at", String, nullable=False),  # ISO-8601 UTC
    Column("updated_at", String, nullable=False),  # ISO-8601 UTC
)

audit_entries = Table(
    "audit_entries",
    metadata,
    Column("entry_id", String, primary_key=True),
    Column("journey_id", String, ForeignKey("journeys.journey_id"), nullable=False),
    Column("entry_type", String, nullable=False),
    Column("content", Text, nullable=False),
    Column("recorded_at", String, nullable=False),  # ISO-8601 UTC
    Column("sequence", Integer, nullable=False),
)

held_identifiers = Table(
    "held_identifiers",
    metadata,
    Column("identifier_id", String, primary_key=True),
    Column("journey_id", String, ForeignKey("journeys.journey_id"), nullable=False),
    Column("value", String, nullable=False),
    Column("issued_at", String, nullable=False),   # ISO-8601 UTC
    Column("stale_after_seconds", Integer, nullable=False),
    Column("stale_at", String, nullable=False),    # ISO-8601 UTC, computed on write
)

authorisation_outcomes = Table(
    "authorisation_outcomes",
    metadata,
    Column("outcome_id", String, primary_key=True),
    Column("journey_id", String, ForeignKey("journeys.journey_id"), nullable=False),
    Column("request_desc", Text, nullable=False),
    Column("outcome", String, nullable=False),
    Column("recorded_by", String, nullable=False),
    Column("timestamp", String, nullable=False),   # ISO-8601 UTC
)
