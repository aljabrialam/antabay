"""Unit tests for capture_export (014-demonstration-capture, T023-T025).

TDD gate: these tests must fail with NotImplementedError against the
Phase 2 skeleton before implementation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _file_db(tmp_path: Any) -> None:
    db_url = f"sqlite:///{tmp_path / 'capture_export.db'}"
    os.environ["JOURNEY_DB_URL"] = db_url
    from journey.storage.db import get_engine, reset_engine
    from journey.storage.tables import metadata

    reset_engine()
    metadata.create_all(get_engine())


def _repo() -> Any:
    from journey.storage.repository import JourneyRepository

    return JourneyRepository()


def _seed_journey_with_events(repo: Any) -> str:
    from journey.models.events import EventType
    from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
    from journey.services.event_service import EventService
    from journey.services.journey_service import JourneyService

    objective = TravelObjective(
        origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
    )
    journey = JourneyService(repository=repo).create_journey(objective)
    events = EventService(repo)
    events.append(
        journey.journey_id,
        EventType.STATE_CHANGE,
        {"from_state": "OBJECTIVE_CONFIRMED", "to_state": "SEARCHING"},
    )
    events.append(
        journey.journey_id,
        EventType.CALL_BUDGET_UPDATED,
        {"budget_remaining": 9},
    )
    return journey.journey_id


class TestExportWritesEventStreamFile:
    def test_export_writes_json_matching_fixture_shape(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey_with_events(repo)

        from scripts.capture_export import export

        out_path = tmp_path / f"{journey_id}.json"
        export(journey_id, out_path)

        rows = json.loads(out_path.read_text())
        assert len(rows) == 2
        assert rows[0]["event_type"] == "state_change"
        assert rows[0]["payload"] == {"from_state": "OBJECTIVE_CONFIRMED", "to_state": "SEARCHING"}
        assert rows[0]["simulated"] is False
        assert "recorded_at" in rows[0]
        assert rows[1]["event_type"] == "call_budget_updated"


class TestPromoteUpdatesCanonicalManifest:
    def test_promote_writes_canonical_manifest(self, tmp_path: Any) -> None:
        from scripts.capture_export import promote

        capture_file = tmp_path / "some-journey.json"
        capture_file.write_text("[]")
        manifest_path = tmp_path / "canonical.json"

        promote(capture_file, manifest_path=manifest_path)

        manifest = json.loads(manifest_path.read_text())
        assert manifest["canonical_file"] == "some-journey.json"
        assert "promoted_at" in manifest

    def test_promote_overwrites_previous_canonical(self, tmp_path: Any) -> None:
        from scripts.capture_export import promote

        first = tmp_path / "first.json"
        first.write_text("[]")
        second = tmp_path / "second.json"
        second.write_text("[]")
        manifest_path = tmp_path / "canonical.json"

        promote(first, manifest_path=manifest_path)
        promote(second, manifest_path=manifest_path)

        manifest = json.loads(manifest_path.read_text())
        assert manifest["canonical_file"] == "second.json"


class TestLoadReproducesEventsIntoFreshJourney:
    def test_load_reinserts_events_into_a_new_journey(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey_with_events(repo)

        from scripts.capture_export import export, load

        out_path = tmp_path / f"{journey_id}.json"
        export(journey_id, out_path)

        new_journey_id = load(out_path)

        assert new_journey_id != journey_id
        reloaded = repo.get_events_from_sequence(new_journey_id, from_sequence=0)
        assert len(reloaded) == 2
        assert reloaded[0].event_type.value == "state_change"
        assert reloaded[1].event_type.value == "call_budget_updated"

    def test_load_makes_no_network_call(self, tmp_path: Any) -> None:
        """load() only touches the local database — no httpx client is
        constructed or used anywhere in the import path (FR-011)."""
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey_with_events(repo)

        from scripts.capture_export import export, load

        out_path = tmp_path / f"{journey_id}.json"
        export(journey_id, out_path)

        # No mock/patch of httpx is required for this to pass — load()
        # takes no http_client parameter and imports no HTTP library.
        import inspect

        source = inspect.getsource(load)
        assert "httpx" not in source

        load(out_path)  # must succeed with zero network setup
