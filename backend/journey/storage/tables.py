from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
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

scoring_runs = Table(
    "scoring_runs",
    metadata,
    Column("run_id", String, primary_key=True),
    Column("journey_id", String, nullable=False),
    Column("evaluated_at", String, nullable=False),   # ISO-8601 UTC
    Column("objective_json", Text, nullable=False),
    Column("result_json", Text, nullable=False),      # full ScoringRun as JSON
    Column("selected_option_id", String, nullable=True),
    Column("option_count", Integer, nullable=False),
    Column("eliminated_count", Integer, nullable=False),
    Column("created_at", String, nullable=False),     # ISO-8601 UTC
)

journey_events = Table(
    "journey_events",
    metadata,
    Column("event_id", String, primary_key=True),
    Column("journey_id", String, ForeignKey("journeys.journey_id"), nullable=False),
    Column("sequence", Integer, nullable=False),      # per-journey monotonic from 1; SSE Last-Event-ID
    Column("event_type", String, nullable=False),
    Column("payload_json", Text, nullable=False),     # JSON-encoded typed payload
    Column("simulated", Integer, nullable=False, default=0),  # 0/1 (Principle V)
    Column("recorded_at", String, nullable=False),    # ISO-8601 UTC
    UniqueConstraint("journey_id", "sequence", name="uq_journey_events_journey_sequence"),
)

verifications = Table(
    "verifications",
    metadata,
    Column("verification_id", String, primary_key=True),
    Column("journey_id", String, ForeignKey("journeys.journey_id"), nullable=False),
    Column("option_id", String, ForeignKey("flight_options.option_id"), nullable=False),
    Column("requested_at", String, nullable=False),          # ISO-8601 UTC
    Column("responded_at", String, nullable=False),          # ISO-8601 UTC
    Column("raw_response_json", Text, nullable=False),
    Column("status_code", Integer, nullable=False),
    Column("atlas_status", Integer, nullable=True),          # null only if body unparseable
    Column("outcome", String, nullable=False),                # VERIFIED | PRICE_CHANGED | UNAVAILABLE | RATE_LIMITED | ERROR
    Column("session_id", String, nullable=True),              # set only on VERIFIED/PRICE_CHANGED
    Column("max_seats", Integer, nullable=True),               # set only on VERIFIED/PRICE_CHANGED
    Column("price_change_json", Text, nullable=True),          # JSON-encoded PriceChange, if present
    Column("passenger_requirements_json", Text, nullable=False),  # JSON-encoded list, may be "[]"
    Column("budget_before", Integer, nullable=False),
    Column("budget_after", Integer, nullable=False),
)

orders = Table(
    "orders",
    metadata,
    Column("order_id", String, primary_key=True),
    Column("journey_id", String, ForeignKey("journeys.journey_id"), nullable=False),
    Column("option_id", String, ForeignKey("flight_options.option_id"), nullable=False),
    Column("requested_at", String, nullable=False),           # ISO-8601 UTC
    Column("responded_at", String, nullable=True),            # null only on UNCERTAIN (no response received)
    Column("raw_response_json", Text, nullable=True),         # null only alongside responded_at
    Column("outcome", String, nullable=False),                 # CREATED | DUPLICATE_REJECTED | UNCERTAIN | ERROR
    Column("order_no", String, nullable=True),                 # set on CREATED, or after DUPLICATE_REJECTED resolution
    Column("booking_reference", String, nullable=True),        # pnrCode; set only on CREATED
    Column("ticketing_deadline", String, nullable=True),       # tktLimitTime, ISO-8601 UTC; set only on CREATED
    Column("session_id_used", String, nullable=False),         # the sessionId sent, recorded for audit
)

payments = Table(
    "payments",
    metadata,
    Column("payment_id", String, primary_key=True),
    Column("journey_id", String, ForeignKey("journeys.journey_id"), nullable=False),
    Column("order_no", String, nullable=False),
    Column("requested_at", String, nullable=False),           # ISO-8601 UTC
    Column("responded_at", String, nullable=True),            # null only on UNCERTAIN
    Column("raw_response_json", Text, nullable=True),         # null only alongside responded_at
    Column("outcome", String, nullable=False),                 # SUCCESS | DECLINED | UNCERTAIN | ERROR
)

ticketing_queries = Table(
    "ticketing_queries",
    metadata,
    Column("query_id", String, primary_key=True),
    Column("journey_id", String, ForeignKey("journeys.journey_id"), nullable=False),
    Column("order_no", String, nullable=False),
    Column("queried_at", String, nullable=False),              # ISO-8601 UTC
    Column("raw_response_json", Text, nullable=False),
    Column("order_status", String, nullable=True),             # audit only — never used to confirm ticketing
    Column("ticket_status", String, nullable=True),            # audit only — never used to confirm ticketing
    Column("passenger_ticket_numbers_json", Text, nullable=False),  # list[list[str]], one per passenger
    Column("confirmed", Integer, nullable=False, default=0),   # 0/1 — True only if every passenger has ticket numbers
    Column("is_terminal_error", Integer, nullable=False, default=0),  # 0/1 — True if errorCode was non-null
)

verification_attempts = Table(
    "verification_attempts",
    metadata,
    Column("attempt_id", String, primary_key=True),
    Column("journey_id", String, ForeignKey("journeys.journey_id"), nullable=False),
    Column("action_type", String, nullable=False),
    Column("affected_record_id", String, nullable=False),
    Column("action_response_json", Text, nullable=True),
    Column("queried_at", String, nullable=False),              # ISO-8601 UTC
    Column("observed_at", String, nullable=False),              # ISO-8601 UTC — governs FR-011 ordering
    Column("query_result_json", Text, nullable=False),
    Column("classification", String, nullable=False),          # SUCCESS | FAILURE | UNRESOLVED
    Column("condition_result", String, nullable=False),        # SUCCESS | FAILURE | INCONCLUSIVE | NOT_FOUND
    Column("has_discrepancy", Integer, nullable=False, default=0),   # 0/1
    Column("applied_to_state", Integer, nullable=False, default=0),  # 0/1
)

webhook_notifications = Table(
    "webhook_notifications",
    metadata,
    Column("notification_id", String, primary_key=True),
    Column("received_at", String, nullable=False),              # ISO-8601 UTC
    Column("declared_event_type", String, nullable=False),      # raw `type` field; "" if malformed/absent
    Column("order_reference", String, nullable=True),           # raw order reference; None if absent/malformed
    Column("raw_payload_json", Text, nullable=False),           # exact, unmodified body (FR-002)
    Column("journey_id", String, ForeignKey("journeys.journey_id"), nullable=True),
    Column("associated", Integer, nullable=False, default=0),   # 0/1 — explicit, not merely journey_id is not null
    Column("confirmation_triggered", Integer, nullable=False, default=0),  # 0/1
    Column("simulated", Integer, nullable=False, default=0),    # 0/1 — set only by the disruption injector (008)
)
