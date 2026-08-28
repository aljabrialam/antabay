"""CLI to seed a journey + event stream for Playwright E2E tests.

Each invocation creates a brand-new journey (a fresh UUID) so tests can run
in any order without needing to clean up after themselves (Constitution
Principle XIII: tests MUST create and clean their own data). Prints the new
journey_id (and, for `auth`, the request_id) to stdout as the last line so
the caller can parse it without depending on any other log output.

Usage (run from backend/, with JOURNEY_DB_URL set to the same DB the
running server is using):
    python -m scripts.seed_console_fixture live
    python -m scripts.seed_console_fixture auth
    python -m scripts.seed_console_fixture replay
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from journey.models.events import EventType, objective_set_payload_from
from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
from journey.services.event_service import EventService
from journey.services.journey_service import JourneyService
from journey.storage.db import get_engine
from journey.storage.tables import metadata

FIXTURE_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "journey_events_001.json"


def _new_journey() -> tuple[str, TravelObjective]:
    objective = TravelObjective(
        origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
        destination=ConstrainedField(value="NRT", constraint_type=ConstraintType.HARD),
        preferences=ConstrainedField(
            value=["window seat"], constraint_type=ConstraintType.SOFT
        ),
    )
    journey = JourneyService().create_journey(objective)
    return journey.journey_id, objective


def seed_live() -> str:
    journey_id, objective = _new_journey()
    svc = EventService()
    svc.append(journey_id, EventType.OBJECTIVE_SET, objective_set_payload_from(objective))
    svc.append(
        journey_id,
        EventType.STATE_CHANGE,
        {"from_state": "OBJECTIVE_CONFIRMED", "to_state": "SEARCHING"},
    )
    svc.append(
        journey_id,
        EventType.EXTERNAL_CALL,
        {"endpoint": "/shopping/flightoffices", "outcome": "success", "elapsed_ms": 843},
    )
    svc.append(journey_id, EventType.CALL_BUDGET_UPDATED, {"budget_remaining": 9})
    svc.append(
        journey_id,
        EventType.IDENTIFIER_ISSUED,
        {
            "identifier_id": "routingIdentifier",
            "value": "rtg_abc123",
            "stale_after_seconds": 463,
            "stale_at": "2026-09-05T09:27:43Z",
        },
    )
    svc.append(
        journey_id,
        EventType.IDENTIFIER_ISSUED,
        {
            "identifier_id": "offerWindow",
            "value": "offer_xyz789",
            "stale_after_seconds": 0,
            "stale_at": "2026-09-05T09:20:18Z",
        },
    )
    svc.append(
        journey_id,
        EventType.IDENTIFIER_EXPIRED,
        {"identifier_id": "offerWindow"},
    )
    svc.append(
        journey_id,
        EventType.OPTION_REJECTED,
        {
            "option_id": "7C907+7C1151",
            "constraint_violated": "no overnight connection",
            "satisfies_numeric_constraints": True,
        },
    )
    return journey_id


def seed_auth() -> tuple[str, str]:
    journey_id = seed_live()
    request_id = "req-1"
    EventService().append(
        journey_id,
        EventType.AUTHORISATION_REQUESTED,
        {
            "request_id": request_id,
            "action": "Rebook LJ201 · arr 09:55",
            "cost": "+USD 6.24",
            "objective_effect": "Preserved",
            "rule_id": "AUTH-01",
        },
    )
    return journey_id, request_id


def seed_replay() -> str:
    from datetime import datetime

    journey_id, _ = _new_journey()
    svc = EventService()
    fixture = json.loads(FIXTURE_PATH.read_text())
    for row in fixture:
        svc.append(
            journey_id,
            EventType(row["event_type"]),
            row["payload"],
            simulated=row["simulated"],
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
        )
    return journey_id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=["live", "auth", "replay"])
    args = parser.parse_args()

    metadata.create_all(get_engine())

    if args.scenario == "live":
        print(json.dumps({"journey_id": seed_live()}))
    elif args.scenario == "auth":
        journey_id, request_id = seed_auth()
        print(json.dumps({"journey_id": journey_id, "request_id": request_id}))
    else:
        print(json.dumps({"journey_id": seed_replay()}))


if __name__ == "__main__":
    sys.exit(main())
