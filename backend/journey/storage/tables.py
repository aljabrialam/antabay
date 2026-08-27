from sqlalchemy import (
    Boolean,
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
    Column("call_budget", Integer, nullable=False, default=20),
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

search_records = Table(
    "search_records",
    metadata,
    Column("search_id", String, primary_key=True),
    Column("journey_id", String, ForeignKey("journeys.journey_id"), nullable=False),
    Column("requested_at", String, nullable=False),   # ISO-8601 UTC
    Column("responded_at", String, nullable=False),   # ISO-8601 UTC
    Column("raw_response_json", Text, nullable=False),
    Column("status_code", Integer, nullable=False),
    Column("atlas_status", Integer, nullable=False),
    Column("option_count", Integer, nullable=False),
    Column("budget_before", Integer, nullable=False),
    Column("budget_after", Integer, nullable=False),
    Column("outcome", String, nullable=False),        # SUCCESS | EMPTY | RATE_LIMITED | ERROR
)

flight_options = Table(
    "flight_options",
    metadata,
    Column("option_id", String, primary_key=True),
    Column("journey_id", String, ForeignKey("journeys.journey_id"), nullable=False),
    Column("search_record_id", String, ForeignKey("search_records.search_id"), nullable=False),
    Column("fid", String, nullable=False),
    Column("routing_identifier", String, nullable=False),
    Column("currency", String, nullable=False),
    Column("adult_price", String, nullable=False),    # TEXT for Decimal precision
    Column("adult_tax", String, nullable=False),
    Column("transaction_fee", String, nullable=False),
    Column("refreshed_at", String, nullable=True),    # ISO-8601 UTC; nullable
    Column("expire_at", String, nullable=True),       # ISO-8601 UTC; nullable
    Column("is_multi_leg", Integer, nullable=False),  # 0/1
    Column("separate_bookings", Integer, nullable=False),  # 0/1
    Column("recorded_at", String, nullable=False),    # ISO-8601 UTC; injected now
)

legs = Table(
    "legs",
    metadata,
    Column("leg_id", String, primary_key=True),
    Column("option_id", String, ForeignKey("flight_options.option_id"), nullable=False),
    Column("segment_index", Integer, nullable=False),
    Column("carrier", String, nullable=False),
    Column("flight_number", String, nullable=False),
    Column("dep_airport", String, nullable=False),
    Column("dep_time", String, nullable=False),       # YYYYMMDDHHMM local
    Column("arr_airport", String, nullable=False),
    Column("arr_time", String, nullable=False),       # YYYYMMDDHHMM local
    Column("duration_minutes", Integer, nullable=False),
    Column("stop_cities", String, nullable=False),    # empty string if none
    Column("cabin_class", String, nullable=False),
    Column("seat_count", Integer, nullable=False),
    Column("risk_sellout", Integer, nullable=False),  # 0/1
    Column("code_share", Integer, nullable=False),    # 0/1
    Column("aircraft_code", String, nullable=False),
    Column("fare_family", String, nullable=True),
)
